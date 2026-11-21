"""Environment readers for the operational knobs (OPENBOOKS_* variables)."""
from __future__ import annotations

import os


def env_number(name: str, default: float) -> float:
    """Return the variable as a float; unset, empty or non-numeric values fall back to default."""
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)
