from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import Refusal

REGISTRY_PATH = Path(__file__).resolve().parent / "data" / "iso4217_registry.json"
REGISTRY_SCHEMA = "openbooks.iso4217_registry.v1"
PAYLOAD_CHECKSUM_KEY = "payload_sha256"


class RegistryIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class CurrencyRecord:
    code: str
    number: str | None
    name: str | None
    minor_unit: int | None
    fund: bool | None
    current: bool
    withdrawn: str | None
    withdrawn_month: str | None


def registry_checksum(document: dict[str, Any]) -> str:
    body = {key: value for key, value in document.items() if key != PAYLOAD_CHECKSUM_KEY}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _document() -> dict[str, Any]:
    document = json.loads(REGISTRY_PATH.read_bytes())
    if document.get("schema") != REGISTRY_SCHEMA:
        raise RegistryIntegrityError(f"unexpected ISO 4217 registry schema {document.get('schema')!r}")
    if registry_checksum(document) != document.get(PAYLOAD_CHECKSUM_KEY):
        raise RegistryIntegrityError("ISO 4217 registry checksum mismatch: the bundled snapshot was modified")
    return document


@lru_cache(maxsize=1)
def _indexes() -> tuple[dict[str, CurrencyRecord], dict[str, tuple[CurrencyRecord, ...]]]:
    document = _document()
    current = {
        row["code"]: CurrencyRecord(row["code"], row["number"], row["name"], row["minor_unit"], row["fund"], True, None, None)
        for row in document["current"]
    }
    withdrawn: dict[str, list[CurrencyRecord]] = {}
    for row in document["historical"]:
        withdrawn.setdefault(row["code"], []).append(
            CurrencyRecord(
                row["code"],
                row["number"],
                row["name"],
                None,
                None,
                False,
                row["withdrawn"],
                row["withdrawn_month"],
            )
        )
    return current, {code: tuple(rows) for code, rows in withdrawn.items()}


def _month(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def lookup(code: str, *, as_of: date | None = None) -> CurrencyRecord:
    current, withdrawn = _indexes()
    if code in current:
        return current[code]
    if as_of is not None and code in withdrawn:
        if any(record.withdrawn_month is None for record in withdrawn[code]):
            raise Refusal("PARSE_ERROR", f"currency code {code!r} has a withdrawal date range; as-of lookup is not provable")
        for record in withdrawn[code]:
            if _month(as_of) <= record.withdrawn_month:
                return record
        raise Refusal("PARSE_ERROR", f"currency code {code!r} was withdrawn before {as_of.isoformat()}")
    raise Refusal("PARSE_ERROR", f"currency code {code!r} is not an ISO 4217 code")


def exponent_of(code: str, *, as_of: date | None = None) -> int:
    record = lookup(code, as_of=as_of)
    if not record.current:
        raise Refusal(
            "PARSE_ERROR",
            f"currency code {code!r} was withdrawn {record.withdrawn}; SIX list three does not publish its minor unit",
        )
    if record.minor_unit is None:
        raise Refusal("PARSE_ERROR", f"currency code {code!r} has no defined minor unit (ISO 4217 N.A.)")
    return record.minor_unit
