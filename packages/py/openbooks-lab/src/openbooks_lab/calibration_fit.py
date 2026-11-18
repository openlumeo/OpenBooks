"""Fitting the calibration (private): temperature scaling on one part of the calibration data and a split-conformal quantile
on the other. The shipped statements package only evaluates a Calibrator; it never fits one."""
from __future__ import annotations

import math

import numpy as np
from openbooks_statements.calibration import Calibrator, softmax
from scipy.optimize import minimize_scalar


def nll(logits: np.ndarray, labels: np.ndarray, temperature: float) -> float:
    p = softmax(logits / temperature)
    return float(-np.log(np.clip(p[np.arange(len(labels)), labels], 1e-12, None)).mean())


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    res = minimize_scalar(lambda lt: nll(logits, labels, math.exp(lt)), bounds=(-3.0, 3.0), method="bounded")
    return float(math.exp(res.x))


def ece(probs: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    conf, pred = probs.max(axis=1), probs.argmax(axis=1)
    edges, total = np.linspace(0, 1, bins + 1), 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs((pred[m] == labels[m]).mean() - conf[m].mean())
    return float(total)


def conformal_threshold(probs: np.ndarray, labels: np.ndarray, alpha: float) -> float:
    """Split-conformal quantile of the score 1 - p(true class). inf (keep every class) if too few samples."""
    n = len(labels)
    scores = np.sort(1.0 - probs[np.arange(n), labels])
    k = math.ceil((n + 1) * (1 - alpha))
    return float("inf") if k > n else float(scores[k - 1])


def fit_calibrator(logits: np.ndarray, labels: np.ndarray, alpha: float = 0.05, *, holdout: float = 0.5, seed: int = 0) -> Calibrator:
    """Temperature on one part of the calibration data, conformal quantile on the other (they must not overlap)."""
    idx = np.random.default_rng(seed).permutation(len(labels))
    cut = int(len(idx) * holdout)
    a, b = idx[:cut], idx[cut:]
    t = fit_temperature(logits[a], labels[a])
    probs = softmax(logits[b] / t)
    return Calibrator(t, conformal_threshold(probs, labels[b], alpha), alpha)
