"""Layout encoder shared by the typed heads: hashed word and shape embeddings plus 2D box embeddings.

Release-one size: about 19M parameters (budget 25M, target ~20M; int8 at rest is about 1 MB per million). Trained from
scratch on synthetic statements only. The 50M encoder from scripts/train_jepa.py was pretrained on CORD (CC BY-SA), is
internal-only, and is deliberately NOT loadable here.
"""
from __future__ import annotations

import re
import zlib

import torch
from torch import nn

NB, NS, MAXLEN, D, LAYERS, HEADS = 16384, 512, 512, 384, 6, 6
MONEY = re.compile(r"^\(?-?\d[\d,]*\.\d{2}\)?(?:Dr|Cr|DR|CR)?$")
NOT_MONEY, MAX_RANK, MAX_N = 5, 4, 6


def column_heads(boxes: list[list[int]], hashes: list[int], money: list[bool]) -> list[list[int]]:
    """For each amount token, the hashed words (up to 3) of the nearest non-amount line above it in the same x-range.

    On a statement that is the column header ('Withdrawal Amt.', 'Credit'); the model learns what those words mean. Nothing
    here knows any header vocabulary, so a new header wording is just a new hash, not a rule to maintain.
    """
    import numpy as np

    heads = [[0, 0, 0] for _ in boxes]
    if not any(money):
        return heads
    b, mon = np.asarray(boxes), np.asarray(money)
    for i in np.nonzero(mon)[0]:
        ok = ~mon & (np.minimum(b[:, 2], b[i, 2]) - np.maximum(b[:, 0], b[i, 0]) > 0) & (b[:, 3] <= b[i, 1])
        idx = np.nonzero(ok)[0]
        if not len(idx):
            continue
        near = idx[np.argmax(b[idx, 3])]
        h = max(4, b[near, 3] - b[near, 1])
        line = idx[np.abs((b[idx, 1] + b[idx, 3]) / 2 - (b[near, 1] + b[near, 3]) / 2) <= 0.6 * h]
        ids = [hashes[k] for k in line[np.argsort(b[line, 0])][:3]]
        heads[i] = ids + [0] * (3 - len(ids))
    return heads


def row_features(boxes: list[list[int]], money: list[bool]) -> list[list[int]]:
    """Per token (rank from the right among the amount tokens of its row, number of amounts in the row).

    A statement row reads description ... [debit] [credit] balance, so the balance is always rank 0. This is geometry plus
    the surface money test only: no header words and no rule-based column assignment, so it stays independent of the extractor.
    """
    feats = [[NOT_MONEY, 0] for _ in boxes]
    order = sorted((i for i, m in enumerate(money) if m), key=lambda i: boxes[i][1] + boxes[i][3])
    rows: list[list[int]] = []
    for i in order:
        cy, h = (boxes[i][1] + boxes[i][3]) / 2, max(4, boxes[i][3] - boxes[i][1])
        if rows and abs(cy - sum((boxes[k][1] + boxes[k][3]) / 2 for k in rows[-1]) / len(rows[-1])) <= 0.6 * h:
            rows[-1].append(i)
        else:
            rows.append([i])
    for row in rows:
        for rank, i in enumerate(sorted(row, key=lambda k: -boxes[k][2])):
            feats[i] = [min(rank, MAX_RANK), min(len(row), MAX_N)]
    return feats


def h_word(w: str) -> int:
    return zlib.crc32(w.lower().encode()) % (NB - 2) + 2


def h_shape(w: str) -> int:
    s = "".join("d" if c.isdigit() else "A" if c.isupper() else "a" if c.isalpha() else c for c in w)
    return zlib.crc32((re.sub(r"(.)\1+", r"\1", s) + str(min(len(w), 12))).encode()) % (NS - 1) + 1


