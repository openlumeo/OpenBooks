"""Calibration and abstention for the typed heads at inference: temperature-scaled probabilities and split-conformal sets.

A token is only trusted when its conformal set holds exactly one class. Anything else abstains, which the pipeline reports
as LOW_CONFIDENCE. Coverage (the true class is in the set) is guaranteed at 1 - alpha only if calibration and test data are
exchangeable; on layouts unlike the calibration set it can fail. The numbers (temperature, qhat, alpha) ship in
roles_calibration.json, bound to the exact weights by hash. Fitting them is not part of this package.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


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

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"temperature": self.temperature, "qhat": None if math.isinf(self.qhat) else self.qhat,
                                    "alpha": self.alpha}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Calibrator":
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d["temperature"], float("inf") if d["qhat"] is None else d["qhat"], d["alpha"])
