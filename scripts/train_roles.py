"""Train, calibrate and evaluate the typed heads (token column role + value type) on synthetic statements.

Data: random bank-statement layouts rendered to PDF (text layer) and to scans read by OCR, every word labelled by the
cell it came from. Splits use different layout seeds: train / calibration / test (same generator) / shifted test
(font sizes, header words and date formats never seen in training). Trains a ~19M-parameter encoder FROM SCRATCH (no CORD-derived weights) on synthetic data only, saves int8 at rest, and
writes models/roles_head.pt, models/roles_calibration.json, models/roles_manifest.json (training config and data provenance)
and docs/evidence/roles_metrics.json.
Real statements and real scans are not covered here: see docs/HANDOFF.md.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]

from openbooks_lab.calibration_fit import ece, fit_calibrator  # noqa: E402
from openbooks_statements.calibration import Calibrator  # noqa: E402
from openbooks_statements.encoder import RoleNet, dequantize_state, h_shape, h_word, n_params, quantize_state, row_features, windows  # noqa: E402
from openbooks_statements.encoder import NB, column_heads  # noqa: E402
from openbooks_lab.golden_docs import _pdf_rows  # noqa: E402
from openbooks_statements.pdf_front import read_words  # noqa: E402
from openbooks.pipeline import Params  # noqa: E402
from openbooks_statements.roles import AMOUNT, VTYPES, vtype_of  # noqa: E402
from openbooks_lab.synth import (FAMILIES, NOISY_SCAN, ROLES, SKEW_MERCHANTS, label_words, merchant_rows, random_layout,  # noqa: E402
                             render, to_scan, with_failed_rows)

RID, TID = {r: i for i, r in enumerate(ROLES)}, {t: i for i, t in enumerate(VTYPES)}
ALPHA = 0.01
PARAM_BUDGET = 25_000_000


def items_of(pages, cells) -> list[dict]:
    out = []
    for pg in pages:
        if not pg:
            continue
        roles = label_words(pg, cells)
        for idx in windows(pg):
            ws = [pg[i] for i in idx]
            clamp = lambda v: min(1000, max(0, int(v)))  # noqa: E731
            out.append({"w": [h_word(w.text) for w in ws], "s": [h_shape(w.text) for w in ws],
                        "b": [[clamp(w.x0 * 1000 / w.pw), clamp(w.y0 * 1000 / w.ph), clamp(w.x1 * 1000 / w.pw),
                               clamp(w.y1 * 1000 / w.ph)] for w in ws],
                        "y": [RID[roles[i]] for i in idx], "t": [TID[vtype_of(pg[i].text)] for i in idx]})
    return out


def make_split(seed: int, n_text: int, n_ocr: int, shifted: bool = False, wide: bool = False,
               family: str | None = None) -> list[dict]:
    """family=None draws exactly what it always did (pinned by tests); a named family draws that synthetic family."""
    rng, items = random.Random(seed), []
    for k in range(n_text + n_ocr):
        rich = shifted or rng.random() < 0.6
        lay = random_layout(rng, shifted, rich, wide=wide, family=family)
        lay.has_header = rng.random() < 0.9
        rows = _pdf_rows(random.Random(seed + k), rng.randint(8, 40))
        if family == "skew":
            rows = merchant_rows(rows, rng, SKEW_MERCHANTS)
        if rich and rng.random() < 0.3:
            rows = with_failed_rows(rows, rng, rng.choice([1, 2]))
        pdf, cells = render(rows, "1000.00", lay, rng, closing=rows[-1][4])
        scan = k >= n_text
        scan_kw = NOISY_SCAN if family == "branch" else {}
        pages, _ = read_words(to_scan(pdf, rng, **scan_kw) if scan else pdf, Params(ocr=True))
        items += items_of(pages, cells)
        if scan and (k - n_text) % 20 == 0:
            print(f"  seed {seed}: {k - n_text + 1}/{n_ocr} scans", flush=True)
    return items


WIDE_AUG = os.environ.get("OB_WIDE") == "1"
TEXT_TYPES = {TID["text"], TID["code"]}
_AUG = random.Random(123)


def swap_vocab(it: dict) -> tuple[list[int], list[list[int]]]:
    """Unseen-wording augmentation: consistently replace some text words in one window (header words included, also
    where they appear as column-head features) with random buckets, as a statement in another vocabulary would look.
    Money and dates keep their identity. The model then learns to lean on geometry and to doubt words it never saw."""
    p = _AUG.choice([0.3, 0.6, 1.0])
    words = {h for h, t in zip(it["w"], it["t"]) if t in TEXT_TYPES}
    mp = {h: _AUG.randrange(1, NB) for h in words if _AUG.random() < p}
    return [mp.get(h, h) for h in it["w"]], [[mp.get(h, h) for h in r] for r in it["H"]]


def collate(items: list[dict], dev, aug: bool = False):
    n = max(len(i["w"]) for i in items)
    W, S = torch.zeros(len(items), n, dtype=torch.long), torch.zeros(len(items), n, dtype=torch.long)
    X = torch.zeros(len(items), n, 4, dtype=torch.long)
    R = torch.zeros(len(items), n, 2, dtype=torch.long)
    H = torch.zeros(len(items), n, 3, dtype=torch.long)
    Y, T = torch.full((len(items), n), -100), torch.full((len(items), n), -100)
    pad = torch.ones(len(items), n, dtype=torch.bool)
    for k, it in enumerate(items):
        m = len(it["w"])
        W[k, :m], S[k, :m], X[k, :m] = torch.tensor(it["w"]), torch.tensor(it["s"]), torch.tensor(it["b"])
        if "R" not in it:
            money = [t == TID["money"] for t in it["t"]]
            it["R"], it["H"] = row_features(it["b"], money), column_heads(it["b"], it["w"], money)
        ws, hs = swap_vocab(it) if aug and _AUG.random() < 0.5 else (it["w"], it["H"])
        W[k, :m] = torch.tensor(ws)
        R[k, :m], H[k, :m] = torch.tensor(it["R"]), torch.tensor(hs)
        Y[k, :m], T[k, :m], pad[k, :m] = torch.tensor(it["y"]), torch.tensor(it["t"]), False
    return [t.to(dev) for t in (W, S, X, pad, R, H, Y, T)]


@torch.no_grad()
def logits_of(net, items, dev, bs=16):
    net.eval()
    ro, ty, yr, yt = [], [], [], []
    for i in range(0, len(items), bs):
        W, S, X, pad, R, H, Y, T = collate(items[i:i + bs], dev)
        with torch.autocast("cuda", dtype=torch.float16, enabled=dev.type == "cuda"):
            r, t = net(W, S, X, pad, R, H)
        keep = ~pad
        ro.append(r.float()[keep].cpu().numpy())
        ty.append(t.float()[keep].cpu().numpy())
        yr.append(Y[keep].cpu().numpy())
        yt.append(T[keep].cpu().numpy())
    return np.concatenate(ro), np.concatenate(ty), np.concatenate(yr), np.concatenate(yt)


SEED = int(os.environ.get("OB_SEED", "1"))
LOSS = os.environ.get("OB_LOSS", "ce")


def task_loss(logits: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    logits, y = logits.float().reshape(-1, logits.shape[-1]), y.reshape(-1)
    if LOSS == "ls":
        return F.cross_entropy(logits, y, ignore_index=-100, label_smoothing=0.1)
    ce = F.cross_entropy(logits, y, ignore_index=-100, reduction="none")
    if LOSS.startswith("focal"):
        ce = ce * (1 - torch.exp(-ce)).pow(float(LOSS[5:]))
    return ce[y != -100].mean()


def train(train_items, dev, epochs: int, seed: int) -> RoleNet:
    torch.manual_seed(seed)
    net = RoleNet(len(ROLES), len(VTYPES))
    net.to(dev)
    lr_enc = 3e-4
    opt = torch.optim.AdamW([{"params": net.enc.parameters(), "lr": lr_enc},
                             {"params": list(net.role.parameters()) + list(net.vtype.parameters()), "lr": 1e-3}], weight_decay=0.01)
    base = [g["lr"] for g in opt.param_groups]
    scaler = torch.amp.GradScaler("cuda", enabled=dev.type == "cuda")
    rng, bs = random.Random(seed), 16
    total, step = epochs * math.ceil(len(train_items) / bs), 0
    for ep in range(epochs):
        net.train()
        order = list(range(len(train_items)))
        rng.shuffle(order)
        run = 0.0
        for i in range(0, len(order), bs):
            W, S, X, pad, R, H, Y, T = collate([train_items[j] for j in order[i:i + bs]], dev, aug=WIDE_AUG)
            scale = min(1.0, (step + 1) / 50) * 0.5 * (1 + math.cos(math.pi * step / total))
            for g, b in zip(opt.param_groups, base):
                g["lr"] = b * scale
            with torch.autocast("cuda", dtype=torch.float16, enabled=dev.type == "cuda"):
                r, t = net(W, S, X, pad, R, H)
            loss = task_loss(r, Y) + 0.5 * task_loss(t, T)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            run += float(loss)
            step += 1
        print(f"  epoch {ep + 1}/{epochs} loss {run / math.ceil(len(order) / bs):.4f}", flush=True)
    return net


def report(role_l, type_l, yr, yt, cal_r: Calibrator, cal_t: Calibrator) -> dict:
    money = np.array([ROLES[y] in AMOUNT for y in yr])
    pr = cal_r.probs(role_l)
    sets = cal_r.sets(role_l)
    single = np.array([len(s) == 1 for s in sets])
    covered = np.array([y in s for y, s in zip(yr, sets)])
    singleton_ok = np.array([len(s) == 1 and s[0] == y for y, s in zip(yr, sets)])
    pt = cal_t.probs(type_l)
    return {"tokens": int(len(yr)), "role_accuracy": round(float((pr.argmax(1) == yr).mean()), 4),
            "amount_tokens": int(money.sum()), "amount_role_accuracy": round(float((pr.argmax(1)[money] == yr[money]).mean()), 4),
            "type_accuracy": round(float((pt.argmax(1) == yt).mean()), 4),
            "role_ece_after_temperature": round(ece(pr, yr), 4),
            "role_coverage": round(float(covered.mean()), 4), "role_singleton_rate": round(float(single.mean()), 4),
            "amount_singleton_rate": round(float(single[money].mean()), 4),
            "amount_singleton_wrong": int((single[money] & ~singleton_ok[money]).sum()),
            "amount_abstain_rate": round(float((~single[money]).mean()), 4)}


def family_arg() -> tuple[str, ...] | None:
    """OB_FAMILIES unset: shipped behaviour (no family data). "none" or "sign,skew": a family run that trains on the listed
    families, scores every family's test split, and writes to models/fam_<tag>/ so shipped weights are never touched."""
    raw = os.environ.get("OB_FAMILIES")
    if raw is None:
        return None
    fams = tuple(f for f in raw.split(",") if f and f != "none")
    if bad := set(fams) - set(FAMILIES):
        raise SystemExit(f"unknown OB_FAMILIES {sorted(bad)}; choose from {FAMILIES}")
    return fams


