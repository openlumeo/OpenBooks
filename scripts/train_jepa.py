"""JEPA-style masked layout pretraining + BIO fine-tune on a single 6 GB NVIDIA GPU.

Real data only: FUNSD + CORD (train/validation splits). Public test splits are never
trained on. Reports a from-scratch baseline next to the pretrained run, so the effect
of pretraining is measured, not assumed.

Usage: python scripts/train_jepa.py [--smoke] [--steps 8000] [--ft-epochs 40]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import re
import time
import zlib
from pathlib import Path

import pyarrow.parquet as pq
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
NB, NS, MAXLEN, D, N_TAGS = 32768, 512, 512, 512, 7
LAYERS, HEADS = 10, 8
MASK_ID = 1
CKPT = ROOT / "models" / "pretrain_ckpt.pt"


def h_word(w: str) -> int:
    return zlib.crc32(w.lower().encode()) % (NB - 2) + 2


def h_shape(w: str) -> int:
    s = "".join("d" if c.isdigit() else "A" if c.isupper() else "a" if c.isalpha() else c for c in w)
    return zlib.crc32((re.sub(r"(.)\1+", r"\1", s) + str(min(len(w), 12))).encode()) % (NS - 1) + 1


def make_docs(words, boxes, tags=None) -> list[dict]:
    """Split one page into windows of MAXLEN tokens (no truncation, so nothing is dropped)."""
    out = []
    for i in range(0, len(words), MAXLEN):
        ws = words[i:i + MAXLEN]
        out.append({"w": [h_word(w) for w in ws], "s": [h_shape(w) for w in ws],
                    "b": [[min(1000, max(0, int(v))) for v in b] for b in boxes[i:i + MAXLEN]],
                    "y": None if tags is None else list(tags[i:i + MAXLEN])})
    return out


def load_funsd(split: str) -> list[dict]:
    t = pq.read_table(RAW / "funsd" / "data" / f"{split}-00000-of-00001.parquet", columns=["words", "bboxes", "ner_tags"])
    docs = []
    for r in t.to_pylist():
        docs += make_docs(r["words"], r["bboxes"], r["ner_tags"])
    return docs


def load_cord(splits: tuple[str, ...]) -> list[dict]:
    docs = []
    for split in splits:
        for f in sorted((RAW / "cord_v2" / "data").glob(f"{split}-*.parquet")):
            for r in pq.read_table(f, columns=["ground_truth"]).to_pylist():
                gt = json.loads(r["ground_truth"])
                W, H = gt["meta"]["image_size"]["width"], gt["meta"]["image_size"]["height"]
                words, boxes = [], []
                for line in gt["valid_line"]:
                    for wd in line["words"]:
                        q = wd["quad"]
                        xs, ys = [q["x1"], q["x2"], q["x3"], q["x4"]], [q["y1"], q["y2"], q["y3"], q["y4"]]
                        if wd["text"].strip():
                            words.append(wd["text"])
                            boxes.append([min(xs) * 1000 / W, min(ys) * 1000 / H, max(xs) * 1000 / W, max(ys) * 1000 / H])
                if words:
                    docs += make_docs(words, boxes)
    return docs


def make_mask(boxes: list[list[int]], rng: random.Random) -> list[bool]:
    """Mask 1-3 rectangular regions (row-like: wide and short), as in table rows and field boxes."""
    n = len(boxes)
    cx = [(b[0] + b[2]) / 2 for b in boxes]
    cy = [(b[1] + b[3]) / 2 for b in boxes]
    m = [False] * n
    for _ in range(rng.randint(1, 3)):
        a, w, h = rng.randrange(n), rng.uniform(0.2, 0.6) * 1000, rng.uniform(0.05, 0.25) * 1000
        for i in range(n):
            if abs(cx[i] - cx[a]) <= w / 2 and abs(cy[i] - cy[a]) <= h / 2:
                m[i] = True
    idx = [i for i, v in enumerate(m) if v]
    if len(idx) > 0.6 * n:
        keep = set(rng.sample(idx, max(1, int(0.6 * n))))
        m = [i in keep for i in range(n)]
    if not any(m):
        m[rng.randrange(n)] = True
    return m


def collate(docs: list[dict], dev, rng: random.Random | None = None):
    B, n = len(docs), max(len(d["w"]) for d in docs)
    W = torch.zeros(B, n, dtype=torch.long)
    S = torch.zeros(B, n, dtype=torch.long)
    X = torch.zeros(B, n, 4, dtype=torch.long)
    Y = torch.full((B, n), -100, dtype=torch.long)
    M = torch.zeros(B, n, dtype=torch.bool)
    pad = torch.ones(B, n, dtype=torch.bool)
    for i, d in enumerate(docs):
        k = len(d["w"])
        W[i, :k], S[i, :k], X[i, :k], pad[i, :k] = (torch.tensor(d["w"]), torch.tensor(d["s"]),
                                                   torch.tensor(d["b"]), False)
        if d["y"] is not None:
            Y[i, :k] = torch.tensor(d["y"])
        if rng is not None:
            M[i, :k] = torch.tensor(make_mask(d["b"], rng))
    return [t.to(dev) for t in (W, S, X, Y, M, pad)]


class Enc(nn.Module):
    """Token + shape + 2D box embeddings (LayoutLM-style), LAYERS x width D transformer."""

    def __init__(self, d: int = D, layers: int = LAYERS, heads: int = HEADS):
        super().__init__()
        self.word, self.shape = nn.Embedding(NB, d, padding_idx=0), nn.Embedding(NS, d, padding_idx=0)
        self.xe, self.ye, self.we, self.he = (nn.Embedding(1001, d) for _ in range(4))
        self.pos = nn.Embedding(MAXLEN, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, 0.1, activation="gelu", batch_first=True, norm_first=True)
        self.tf = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d)

    def forward(self, W, S, X, pad):
        pos = torch.arange(W.shape[1], device=W.device)
        wd, ht = (X[..., 2] - X[..., 0]).clamp(0, 1000), (X[..., 3] - X[..., 1]).clamp(0, 1000)
        x = (self.word(W) + self.shape(S) + self.xe(X[..., 0]) + self.xe(X[..., 2]) + self.ye(X[..., 1])
             + self.ye(X[..., 3]) + self.we(wd) + self.he(ht) + self.pos(pos))
        return self.norm(self.tf(x, src_key_padding_mask=pad))


class Predictor(nn.Module):
    def __init__(self, d: int = D, pd: int = 128):
        super().__init__()
        self.inp, self.out = nn.Linear(d, pd), nn.Linear(pd, d)
        layer = nn.TransformerEncoderLayer(pd, 4, 4 * pd, 0.0, activation="gelu", batch_first=True, norm_first=True)
        self.tf = nn.TransformerEncoder(layer, 2, enable_nested_tensor=False)

    def forward(self, h, pad):
        return self.out(self.tf(self.inp(h), src_key_padding_mask=pad))


def n_params(*ms) -> int:
    return sum(p.numel() for m in ms for p in m.parameters())


def cosine_lr(step: int, total: int, base: float, warm: int = 300) -> float:
    return base * (step + 1) / warm if step < warm else base * 0.5 * (1 + math.cos(math.pi * (step - warm) / max(1, total - warm)))


def vicreg_reg(h: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    h = h.float()
    var = F.relu(1 - torch.sqrt(h.var(0) + 1e-4)).mean()
    hc = h - h.mean(0)
    cov = (hc.T @ hc) / (len(h) - 1)
    return var, (cov.pow(2).sum() - cov.diagonal().pow(2).sum()) / h.shape[1]


def pretrain(docs, steps, bs, dev, seed):
    rng = random.Random(seed)
    stu, pred = Enc().to(dev), Predictor().to(dev)
    tgt = copy.deepcopy(stu).eval()
    for p in tgt.parameters():
        p.requires_grad = False
    opt = torch.optim.AdamW(list(stu.parameters()) + list(pred.parameters()), lr=5e-4, weight_decay=0.05)
    scaler = torch.amp.GradScaler("cuda")
    log, t0, start = [], time.time(), 0
    if steps >= 1000 and CKPT.exists():
        c = torch.load(CKPT, map_location=dev)
        for obj, key in ((stu, "stu"), (tgt, "tgt"), (pred, "pred"), (opt, "opt"), (scaler, "scaler")):
            obj.load_state_dict(c[key])
        start, log = c["step"], c["log"]
        print(f"resumed at step {start}", flush=True)
    for step in range(start, steps):
        rng = random.Random(seed * 1_000_003 + step)
        for g in opt.param_groups:
            g["lr"] = cosine_lr(step, steps, 5e-4)
        W, S, X, _, M, pad = collate(rng.sample(docs, bs), dev, rng)
        with torch.autocast("cuda", dtype=torch.float16):
            h = stu(W.masked_fill(M, MASK_ID), S.masked_fill(M, 0), X, pad)
            with torch.no_grad():
                t = F.layer_norm(tgt(W, S, X, pad).float(), (D,))
            p = pred(h, pad).float()
        valid = ~pad
        l_jepa = F.smooth_l1_loss(p[M], t[M])
        l_var, l_cov = vicreg_reg(h[valid])
        loss = l_jepa + 1.0 * l_var + 0.1 * l_cov
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(stu.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        with torch.no_grad():
            for pt, ps in zip(tgt.parameters(), stu.parameters()):
                pt.mul_(0.996).add_(ps.detach(), alpha=0.004)
        if step % 200 == 0 or step == steps - 1:
            row = {"step": step, "loss": round(loss.item(), 4), "jepa": round(l_jepa.item(), 4),
                   "var": round(l_var.item(), 4), "target_std": round(t[valid].std(0).mean().item(), 4),
                   "sec": round(time.time() - t0)}
            log.append(row)
            print(row, flush=True)
        if steps >= 1000 and step % 1000 == 999 and step + 1 < steps:
            CKPT.parent.mkdir(exist_ok=True)
            torch.save({"stu": stu.state_dict(), "tgt": tgt.state_dict(), "pred": pred.state_dict(),
                        "opt": opt.state_dict(), "scaler": scaler.state_dict(), "step": step + 1, "log": log}, CKPT)
    CKPT.unlink(missing_ok=True)
    return stu, log, n_params(stu, pred)


def f1_nonO(pred, y) -> dict:
    ok = y != -100
    pred, y = pred[ok], y[ok]
    tp = ((pred == y) & (y > 0)).sum().item()
    fp = ((pred > 0) & (pred != y)).sum().item()
    fn = ((y > 0) & (pred != y)).sum().item()
    return {"token_f1_non_O": round(2 * tp / max(1, 2 * tp + fp + fn), 4), "token_acc": round((pred == y).float().mean().item(), 4)}


def finetune(init, train, test, epochs, dev, seed, bs=8):
    torch.manual_seed(seed)
    rng = random.Random(seed)
    enc, head = Enc().to(dev), nn.Linear(D, N_TAGS).to(dev)
    if init is not None:
        enc.load_state_dict(init)
    opt = torch.optim.AdamW([{"params": enc.parameters(), "lr": 1e-4}, {"params": head.parameters(), "lr": 1e-3}], weight_decay=0.01)
    steps = epochs * math.ceil(len(train) / bs)
    k = 0
    for _ in range(epochs):
        idx = list(range(len(train)))
        rng.shuffle(idx)
        enc.train()
        for i in range(0, len(idx), bs):
            W, S, X, Y, _, pad = collate([train[j] for j in idx[i:i + bs]], dev)
            for g, base in zip(opt.param_groups, (1e-4, 1e-3)):
                g["lr"] = cosine_lr(k, steps, base, warm=20)
            loss = F.cross_entropy(head(enc(W, S, X, pad)).reshape(-1, N_TAGS), Y.reshape(-1), ignore_index=-100)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            k += 1
    enc.eval()
    preds, ys = [], []
    with torch.no_grad():
        for i in range(0, len(test), bs):
            W, S, X, Y, _, pad = collate(test[i:i + bs], dev)
            preds.append(head(enc(W, S, X, pad)).argmax(-1).flatten())
            ys.append(Y.flatten())
    return f1_nonO(torch.cat(preds), torch.cat(ys))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=8000)
    ap.add_argument("--ft-epochs", type=int, default=40)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        a.steps, a.ft_epochs = 30, 2
    assert torch.cuda.is_available(), "NVIDIA GPU not visible to torch"
    dev = torch.device("cuda")
    random.seed(a.seed)
    torch.manual_seed(a.seed)
    funsd_tr, funsd_te = load_funsd("train"), load_funsd("test")
    cord = load_cord(("train", "validation"))
    corpus = funsd_tr + cord
    print(f"windows: funsd_train={len(funsd_tr)} funsd_test={len(funsd_te)} cord_train+val={len(cord)}", flush=True)
    enc, log, n_par = pretrain(corpus, a.steps, a.bs, dev, a.seed)
    res = {"gpu": torch.cuda.get_device_name(0), "params_pretrain_total": n_par, "params_encoder": n_params(enc),
           "pretrain_steps": a.steps, "pretrain_log": log,
           "corpus_windows": len(corpus), "finetune": {"train": len(funsd_tr), "test": len(funsd_te)}}
    res["funsd_pretrained"] = finetune({k: v.cpu() for k, v in enc.state_dict().items()}, funsd_tr, funsd_te, a.ft_epochs, dev, a.seed)
    res["funsd_scratch"] = finetune(None, funsd_tr, funsd_te, a.ft_epochs, dev, a.seed)
    print(json.dumps({k: res[k] for k in ("params_encoder", "funsd_pretrained", "funsd_scratch")}, indent=2), flush=True)
    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "docs" / "evidence").mkdir(parents=True, exist_ok=True)
    if not a.smoke:
        torch.save(enc.state_dict(), ROOT / "models" / "jepa_encoder.pt")
    (ROOT / "docs" / "evidence" / ("train_metrics_smoke.json" if a.smoke else "train_metrics.json")).write_text(
        json.dumps(res, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
