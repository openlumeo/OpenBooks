"""Model-only inference for the typed role heads: what the web app asks for when it wants the model's own reading.

/v1/runs already runs the heads inside process() as a cross-check. This is the same model served directly: warm-loaded,
serialised on the one GPU, and batched across pages (RoleModel.logits runs one window at a time, which re-reads the
weights once per page; see docs/PROFILE_ROLES.md). Input is one PDF or scan. Output is, per word, the calibrated role
and value type, the conformal sets, and `abstained` (the set is not exactly one role).

The heads are a cross-check only. Nothing returned here can release a document.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import torch
from openbooks.core.params import Params
from openbooks.statements.encoder import NOT_MONEY, tensors, windows
from openbooks.statements.labels import ROLES, VTYPES
from openbooks.statements.pdf_front import read_words
from openbooks.statements.roles import Predictions, RoleModel

MAX_BATCH_TOKENS = 4096  # padded tokens per forward; 8 full 512-token windows, ~50 MB of attention scores

# One GPU: one forward at a time. ponytail: a micro-batching queue across requests if concurrent load ever matters.
_GPU = threading.Lock()


def _pad(parts: list[tuple], dev) -> tuple:
    """Collate batch-of-one tensors (W,S,X,pad,R,H) of different lengths into one padded batch. Pads are masked."""
    n = max(p[0].shape[1] for p in parts)
    fills = (0, 0, 0, True, None, 0)
    out = []
    for i, fill in enumerate(fills):
        cols = []
        for p in parts:
            t, k = p[i], n - p[i].shape[1]
            if k:
                if fill is None:  # R: a pad token is "not money", in no row
                    tail = torch.tensor([NOT_MONEY, 0], device=dev).expand(1, k, 2)
                else:
                    tail = torch.full((1, k, *t.shape[2:]), fill, dtype=t.dtype, device=dev)
                t = torch.cat([t, tail], 1)
            cols.append(t)
        out.append(torch.cat(cols, 0))
    return tuple(out)


@torch.no_grad()
def logits_batched(model: RoleModel, words, max_tokens: int = MAX_BATCH_TOKENS) -> tuple[np.ndarray, np.ndarray]:
    """Same numbers as RoleModel.logits (pad tokens are masked), with the windows of a document batched together."""
    role = np.zeros((len(words), len(ROLES)), dtype=np.float32)
    vt = np.zeros((len(words), len(VTYPES)), dtype=np.float32)
    wins = windows(words)
    order = sorted(range(len(wins)), key=lambda k: len(wins[k]))  # similar lengths together = little padding
    i = 0
    while i < len(order):
        group = [order[i]]
        i += 1
        while i < len(order) and (len(group) + 1) * len(wins[order[i]]) <= max_tokens:
            group.append(order[i])
            i += 1
        batch = _pad([tensors(words, wins[k], model.dev) for k in group], model.dev)
        r, t = model.net(*batch)
        r, t = r.float().cpu().numpy(), t.float().cpu().numpy()
        for b, k in enumerate(group):
            n = len(wins[k])
            role[wins[k]], vt[wins[k]] = r[b, :n], t[b, :n]
    return role, vt


def predict_batched(model: RoleModel, pages, timings: dict | None = None) -> Predictions:
    """RoleModel.predict with batched windows. timings gets `model` (features + forward) and `calibration` seconds."""
    words = [w for pg in pages for w in pg]
    if not words:
        return Predictions({})
    t0 = time.perf_counter()
    logits = logits_batched(model, words)
    t1 = time.perf_counter()
    preds = model.predictions(words, *logits)
    if timings is not None:
        timings["model"], timings["calibration"] = t1 - t0, time.perf_counter() - t1
    return preds


def _page_json(page_no: int, words, preds: Predictions) -> dict:
    pw, ph = words[0].pw, words[0].ph
    tokens = []
    for w in words:
        p = preds.table[w]
        tokens.append({
            "text": w.text,
            **({"ocr_text": w.orig} if w.orig is not None else {}),
            "ocr_confidence": w.conf,
            "box": [round(w.x0 / pw, 4), round(w.y0 / ph, 4), round(w.x1 / pw, 4), round(w.y1 / ph, 4)],  # 0..1 of the page
            "role": p.role, "role_set": list(p.role_set),
            "vtype": p.vtype, "type_set": list(p.type_set),
            "abstained": len(p.role_set) != 1,
        })
    return {"page": page_no, "width": pw, "height": ph, "tokens": tokens}


def infer_file(path: Path, params: Params, model: RoleModel, timings: dict | None = None) -> dict:
    """Read one PDF or scan and return the loaded model's per-token reading.
    timings, if given, receives seconds for extract, model, calibration and serialization."""
    t_start = time.perf_counter()
    pages, method = read_words(path, params)
    t0 = time.perf_counter()
    if timings is not None:
        timings["extract"] = t0 - t_start
    with _GPU:
        preds = predict_batched(model, pages, timings)
        if model.dev.type == "cuda":
            torch.cuda.synchronize()
    ms = (time.perf_counter() - t0) * 1000
    t_ser = time.perf_counter()
    out_pages = [_page_json(pg[0].page, pg, preds) for pg in pages if pg]
    toks = [t for pg in out_pages for t in pg["tokens"]]
    by_role: dict[str, int] = {}
    for t in toks:
        by_role[t["role"]] = by_role.get(t["role"], 0) + 1
    n = len(toks)
    abstained = sum(t["abstained"] for t in toks)
    if timings is not None:
        timings["serialization"] = time.perf_counter() - t_ser
    return {
        "schema_version": "openbooks.roles.v1",
        "method": method,  # pdf_text | ocr
        "pages": out_pages,
        "summary": {
            "tokens": n,
            "abstained": abstained,
            "abstain_rate": round(abstained / n, 4) if n else 0.0,
            "by_role": by_role,
            "inference_ms": round(ms, 1),
            "device": str(model.dev),
        },
        "model": model.identity,  # weights_sha256 + calibration_sha256, same fields a --model release records
    }