def make_family_splits(n_tr: int, n_oc: int) -> dict[str, dict[str, list[dict]]]:
    """Per family: train / calib / test windows from disjoint layout seeds (100000+, clear of every other split)."""
    out = {}
    for i, fam in enumerate(FAMILIES):
        base = 100_000 + 3_000 * i
        print(f"generating family {fam}", flush=True)
        out[fam] = {"train": make_split(base, max(1, n_tr // 6), max(1, n_oc // 5), family=fam),
                    "calib": make_split(base + 1_000, max(1, n_tr // 20), max(1, n_oc // 6), family=fam),
                    "test": make_split(base + 2_000, max(1, n_tr // 20), max(1, n_oc // 6), family=fam)}
    return out


def main() -> None:
    n_tr, n_oc, epochs = (int(a) for a in (sys.argv[1:4] if len(sys.argv) > 3 else (1200, 150, 6)))
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()
    DATA = ROOT / "data" / f"roles_dataset_{n_tr}_{n_oc}.pkl"
    if DATA.exists():
        splits = pickle.loads(DATA.read_bytes())
    else:
        print("generating data", flush=True)
        scale = lambda n: max(1, n // 10)  # noqa: E731
        splits = {"train": make_split(0, n_tr, n_oc), "calib": make_split(10_000, scale(n_tr) * 2, scale(n_oc) * 5),
                  "test": make_split(20_000, scale(n_tr) * 2, scale(n_oc) * 4),
                  "shifted": make_split(30_000, scale(n_tr), scale(n_oc) * 3, shifted=True)}
        DATA.write_bytes(pickle.dumps(splits))
    WIDE = ROOT / "data" / f"roles_dataset_wide_{n_tr}_{n_oc}.pkl"
    if not WIDE_AUG:
        wide = {"train": [], "calib": []}
    elif WIDE.exists():
        wide = pickle.loads(WIDE.read_bytes())
    else:
        print("generating wide-layout data", flush=True)
        wide = {"train": make_split(40_000, n_tr // 3, max(1, n_oc // 4), wide=True),
                "calib": make_split(50_000, max(1, n_tr // 20), max(1, n_oc // 10), wide=True)}
        WIDE.write_bytes(pickle.dumps(wide))
    splits["train"], splits["calib"] = splits["train"] + wide["train"], splits["calib"] + wide["calib"]
    fams, fam = family_arg(), {}
    out_dir, tag = ROOT / "models", ""
    if fams is not None:
        FAM = ROOT / "data" / f"roles_dataset_fam_{n_tr}_{n_oc}.pkl"
        fam = pickle.loads(FAM.read_bytes()) if FAM.exists() else make_family_splits(n_tr, n_oc)
        if not FAM.exists():
            FAM.write_bytes(pickle.dumps(fam))
        for f in fams:
            splits["train"], splits["calib"] = splits["train"] + fam[f]["train"], splits["calib"] + fam[f]["calib"]
        tag = "+".join(fams) or "none"
        out_dir = ROOT / "models" / f"fam_{tag}"
        print(f"family run: trained on {fams or 'no families'}; held out {[f for f in FAMILIES if f not in fams]}; out {out_dir}", flush=True)
    print({k: len(v) for k, v in splits.items()}, f"windows, data ready in {time.time() - t0:.0f}s", flush=True)
    net = train(splits["train"], dev, epochs, seed=SEED)
    params = n_params(net)
    if params > PARAM_BUDGET:
        raise SystemExit(f"{params / 1e6:.1f}M parameters is over the {PARAM_BUDGET / 1e6:.0f}M budget")

    def evaluate(model) -> tuple[dict, Calibrator, Calibrator]:
        cl = logits_of(model, splits["calib"], dev)
        cal_r, cal_t = fit_calibrator(cl[0], cl[2], ALPHA), fit_calibrator(cl[1], cl[3], ALPHA)
        res = {"calibration": {"role_temperature": round(cal_r.temperature, 3), "role_qhat": cal_r.qhat, "alpha": ALPHA}}
        for name in ("calib", "test", "shifted"):
            lg = cl if name == "calib" else logits_of(model, splits[name], dev)
            res[name] = report(lg[0], lg[1], lg[2], lg[3], cal_r, cal_t)
        for f, parts in fam.items():
            lg = logits_of(model, parts["test"], dev)
            res[f"family_{f}"] = {**report(lg[0], lg[1], lg[2], lg[3], cal_r, cal_t), "trained_on": f in (fams or ())}
        return res, cal_r, cal_t

    fp32, _, _ = evaluate(net)
    blob = quantize_state({k: v.detach().cpu() for k, v in net.state_dict().items()})
    qnet = RoleNet(len(ROLES), len(VTYPES))
    qnet.load_state_dict(dequantize_state(blob))
    qnet.to(dev)
    int8, cal_r, cal_t = evaluate(qnet)
    print("fp32 test", json.dumps(fp32["test"]), flush=True)
    print("int8 test", json.dumps(int8["test"]), flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    weights = out_dir / "roles_head.pt"
    torch.save({"int8_state": blob}, weights)
    cal_json = {k: {"temperature": c.temperature, "qhat": None if math.isinf(c.qhat) else c.qhat, "alpha": c.alpha}
                for k, c in (("role", cal_r), ("vtype", cal_t))}
    cal_json["weights_sha256"] = hashlib.sha256(weights.read_bytes()).hexdigest()  # RoleModel.load refuses a mismatch
    (out_dir / "roles_calibration.json").write_text(json.dumps(cal_json), encoding="utf-8")
    size_mb = round(weights.stat().st_size / 1e6, 2)
    window_counts = {k: len(v) for k, v in splits.items()}
    manifest = {
        "model": "RoleNet (typed heads: column role + value type) over a LayoutLM-style encoder",
        "parameters": params, "parameters_m": round(params / 1e6, 2), "budget_m": PARAM_BUDGET // 1_000_000,
        "weights_file": str(weights.relative_to(ROOT)).replace("\\", "/"), "families_in_training": list(fams or ()), "weights_mb_int8_at_rest": size_mb,
        "init": "random (scratch). No pretrained weights are loaded: models/jepa_encoder.pt (50M) was pretrained on FUNSD+CORD and is internal-only.",
        "training_data": {"origin": "SYNTHETIC only, generated by src/openbooks/synth.py + src/openbooks/golden_docs.py (_pdf_rows)",
                          "files_read_from_data_raw": [], "windows_per_split": window_counts,
                          "layout_seeds": {"train": 0, "calibration": 10000, "test": 20000, "shifted_test": 30000,
                                           "wide_train": 40000, "wide_calibration": 50000},
                          "augmentation": "unseen-wording: per-window random remap of text-word hashes (synthetic, no external data)",
                          "text_layer_and_ocr_pages": {"train": [n_tr, n_oc]}},
        "excluded_from_training_and_shipping": ["CORD (CC BY-SA 4.0, share-alike unsettled for weights)",
                                                "nikitpatel/invoice-ner-dataset (CC-BY-NC-SA-4.0, non-commercial)",
                                                "models/jepa_encoder.pt (pretrained on CORD)"],
        "config": {"epochs": epochs, "loss": LOSS, "seed": SEED, "wide_aug": WIDE_AUG, "batch_size": 16, "lr_encoder": 3e-4, "lr_heads": 1e-3, "weight_decay": 0.01, "alpha": ALPHA,
                   "precision": "fp16 autocast", "quantization": "per-row symmetric int8 for 2D weights >= 4096 elements"},
        "source_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in
                          ("scripts/train_roles.py", "src/openbooks/synth.py", "src/openbooks/encoder.py", "src/openbooks/golden_docs.py")},
        "metrics_file": f"docs/evidence/roles_metrics{'_fam_' + tag if tag else ''}.json", "trained_at_unix": int(time.time()),
    }
    (out_dir / "roles_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    results = {"fp32": fp32, "int8_shipped": int8, "parameters": params, "weights_mb_int8": size_mb, "epochs": epochs,
               "seconds": round(time.time() - t0),
               "note": ("synthetic statements only (text layer + EasyOCR scans); 'shifted' = unseen font sizes, header words, date "
                        "formats. Coverage guarantees need exchangeable data, so expect them to weaken on shifted/real layouts. "
                        "No real statements were used or scored.")}
    (ROOT / manifest["metrics_file"]).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"shipped {params / 1e6:.2f}M params, {size_mb} MB int8, total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
