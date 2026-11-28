from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any

from openbooks.core.iso4217 import PAYLOAD_CHECKSUM_KEY, REGISTRY_SCHEMA, registry_checksum

PAGE_URL = "https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html"
LIST_ONE_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml"
LIST_THREE_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-three.xml"
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "py"
    / "openbooks"
    / "src"
    / "openbooks"
    / "core"
    / "data"
    / "iso4217_registry.json"
)
NOT_APPLICABLE = "N.A."
CODE_PATTERN = re.compile(r"^[A-Z]{3}$")
NUMBER_PATTERN = re.compile(r"^\d{3}$")
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
USER_AGENT = "openbooks-registry-builder/1"


def fetch(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def element_text(node: ET.Element, tag: str) -> str:
    found = node.find(tag)
    if found is None or found.text is None or not found.text.strip():
        raise ValueError(f"<{node.tag}> is missing <{tag}>")
    return found.text.strip()


def checked(value: str, pattern: re.Pattern[str], field: str) -> str:
    if not pattern.match(value):
        raise ValueError(f"{field} {value!r} does not match {pattern.pattern}")
    return value


def parse_current(body: bytes) -> tuple[str, list[dict[str, Any]]]:
    root = ET.fromstring(body)
    rows = []
    for node in root.iter("CcyNtry"):
        if node.find("Ccy") is None:
            continue
        name_node = node.find("CcyNm")
        if name_node is None or name_node.text is None:
            raise ValueError("CcyNtry without CcyNm")
        minor = element_text(node, "CcyMnrUnts")
        rows.append(
            {
                "code": checked(element_text(node, "Ccy"), CODE_PATTERN, "Ccy"),
                "number": checked(element_text(node, "CcyNbr"), NUMBER_PATTERN, "CcyNbr"),
                "name": name_node.text.strip(),
                "minor_unit": None if minor == NOT_APPLICABLE else int(checked(minor, re.compile(r"^\d+$"), "CcyMnrUnts")),
                "fund": name_node.get("IsFund") == "true",
            }
        )
    return root.get("Pblshd", ""), rows


def parse_historical(body: bytes) -> tuple[str, list[dict[str, Any]]]:
    root = ET.fromstring(body)
    rows = []
    for node in root.iter("HstrcCcyNtry"):
        withdrawn = element_text(node, "WthdrwlDt")
        number = node.find("CcyNbr")
        name = node.find("CcyNm")
        rows.append(
            {
                "code": checked(element_text(node, "Ccy"), CODE_PATTERN, "Ccy"),
                "number": None if number is None or not number.text else checked(number.text.strip(), NUMBER_PATTERN, "CcyNbr"),
                "name": None if name is None or not name.text else name.text.strip(),
                "withdrawn": withdrawn,
                "withdrawn_month": withdrawn if MONTH_PATTERN.match(withdrawn) else None,
            }
        )
    return root.get("Pblshd", ""), rows


def unique_current(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        previous = by_code.setdefault(row["code"], row)
        if previous != row:
            raise ValueError(f"conflicting current entries for {row['code']}: {previous} vs {row}")
    return sorted(by_code.values(), key=lambda row: row["code"])


def unique_historical(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = {tuple(row.items()): row for row in rows}
    return sorted(unique.values(), key=lambda row: (row["code"], row["withdrawn"], row["number"]))


def source_record(url: str, body: bytes, published: str) -> dict[str, Any]:
    return {
        "url": url,
        "published": published,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def build_document(current_body: bytes, historical_body: bytes, retrieved_on: str) -> dict[str, Any]:
    current_published, current_rows = parse_current(current_body)
    historical_published, historical_rows = parse_historical(historical_body)
    document: dict[str, Any] = {
        "schema": REGISTRY_SCHEMA,
        "source": {
            "publisher": "SIX Group, ISO 4217 maintenance agency",
            "page": PAGE_URL,
            "retrieved_on": retrieved_on,
            "list_one": source_record(LIST_ONE_URL, current_body, current_published),
            "list_three": source_record(LIST_THREE_URL, historical_body, historical_published),
        },
        "current": unique_current(current_rows),
        "historical": unique_historical(historical_rows),
    }
    document[PAYLOAD_CHECKSUM_KEY] = registry_checksum(document)
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the bundled ISO 4217 registry from SIX list one and list three.")
    parser.add_argument("--list-one-file", type=Path)
    parser.add_argument("--list-three-file", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    current_body = args.list_one_file.read_bytes() if args.list_one_file else fetch(LIST_ONE_URL, args.timeout)
    historical_body = args.list_three_file.read_bytes() if args.list_three_file else fetch(LIST_THREE_URL, args.timeout)
    document = build_document(current_body, historical_body, date.today().isoformat())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    current_codes = {row["code"] for row in document["current"]}
    withdrawn_codes = {row["code"] for row in document["historical"]}
    print(f"current codes: {len(document['current'])}")
    print(f"funds: {sum(1 for row in document['current'] if row['fund'])}")
    print(f"no minor unit (N.A.): {sum(1 for row in document['current'] if row['minor_unit'] is None)}")
    print(f"historical rows: {len(document['historical'])} across {len(withdrawn_codes)} codes")
    print(f"codes both current and historical: {sorted(current_codes & withdrawn_codes)}")
    print(f"payload sha256: {document[PAYLOAD_CHECKSUM_KEY]}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
