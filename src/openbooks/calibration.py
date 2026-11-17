"""Calibration and abstention for the typed heads: temperature scaling plus split-conformal prediction sets.

A token is only trusted when its conformal set holds exactly one class. Anything else abstains, which the
pipeline reports as LOW_CONFIDENCE. Coverage (the true class is in the set) is guaranteed at 1 - alpha only if
calibration and test data are exchangeable; on layouts unlike the calibration set it can fail, so the abstain
rate and coverage are measured on held-out layouts in docs/evidence/roles_metrics.json.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


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


def prediction_set(probs: np.ndarray, qhat: float) -> list[int]:
    return [i for i, p in enumerate(probs) if 1.0 - p <= qhat]


@dataclass(frozen=True)
class Calibrator:
    temperature: float = 1.0
    qhat: float = float("inf")
    alpha: float = 0.05

    def probs(self, logits: np.ndarray) -> np.ndarray:
        return softmax(np.asarray(logits, dtype=np.float64) / self.temperature)

    def sets(self, logits: np.ndarray) -> list[list[int]]:
        return [prediction_set(p, self.qhat) for p in self.probs(logits)]

    @classmethod
    def fit(cls, logits: np.ndarray, labels: np.ndarray, alpha: float = 0.05, *, holdout: float = 0.5, seed: int = 0):
        """Temperature on one part of the calibration data, conformal quantile on the other (they must not overlap)."""
        idx = np.random.default_rng(seed).permutation(len(labels))
        cut = int(len(idx) * holdout)
        a, b = idx[:cut], idx[cut:]
        t = fit_temperature(logits[a], labels[a])
        probs = softmax(logits[b] / t)
        return cls(t, conformal_threshold(probs, labels[b], alpha), alpha)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"temperature": self.temperature, "qhat": None if math.isinf(self.qhat) else self.qhat,
                                    "alpha": self.alpha}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Calibrator":
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d["temperature"], float("inf") if d["qhat"] is None else d["qhat"], d["alpha"])
