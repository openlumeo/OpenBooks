"""Typed heads for PDFs and scans: a calibrated column role and value type for every token, with abstention.

Two jobs, both optional (--model):
 1. cross-check: the rule-based extractor's column assignment must agree with the model's conformal sets, else
    LOW_CONFIDENCE. This can only add refusals.
 2. header-less fallback: when no header line is found the model assigns debit/credit/balance to amounts. A token
    whose conformal set is not exactly one role abstains. The balance gate still has the last word.
The weights ship in this distribution (data/roles_head.pt); without them the flag is refused, never ignored.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import threading
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import torch
from openbooks.core.errors import Refusal

from .calibration import Calibrator, prediction_set
from .encoder import RoleNet, dequantize_state, tensors, windows
from .assets import CALIBRATION_NAME, MODELS_DIR, WEIGHTS_NAME, ModelUnavailable
from .labels import ROLES, VTYPES

WEIGHTS, CALIBRATION = MODELS_DIR / WEIGHTS_NAME, MODELS_DIR / CALIBRATION_NAME
AMOUNT = ("debit", "credit", "balance")
_MONEY = re.compile(r"^\(?-?\d[\d,]*\.\d{2}\)?(?:Dr|Cr|DR|CR)?$")
_DATE = re.compile(r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4})$")


def vtype_of(text: str) -> str:
    """Surface value type of a token (the type-head label)."""
    if _DATE.match(text):
        return "date"
    if _MONEY.match(text):
        return "money"
    return "code" if re.fullmatch(r"\d{5,}", text) else "text"


@dataclass(frozen=True)
class Pred:
    role: str
    role_set: tuple[str, ...]
    vtype: str
    type_set: tuple[str, ...]


class Predictions:
    def __init__(self, table: dict):
        self.table = table
        self._pages: dict[int, list] = {}
        for w in table:
            self._pages.setdefault(w.page, []).append(w)

    def get(self, w) -> Pred | None:
        """Prediction for a word. A word the extractor built (a 'Rs.' prefix or 'Cr' suffix merged in, OCR digits rejoined)
        is not a model token: use the numeric tokens inside its box and only the roles they all allow."""
        p = self.table.get(w)
        if p is not None:
            return p
        inside = [self.table[t] for t in self._pages.get(w.page, ()) if w.x0 <= t.cx <= w.x1 and w.y0 <= t.cy <= w.y1]
        parts = [q for q in inside if "money" in q.type_set] or inside
        if not parts:
            return None
        allowed = tuple(r for r in parts[0].role_set if all(r in q.role_set for q in parts[1:]))
        types = tuple(t for t in parts[0].type_set if all(t in q.type_set for q in parts[1:]))
        return Pred(parts[0].role, allowed, parts[0].vtype, types)

    def resolve(self, tokens, prev, value) -> dict:
        """Amount role of every money token in one row. A token whose conformal set is one role keeps it. If any set is
        wider, enumerate the readings inside the sets and keep those with one balance, at most one amount, and
        prev +/- amount = balance (prev=None skips the chain). Exactly one survivor resolves the row; zero or several
        abstain (LOW_CONFIDENCE). The balance gate still checks the whole statement afterwards."""
        sets = [getattr(self.get(w), "role_set", ()) for w in tokens]
        cands = [tuple(r for r in s if r in AMOUNT) for s in sets]
        if all(len(c) == 1 for c in cands):
            return {w: c[0] for w, c in zip(tokens, cands)}
        keep = [a for a in product(*cands)
                if a.count("balance") == 1 and len(a) - 1 <= 1 and _ties(a, tokens, prev, value)]
        if len(keep) != 1:
            raise Refusal("LOW_CONFIDENCE", f"page {tokens[0].page}: the typed head is not sure which columns the amounts "
                                            f"are in ({len(keep)} readings tie the balance)")
        return dict(zip(tokens, keep[0]))


class RoleModel:
    def __init__(self, net: RoleNet, role_cal: Calibrator, type_cal: Calibrator, dev):
        self.net, self.role_cal, self.type_cal, self.dev = net.eval(), role_cal, type_cal, dev

    _load_lock = threading.Lock()
    _cache_key: tuple | None = None
    _cached_model: RoleModel | None = None
    _cached_issue: str | None = None

    @classmethod
    def load(cls, weights: Path = WEIGHTS, calibration: Path = CALIBRATION) -> RoleModel | None:
        """Reuse the loaded model while its assets are unchanged."""
        with cls._load_lock:
            try:
                st = weights.stat()
                cal_bytes = calibration.read_bytes()
            except FileNotFoundError:
                return None
            except OSError as e:
                raise ModelUnavailable(f"Cannot read model assets ({type(e).__name__}). Check OPENBOOKS_MODELS_DIR.") from e
            key = (weights, calibration, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, cal_bytes)
            if key != cls._cache_key:
                try:
                    model = cls._build(weights, cal_bytes)
                except ModelUnavailable as e:
                    model, issue = None, e.message
                except OSError as e:
                    # Files may change during a deployment. Try again on the next call.
                    raise ModelUnavailable(f"Cannot read model weights ({type(e).__name__}). Check OPENBOOKS_MODELS_DIR.") from e
                else:
                    issue = None
                cls._cache_key, cls._cached_model, cls._cached_issue = key, model, issue
            if cls._cached_issue is not None:
                raise ModelUnavailable(cls._cached_issue)
            return cls._cached_model

    @classmethod
    def _build(cls, weights: Path, cal_bytes: bytes) -> RoleModel:
        """The calibration is only valid for the weights it was fitted on, so it names them by sha256 and a mismatch
        refuses: a retrain with an old calibration (or the reverse) must never load silently."""
        try:
            cal = json.loads(cal_bytes)
            fitted = cal.get("weights_sha256")
            if not fitted:
                raise ModelUnavailable("Invalid model calibration: no weights hash. Restore roles_calibration.json for these weights.")
            if not isinstance(fitted, str) or not re.fullmatch(r"[0-9a-f]{64}", fitted):
                raise ValueError("invalid weights_sha256")
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as e:
            raise ModelUnavailable("Invalid model calibration. Restore roles_calibration.json for these weights.") from e
        # Hash and deserialize the same bytes so a replacement on disk cannot misidentify a loaded checkpoint.
        weights_bytes = weights.read_bytes()
        w_sha = hashlib.sha256(weights_bytes).hexdigest()
        if fitted != w_sha:
            raise ModelUnavailable(f"Model calibration was fitted for other weights ({fitted[:12]}, not {w_sha[:12]}). "
                                   "Restore the matching roles_calibration.json or refit the calibration for these weights.")
        try:
            role_cal = _calibrator(cal["role"])
            type_cal = _calibrator(cal["vtype"])
        except (KeyError, TypeError, ValueError, OverflowError) as e:
            raise ModelUnavailable("Invalid model calibration. Restore roles_calibration.json for these weights.") from e
        try:
            state = torch.load(io.BytesIO(weights_bytes), map_location="cpu", weights_only=True)["int8_state"]
            net = RoleNet(len(ROLES), len(VTYPES))
            net.load_state_dict(dequantize_state(state))
            dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = cls(net.to(dev), role_cal, type_cal, dev)
        except Exception as e:
            raise ModelUnavailable(f"Cannot load the model checkpoint ({type(e).__name__}). "
                                   "Check roles_head.pt and the PyTorch installation.") from e
        model.identity = {"weights_sha256": w_sha, "calibration_sha256": hashlib.sha256(cal_bytes).hexdigest()}
        return model

    @torch.no_grad()
    def logits(self, words) -> tuple[np.ndarray, np.ndarray]:
        role = np.zeros((len(words), len(ROLES)), dtype=np.float32)
        vt = np.zeros((len(words), len(VTYPES)), dtype=np.float32)
        for idx in windows(words):
            r, t = self.net(*tensors(words, idx, self.dev))
            role[idx], vt[idx] = r[0].float().cpu().numpy(), t[0].float().cpu().numpy()
        return role, vt

    def predict(self, pages) -> Predictions:
        words = [w for pg in pages for w in pg]
        if not words:
            return Predictions({})
        return self.predictions(words, *self.logits(words))

    def predictions(self, words, role: np.ndarray, vt: np.ndarray) -> Predictions:
        """Apply the shipped calibration to logits from either inference path."""
        if not np.isfinite(role).all() or not np.isfinite(vt).all():
            raise ModelUnavailable("Model inference produced invalid scores. Check the model checkpoint.")
        rp, tp = self.role_cal.probs(role), self.type_cal.probs(vt)
        if not np.isfinite(rp).all() or not np.isfinite(tp).all():
            raise ModelUnavailable("Model inference produced invalid probabilities. Check the model calibration.")
        rs = [prediction_set(p, self.role_cal.qhat) for p in rp]
        ts = [prediction_set(p, self.type_cal.qhat) for p in tp]
        return Predictions({w: Pred(ROLES[int(rp[i].argmax())], tuple(ROLES[k] for k in rs[i]), VTYPES[int(tp[i].argmax())],
                                    tuple(VTYPES[k] for k in ts[i])) for i, w in enumerate(words)})


def _calibrator(data: dict) -> Calibrator:
    temperature, qhat, alpha = data["temperature"], data["qhat"], data["alpha"]
    values = (temperature, alpha) if qhat is None else (temperature, alpha, qhat)
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError("calibration values must be finite numbers")
    if temperature <= 0 or not 0 < alpha < 1 or (qhat is not None and not 0 <= qhat <= 1):
        raise ValueError("calibration values are out of range")
    return Calibrator(temperature, float("inf") if qhat is None else qhat, alpha)


def _ties(roles, tokens, prev, value) -> bool:
    """Does this reading of one row continue the running balance? (credit adds, debit subtracts, no amount = unchanged)"""
    if prev is None:
        return True
    bal = value(tokens[roles.index("balance")])
    amts = [(r, t) for r, t in zip(roles, tokens) if r != "balance"]
    if not amts:
        return bal == prev
    r, t = amts[0]
    a = abs(value(t))
    return prev + (a if r == "credit" else -a) == bal


def crosscheck(assigned, preds: Predictions) -> None:
    """The rule-based column of every date and amount token must be inside the model's conformal set."""
    bad = 0
    for w, role in assigned:
        if role not in ("date", *AMOUNT):
            continue
        p = preds.get(w)
        if p is None or role not in p.role_set or (role in AMOUNT and "money" not in p.type_set):
            bad += 1
    if bad:
        raise Refusal("LOW_CONFIDENCE", f"the typed heads disagree with the extracted columns on {bad} tokens")
