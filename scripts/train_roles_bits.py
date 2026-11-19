"""Train the bit-level typed heads (src/openbooks/bitenc.py) and score them like the shipped model.

Same layout seeds, splits, loss, schedule, calibration and report as scripts/train_roles.py, so the only change is the token
input (bits instead of hashed buckets). Also logs, per epoch, the train accuracy (exact memorisation, as in Tirumala et al.
2022) next to the calibration-split loss; the epoch where that loss first rises is where overfitting starts.
Writes docs/evidence/roles_metrics_bits.json. fp32 metrics only; nothing shipped is touched.
Usage: python scripts/train_roles_bits.py 1200 150 12
"""
from __future__ import annotations

import json
import math
import pickle
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_roles as tr  # noqa: E402
from openbooks_lab.bitenc import BITS, BitRoleNet, gather_head_bits, head_index, token_bits  # noqa: E402
from openbooks_lab.calibration_fit import fit_calibrator  # noqa: E402
from openbooks.statements.calibration import Calibrator  # noqa: E402
from openbooks.statements.encoder import n_params, row_features, windows  # noqa: E402
from openbooks.statements.roles import VTYPES  # noqa: E402
from openbooks_lab.synth import ROLES  # noqa: E402

ROOT = tr.ROOT
_items_of = tr.items_of


def items_with_bits(pages, cells) -> list[dict]:
    items = _items_of(pages, cells)
    texts = [[pg[i].text for i in idx] for pg in pages if pg for idx in windows(pg)]
    assert len(items) == len(texts)
    for it, t in zip(items, texts):
        money = [x == tr.TID["money"] for x in it["t"]]
        it["B"], it["HI"], it["R"] = token_bits(t), head_index(it["b"], money), row_features(it["b"], money)
    return items


def collate(items: list[dict], dev):
    b, n = len(items), max(len(i["w"]) for i in items)
    B = torch.zeros(b, n, BITS)
    S, X, R, HI = (torch.zeros(b, n, *s, dtype=torch.long) for s in ((), (4,), (2,), (3,)))
    Y, T = torch.full((b, n), -100), torch.full((b, n), -100)
    pad = torch.ones(b, n, dtype=torch.bool)
    for k, it in enumerate(items):
        m = len(it["w"])
        B[k, :m], S[k, :m], X[k, :m] = torch.from_numpy(it["B"]).float(), torch.tensor(it["s"]), torch.tensor(it["b"])
        R[k, :m], HI[k, :m] = torch.tensor(it["R"]), torch.tensor(it["HI"])
        Y[k, :m], T[k, :m], pad[k, :m] = torch.tensor(it["y"]), torch.tensor(it["t"]), False
    B, S, X, pad, R, HI, Y, T = (t.to(dev) for t in (B, S, X, pad, R, HI, Y, T))
    return B, S, X, pad, R, gather_head_bits(B, HI), Y, T


@torch.no_grad()
def logits_of(net, items, dev, bs=16):
    net.eval()
    ro, ty, yr, yt, loss, cnt = [], [], [], [], 0.0, 0
    for i in range(0, len(items), bs):
        B, S, X, pad, R, HB, Y, T = collate(items[i:i + bs], dev)
        with torch.autocast("cuda", dtype=torch.float16, enabled=dev.type == "cuda"):
            r, t = net(B, S, X, pad, R, HB)
        loss += float(tr.task_loss(r, Y) + 0.5 * tr.task_loss(t, T)) * len(Y)
        cnt += len(Y)
        keep = ~pad
        ro.append(r.float()[keep].cpu().numpy())
        ty.append(t.float()[keep].cpu().numpy())
        yr.append(Y[keep].cpu().numpy())
        yt.append(T[keep].cpu().numpy())
    return (np.concatenate(ro), np.concatenate(ty), np.concatenate(yr), np.concatenate(yt)), loss / max(cnt, 1)