class Enc(nn.Module):
    """Token + shape + 2D box embeddings (LayoutLM-style), LAYERS x width D transformer."""

    def __init__(self, d: int = D, layers: int = LAYERS, heads: int = HEADS):
        super().__init__()
        self.word, self.shape = nn.Embedding(NB, d, padding_idx=0), nn.Embedding(NS, d, padding_idx=0)
        self.xe, self.ye, self.we, self.he = (nn.Embedding(1001, d) for _ in range(4))
        self.pos = nn.Embedding(MAXLEN, d)
        self.rank, self.nmon = nn.Embedding(NOT_MONEY + 1, d), nn.Embedding(MAX_N + 1, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, 0.1, activation="gelu", batch_first=True, norm_first=True)
        self.tf = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d)

    def forward(self, W, S, X, pad, R, H):
        pos = torch.arange(W.shape[1], device=W.device)
        wd, ht = (X[..., 2] - X[..., 0]).clamp(0, 1000), (X[..., 3] - X[..., 1]).clamp(0, 1000)
        x = (self.word(W) + self.shape(S) + self.xe(X[..., 0]) + self.xe(X[..., 2]) + self.ye(X[..., 1])
             + self.ye(X[..., 3]) + self.we(wd) + self.he(ht) + self.pos(pos) + self.rank(R[..., 0]) + self.nmon(R[..., 1])
             + self.word(H).sum(2))
        return self.norm(self.tf(x, src_key_padding_mask=pad))


class RoleNet(nn.Module):
    """Encoder plus two typed heads: the column role of a token and the value type it holds."""

    def __init__(self, n_roles: int, n_types: int):
        super().__init__()
        self.enc = Enc()
        self.role, self.vtype = nn.Linear(D, n_roles), nn.Linear(D, n_types)

    def forward(self, W, S, X, pad, R, H):
        h = self.enc(W, S, X, pad, R, H)
        return self.role(h), self.vtype(h)


def windows(words) -> list[list[int]]:
    """Index windows of at most MAXLEN tokens per page, in reading order (page, y, x)."""
    out: list[list[int]] = []
    by_page: dict[int, list[int]] = {}
    for i, w in enumerate(words):
        by_page.setdefault(w.page, []).append(i)
    for idx in by_page.values():
        idx.sort(key=lambda i: (round(words[i].cy / 4), words[i].x0))
        out += [idx[k:k + MAXLEN] for k in range(0, len(idx), MAXLEN)]
    return out


def tensors(words, idx: list[int], dev):
    """Collate one window into (W, S, X, pad, R) batch-of-one tensors, boxes scaled to 0..1000 by page size."""
    ws = [words[i] for i in idx]
    clamp = lambda v: min(1000, max(0, int(v)))  # noqa: E731
    boxes = [[clamp(w.x0 * 1000 / w.pw), clamp(w.y0 * 1000 / w.ph), clamp(w.x1 * 1000 / w.pw), clamp(w.y1 * 1000 / w.ph)] for w in ws]
    W = torch.tensor([[h_word(w.text) for w in ws]], device=dev)
    S = torch.tensor([[h_shape(w.text) for w in ws]], device=dev)
    money = [bool(MONEY.match(w.text)) for w in ws]
    R = torch.tensor([row_features(boxes, money)], device=dev)
    H = torch.tensor([column_heads(boxes, [h_word(w.text) for w in ws], money)], device=dev)
    return W, S, torch.tensor([boxes], device=dev), torch.zeros(1, len(ws), dtype=torch.bool, device=dev), R, H


def n_params(net: nn.Module) -> int:
    return sum(p.numel() for p in net.parameters())


def quantize_state(state: dict, min_numel: int = 4096) -> dict:
    """int8 at rest: per-row symmetric scales for every large 2D weight (embeddings and linears), fp16 for the rest."""
    out = {}
    for k, v in state.items():
        if v.ndim == 2 and v.numel() >= min_numel:
            scale = (v.abs().amax(dim=1, keepdim=True) / 127).clamp(min=1e-8)
            out[k] = {"q": torch.round(v / scale).clamp(-127, 127).to(torch.int8), "s": scale.squeeze(1).half()}
        else:
            out[k] = v.half()
    return out


def dequantize_state(blob: dict) -> dict:
    return {k: (v["q"].float() * v["s"].float().unsqueeze(1) if isinstance(v, dict) else v.float()) for k, v in blob.items()}
