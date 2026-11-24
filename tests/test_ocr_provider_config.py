"""Check the provider example shipped with the agent kit."""

import re
from pathlib import Path

from openbooks.statements import ocr_providers as ocr

SHIPPED_TOML = Path(__file__).resolve().parents[1] / "harness" / "openbooks.providers.toml"


def test_shipped_toml_declares_env_var_names_only_and_no_value_looks_secret():
    loaded = ocr.load_settings(SHIPPED_TOML, {})
    assert loaded.default == "tesseract" and loaded.fallback == "tesseract" and loaded.allow_remote is False
    assert len(loaded.providers) >= 6
    for provider in loaded.providers.values():
        for name in provider.env.values():
            assert re.fullmatch(r"[A-Z][A-Z0-9_]*", name) and not ocr.looks_like_secret(name)
