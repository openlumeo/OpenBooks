import ast
import json
import re
from pathlib import Path

from openbooks.core.refusal_codes import REFUSAL_CODES

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "openbooks"
SCHEMA = SRC / "core" / "schema" / "openbooks.v1.refusal.schema.json"
CODE = re.compile(r"^[A-Z][A-Z_]+$")


def _raised_codes() -> set[str]:
    codes: set[str] = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str) and CODE.match(first.value)):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "Refusal":
                codes.add(first.value)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "__init__":
                codes.add(first.value)
    return codes


def _schema_codes() -> set[str]:
    return set(REFUSAL_CODES)


def test_every_refusal_code_raised_in_the_source_is_in_the_registry():
    raised = _raised_codes()
    assert {"PARSE_ERROR", "UNKNOWN_LAYOUT", "AMBIGUOUS_DATE"} <= raised
    assert raised <= _schema_codes(), sorted(raised - _schema_codes())


def test_the_registry_has_no_codes_the_source_never_raises():
    assert _schema_codes() <= _raised_codes(), sorted(_schema_codes() - _raised_codes())
