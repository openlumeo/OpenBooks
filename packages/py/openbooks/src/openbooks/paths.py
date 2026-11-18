"""Where the model assets are. Interim: until openbooks-statements ships them as package data, they are found next to the
source checkout (repo/models) or in the directory named by OPENBOOKS_MODELS_DIR. An installed wheel has no models."""
from __future__ import annotations

import os
from pathlib import Path


def models_dir() -> Path:
    env = os.environ.get("OPENBOOKS_MODELS_DIR")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if (parent / "models" / "roles_manifest.json").exists():
            return parent / "models"
    return Path(__file__).resolve().parent / "models"  # absent; load() reports "no weights"


MODELS_DIR = models_dir()
