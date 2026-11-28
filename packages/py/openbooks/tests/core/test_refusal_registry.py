import ast
import importlib.util
import re
from pathlib import Path

import pytest
from jsonschema import validate

from openbooks.core import load_schema
from openbooks.core.refusal_codes import REFUSAL_CODES, UnregisteredRefusalCode
from openbooks.core.schema import refusal_doc

SHA = "a" * 64
CODE = re.compile(r"^[A-Z][A-Z_]+$")
ROOT = Path(__file__).resolve().parents[5]
SRC = Path(__file__).resolve().parents[2] / "src" / "openbooks"
SYNC = ROOT / "scripts" / "sync_schemas.py"


def _emitted_codes() -> set[str]:
    codes: set[str] = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str) and CODE.match(first.value)):
                continue
            is_refusal = isinstance(node.func, ast.Name) and node.func.id in {"Refusal", "refusal_doc"}
            is_super_init = isinstance(node.func, ast.Attribute) and node.func.attr == "__init__"
            if is_refusal or is_super_init:
                codes.add(first.value)
    return codes


def test_every_emitted_refusal_code_in_src_is_registered():
    emitted = _emitted_codes()
    assert {"PARSE_ERROR", "UNKNOWN_LAYOUT", "AMBIGUOUS_DATE"} <= emitted
    assert emitted <= set(REFUSAL_CODES), sorted(emitted - set(REFUSAL_CODES))


def test_every_registered_code_matches_the_public_pattern():
    assert all(CODE.match(code) for code in REFUSAL_CODES)
    assert all(meaning.strip() for meaning in REFUSAL_CODES.values())


def test_refusal_doc_rejects_an_unregistered_code():
    with pytest.raises(UnregisteredRefusalCode):
        refusal_doc("NOT_A_REAL_CODE", "x", SHA)


@pytest.mark.parametrize("code", sorted(REFUSAL_CODES))
def test_each_registered_code_yields_a_schema_valid_refusal(code):
    validate(refusal_doc(code, "x", SHA), load_schema("refusal"))


def test_public_schema_accepts_a_code_added_later():
    validate({**refusal_doc("PARSE_ERROR", "x", SHA), "error": {"code": "FUTURE_CODE", "message": "x", "file_sha256": SHA}},
             load_schema("refusal"))


def test_generated_copies_match_the_registry_and_schema():
    spec = importlib.util.spec_from_file_location("sync_schemas", SYNC)
    if spec is None or spec.loader is None or not SYNC.is_file():
        pytest.skip("repository scripts are not present")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.divergences() == []
    assert module.generated_divergences() == []
