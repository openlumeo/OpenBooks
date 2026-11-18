"""Licence guard: the shipped typed heads are trained from scratch on our own synthetic statements only."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUDGET_PARAMS, BUDGET_MB = 25_000_000, 25


def test_training_script_uses_no_external_data_or_pretrained_weights():
    src = (ROOT / "scripts" / "train_roles.py").read_text(encoding="utf-8")
    for banned in (r"torch\.load\(", r"load_cord", r"load_funsd", r"load_sroie", r"/\s*['\"]raw['\"]", r"\.glob\([^)]*raw"):
        assert not re.search(banned, src, re.I), f"train_roles.py matches {banned!r}"


def test_encoder_does_not_load_the_cord_pretrained_checkpoint():
    src = (ROOT / "packages" / "py" / "openbooks" / "src" / "openbooks" / "encoder.py").read_text(encoding="utf-8")
    assert "torch.load" not in src
    code = [ln for ln in src.splitlines() if not ln.lstrip().startswith(("#", '"""'))]
    assert not any("jepa_encoder.pt" in ln for ln in code)


def test_manifest_declares_synthetic_only_and_fits_budget():
    path = ROOT / "models" / "roles_manifest.json"
    if not path.exists():
        pytest.skip("typed heads not trained yet")
    m = json.loads(path.read_text(encoding="utf-8"))
    assert m["training_data"]["files_read_from_data_raw"] == []
    assert m["training_data"]["origin"].startswith("SYNTHETIC only")
    assert m["parameters"] <= BUDGET_PARAMS
    assert (ROOT / "models" / "roles_head.pt").stat().st_size <= BUDGET_MB * 1024 * 1024
