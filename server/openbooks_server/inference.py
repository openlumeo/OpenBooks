"""Model-only inference for the typed role heads: what the web app asks for when it wants the model's own reading.

/v1/runs already runs the heads inside process() as a cross-check. This is the same model served directly: warm-loaded,
serialised on the one GPU, and batched across pages (RoleModel.logits runs one window at a time, which re-reads the
weights once per page; see docs/PROFILE_ROLES.md). Input is one PDF or scan. Output is, per word, the calibrated role
and value type, the conformal sets, and `abstained` (the set is not exactly one role).

The heads are a cross-check only. Nothing returned here can release a document.
"""
from __future__ import annotations

import copy
import os
import threading
import time
from pathlib import Path

import numpy as np
import torch
from openbooks.core.errors import Refusal
from openbooks.core.gates import require_balance, run_gate
from openbooks.core.params import Params
from openbooks.statements.encoder import NOT_MONEY, tensors, windows
from openbooks.statements.labels import ROLES, VTYPES
from openbooks.statements.pdf_front import extract_statement, read_words
from openbooks.statements.roles import Predictions, RoleModel

MAX_BATCH_TOKENS = 4096
ONNX_ENV = "OPENBOOKS_ONNX_MODEL"
ONNX_FILL = (0, 0, 0, True, None, 0)

_GPU = threading.Lock()
_ONNX_LOCK = threading.Lock()
_ONNX_CACHE: dict[str, "OnnxNet"] = {}


class OnnxNet:
    def __init__(self, path: Path):
        import onnxruntime as ort
        from openbooks.statements.encoder import MAXLEN

        self.maxlen = MAXLEN
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    def _padded(self, window: tuple, tokens: int) -> dict:
        feed = {}
        for name, tensor, fill in zip(("W", "S", "X", "pad", "R", "H"), window, ONNX_FILL):
            tensor = tensor.cpu()
            shape = (1, self.maxlen - tokens, *tensor.shape[2:])
            if fill is None:
                extra = torch.zeros(shape, dtype=tensor.dtype)
                extra[..., 0] = NOT_MONEY
            else:
                extra = torch.full(shape, fill, dtype=tensor.dtype)
            feed[name] = torch.cat([tensor, extra], dim=1).numpy()
        return feed

    def __call__(self, *batch):
        total, tokens = batch[0].shape[0], batch[0].shape[1]
        roles, types = [], []
        for row in range(total):
            window = tuple(tensor[row:row + 1] for tensor in batch)
            role, vtype = self.session.run(["role_logits", "type_logits"], self._padded(window, tokens))
            roles.append(torch.from_numpy(role[:, :tokens]))
            types.append(torch.from_numpy(vtype[:, :tokens]))
        return torch.cat(roles, 0), torch.cat(types, 0)


def onnx_model(model: RoleModel) -> RoleModel:
    path = os.environ.get(ONNX_ENV)
    if not path:
        return model
    with _ONNX_LOCK:
        net = _ONNX_CACHE.get(path)
        if net is None:
            net = _ONNX_CACHE[path] = OnnxNet(Path(path))
    served = copy.copy(model)
    served.net, served.dev = net, torch.device("cpu")
    return served


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
                if fill is None:
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
    order = sorted(range(len(wins)), key=lambda k: len(wins[k]))
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


def _layout_roles(pages, params: Params, method: str) -> tuple[dict, str | None]:
    try:
        data, _, assigned, _ = extract_statement(pages, params, method)
        require_balance(run_gate(data))
    except Refusal as refusal:
        return {}, refusal.code
    return dict(assigned), None


def _page_json(page_no: int, words, preds: Predictions, layout_roles: dict) -> dict:
    pw, ph = words[0].pw, words[0].ph
    tokens = []
    for w in words:
        p = preds.table[w]
        tokens.append({
            "text": w.text,
            **({"ocr_text": w.orig} if w.orig is not None else {}),
            "ocr_confidence": w.conf,
            "box": [round(w.x0 / pw, 4), round(w.y0 / ph, 4), round(w.x1 / pw, 4), round(w.y1 / ph, 4)],
            "role": p.role, "role_set": list(p.role_set),
            "vtype": p.vtype, "type_set": list(p.type_set),
            "abstained": len(p.role_set) != 1,
            **({"layout_role": layout_roles[w]} if w in layout_roles else {}),
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
    layout_roles, layout_refusal = _layout_roles(pages, params, method)
    out_pages = [_page_json(pg[0].page, pg, preds, layout_roles) for pg in pages if pg]
    toks = [t for pg in out_pages for t in pg["tokens"]]
    by_role: dict[str, int] = {}
    for t in toks:
        by_role[t["role"]] = by_role.get(t["role"], 0) + 1
    n = len(toks)
    abstained = sum(t["abstained"] for t in toks)
    supported = sum("layout_role" in t for t in toks)
    resolved = sum(t["abstained"] and "layout_role" in t for t in toks)
    if timings is not None:
        timings["serialization"] = time.perf_counter() - t_ser
    return {
        "schema_version": "openbooks.roles.v1",
        "method": method,
        "layout": {"supported": supported, "resolved_abstentions": resolved, "refusal": layout_refusal},
        "pages": out_pages,
        "summary": {
            "tokens": n,
            "abstained": abstained,
            "abstain_rate": round(abstained / n, 4) if n else 0.0,
            "by_role": by_role,
            "inference_ms": round(ms, 1),
            "device": str(model.dev),
        },
        "model": model.identity,
    }
