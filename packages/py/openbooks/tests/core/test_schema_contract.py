import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from openbooks.core.refusal_codes import REFUSAL_CODES

ROOT = Path(__file__).resolve().parents[5]
PY_SRC = ROOT / "packages" / "py" / "openbooks" / "src" / "openbooks"
REFUSAL_SCHEMA = PY_SRC / "core" / "schema" / "openbooks.v1.refusal.schema.json"
TS_CONSTANTS = ROOT / "packages" / "js" / "cli" / "src" / "core" / "generated" / "refusal-codes.ts"
SYNC = ROOT / "scripts" / "sync_schemas.py"

RUNTIME_CODE = re.compile(r'(?:Refusal|refusal_doc)\(\s*"([A-Z][A-Z_]+)"')
TS_BLOCK = re.compile(r"REFUSAL_CODES[^=]*=\s*\{(.*?)\n\};", re.DOTALL)
TS_KEY = re.compile(r'^\s+"?([A-Z][A-Z_]+)"?:', re.MULTILINE)


def schema_enum() -> set[str]:
    return set(REFUSAL_CODES)


def runtime_codes() -> set[str]:
    codes: set[str] = set()
    for path in PY_SRC.rglob("*.py"):
        codes.update(RUNTIME_CODE.findall(path.read_text(encoding="utf-8")))
    return codes


def typescript_codes(source: str) -> set[str]:
    block = TS_BLOCK.search(source)
    assert block, "REFUSAL_CODES map not found in constants.ts"
    return set(TS_KEY.findall(block.group(1)))


def drift(enum: set[str], emitted: set[str], documented: set[str]) -> dict[str, list[str]]:
    return {
        "emitted_not_in_enum": sorted(emitted - enum),
        "enum_never_emitted": sorted(enum - emitted),
        "enum_not_documented": sorted(enum - documented),
        "documented_not_in_enum": sorted(documented - enum),
    }


def test_schema_copies_match_canonical() -> None:
    result = subprocess.run([sys.executable, str(SYNC), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_refusal_enum_matches_python_runtime() -> None:
    assert drift(schema_enum(), runtime_codes(), set())["emitted_not_in_enum"] == []
    assert drift(schema_enum(), runtime_codes(), set())["enum_never_emitted"] == []


def test_refusal_enum_matches_typescript_map() -> None:
    report = drift(schema_enum(), set(), typescript_codes(TS_CONSTANTS.read_text(encoding="utf-8")))
    assert report["enum_not_documented"] == []
    assert report["documented_not_in_enum"] == []


def test_drift_helper_flags_an_added_code() -> None:
    enum = schema_enum() | {"FAKE_CODE"}
    report = drift(enum, runtime_codes(), set(enum))
    assert report["enum_never_emitted"] == ["FAKE_CODE"]


@pytest.mark.parametrize("code", sorted(schema_enum()))
def test_each_enum_code_has_a_typescript_entry(code: str) -> None:
    assert code in typescript_codes(TS_CONSTANTS.read_text(encoding="utf-8"))
