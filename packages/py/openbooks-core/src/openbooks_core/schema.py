"""The openbooks.v1 contract as data (schema/*.json) and the validator that enforces it beyond what JSON Schema can say."""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Literal

import jsonschema

from .errors import Refusal

SCHEMA_VERSION = "openbooks.v1"
_FILES = {"output": "openbooks.v1.schema.json", "refusal": "openbooks.v1.refusal.schema.json"}


@lru_cache(maxsize=None)
def load_schema(name: Literal["output", "refusal"] = "output") -> dict:
    return json.loads(resources.files("openbooks_core").joinpath("schema", _FILES[name]).read_text(encoding="utf-8"))


def _money_schema() -> dict:
    return load_schema("output")["$defs"]["money"]


def _needs_evidence(rec: dict):
    for k, v in rec.items():
        if isinstance(v, dict) and set(v) == {"amount", "currency"}:
            jsonschema.validate(v, _money_schema())
            yield k
        elif isinstance(v, str) and (k == "date" or k.startswith("period_")):
            yield k


def validate_output(doc: dict) -> None:
    try:
        jsonschema.validate(doc, load_schema("output"))
        data = doc["data"]
        for key in ("accounts", "batches", "transactions"):
            for rec in data[key]:
                for f in _needs_evidence(rec):
                    if f"{rec['id']}.{f}" not in doc["evidence"]:
                        raise Refusal("OUTPUT_INVALID", f"missing evidence for {rec['id']}.{f}")
    except jsonschema.ValidationError as e:
        raise Refusal("OUTPUT_INVALID", f"schema: {e.message[:200]}") from None
    accounts, batches = {a["id"] for a in data["accounts"]}, {b["id"] for b in data["batches"]}
    for t in data["transactions"]:
        if t["batch_id"] not in batches or ("account_id" in t and t["account_id"] not in accounts):
            raise Refusal("OUTPUT_INVALID", f"{t['id']} points to a missing account or batch")
    ass = doc["assertions"]
    if not all(a["passed"] for a in ass) or not any(a["independent"] for a in ass):
        raise Refusal("OUTPUT_INVALID", "assertions incomplete")


def refusal_doc(code: str, message: str, sha: str, *, internal: bool = False) -> dict:
    """internal=True marks a refusal caused by an unexpected engine exception, not by something readable in the document."""
    error = {"code": code, "message": message, "file_sha256": sha}
    if internal:
        error["internal"] = True
    return {"schema_version": SCHEMA_VERSION, "status": "refused", "data": None, "error": error}