def train(train_items, calib_items, dev, epochs: int, seed: int):
    torch.manual_seed(seed)
    net = BitRoleNet(len(ROLES), len(VTYPES)).to(dev)
    opt = torch.optim.AdamW([{"params": net.enc.parameters(), "lr": 3e-4},
                             {"params": list(net.role.parameters()) + list(net.vtype.parameters()), "lr": 1e-3}], weight_decay=0.01)
    base = [g["lr"] for g in opt.param_groups]
    scaler = torch.amp.GradScaler("cuda", enabled=dev.type == "cuda")
    rng, bs, step = random.Random(seed), 16, 0
    total, curve = epochs * math.ceil(len(train_items) / bs), []
    for ep in range(epochs):
        net.train()
        order = list(range(len(train_items)))
        rng.shuffle(order)
        run, hit, seen = 0.0, 0, 0
        for i in range(0, len(order), bs):
            B, S, X, pad, R, HB, Y, T = collate([train_items[j] for j in order[i:i + bs]], dev)
            scale = min(1.0, (step + 1) / 50) * 0.5 * (1 + math.cos(math.pi * step / total))
            for g, b0 in zip(opt.param_groups, base):
                g["lr"] = b0 * scale
            with torch.autocast("cuda", dtype=torch.float16, enabled=dev.type == "cuda"):
                r, t = net(B, S, X, pad, R, HB)
            loss = tr.task_loss(r, Y) + 0.5 * tr.task_loss(t, T)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            run += float(loss)
            keep = Y != -100
            hit += int((r.argmax(-1)[keep] == Y[keep]).sum())
            seen += int(keep.sum())
            step += 1
        _, cal_loss = logits_of(net, calib_items, dev)
        curve.append({"epoch": ep + 1, "train_loss": round(run / math.ceil(len(order) / bs), 4),
                      "train_exact_memorisation": round(hit / max(seen, 1), 4), "calib_loss": round(cal_loss, 4)})
        print(" ", curve[-1], flush=True)
    return net, curve


def main() -> None:
    n_tr, n_oc, epochs = (int(a) for a in (sys.argv[1:4] if len(sys.argv) > 3 else (1200, 150, 12)))
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()
    data = ROOT / "data" / f"roles_dataset_bits_{n_tr}_{n_oc}.pkl"
    if data.exists():
        splits = pickle.loads(data.read_bytes())
    else:
        tr.items_of = items_with_bits
        scale = lambda n: max(1, n // 10)  # noqa: E731
        splits = {"train": tr.make_split(0, n_tr, n_oc), "calib": tr.make_split(10_000, scale(n_tr) * 2, scale(n_oc) * 5),
                  "test": tr.make_split(20_000, scale(n_tr) * 2, scale(n_oc) * 4),
                  "shifted": tr.make_split(30_000, scale(n_tr), scale(n_oc) * 3, shifted=True)}
        data.write_bytes(pickle.dumps(splits))
    print({k: len(v) for k, v in splits.items()}, f"windows, ready in {time.time() - t0:.0f}s", flush=True)
    net, curve = train(splits["train"], splits["calib"], dev, epochs, seed=1)
    cl, _ = logits_of(net, splits["calib"], dev)
    cal_r, cal_t = fit_calibrator(cl[0], cl[2], tr.ALPHA), fit_calibrator(cl[1], cl[3], tr.ALPHA)
    res = {"calibration": {"role_temperature": round(cal_r.temperature, 3), "role_qhat": cal_r.qhat, "alpha": tr.ALPHA}}
    for name in ("calib", "test", "shifted"):
        lg = cl if name == "calib" else logits_of(net, splits[name], dev)[0]
        res[name] = tr.report(lg[0], lg[1], lg[2], lg[3], cal_r, cal_t)
        print(name, json.dumps(res[name]), flush=True)
    out = {"variant": "bit-level token input (first 12 bytes + end-of-token bit, MLP); hashed word table removed", "fp32": res,
           "parameters": n_params(net), "epochs": epochs, "loss": tr.LOSS, "epoch_curve": curve, "seconds": round(time.time() - t0),
           "note": "experiment, fp32, same seeds/splits/loss/schedule as the shipped model; not integrated into roles.py"}
    (ROOT / "docs" / "evidence" / "roles_metrics_bits.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"done: {n_params(net) / 1e6:.2f}M params, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
