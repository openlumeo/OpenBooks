"""Where the model assets are, with no torch import.

Order: the directory named by OPENBOOKS_MODELS_DIR, then the assets packaged inside this distribution (data/), then the
repo's models/ directory when running from a source checkout. The calibration is bound to the weights by sha256 and the
loader refuses a mismatch, so a stray or older file elsewhere can never be used silently."""
from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

WEIGHTS_NAME, CALIBRATION_NAME = "roles_head.pt", "roles_calibration.json"


def models_dir() -> Path:
    env = os.environ.get("OPENBOOKS_MODELS_DIR")
    if env:
        return Path(env)
    packaged = Path(str(resources.files("openbooks_statements").joinpath("data")))
    if (packaged / WEIGHTS_NAME).exists():
        return packaged
    for parent in Path(__file__).resolve().parents:
        if (parent / "models" / WEIGHTS_NAME).exists():
            return parent / "models"
    return packaged  # absent: load() reports that there are no weights


MODELS_DIR = models_dir()
