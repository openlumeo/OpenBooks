"""Freeze or verify a labeled document holdout for RoleNet evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from scripts.role_candidates import sha256


def asset(root: Path, name: str, suffix: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != suffix or not path.is_file():
        raise ValueError(f"invalid {suffix} asset: {name}")
    return path


def check_truth(truth: dict) -> None:
    outcome = truth["outcome"]
    rows = truth["transactions"]
    if outcome not in ("released", "refused") or not truth["adjudication"].strip():
        raise ValueError("expected an adjudicated release decision")
    if rows is None and outcome == "refused":
        return
    if not isinstance(rows, list) or not rows:
        raise ValueError("expected reference transactions")
    for row in rows:
        if (date.fromisoformat(row["date"]).isoformat() != row["date"]
                or row["direction"] not in ("debit", "credit")
                or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", row["amount"])
                or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", row["balance"])):
            raise ValueError("invalid reference transaction")


def build_manifest(roster_path: Path) -> dict:
    root = roster_path.resolve().parent
    roster = json.loads(roster_path.read_bytes())
    documents = {}
    group_splits = {}
    pdf_hashes = set()
    for entry in roster:
        doc_id = entry["id"]
        split = entry["split"]
        if not doc_id.strip() or doc_id in documents or split not in ("development", "holdout"):
            raise ValueError(f"invalid id or split: {doc_id}")
        record = {"split": split}
        for key in ("source_document", "layout"):
            group = entry[key]
            canonical = group.strip().casefold()
            if not canonical or group_splits.setdefault((key, canonical), split) != split:
                raise ValueError(f"empty or overlapping {key}: {group}")
            record[key] = group
        pdf = asset(root, entry["pdf"], ".pdf")
        digest = sha256(pdf)
        if digest in pdf_hashes:
            raise ValueError(f"duplicate PDF bytes: {doc_id}")
        pdf_hashes.add(digest)
        record.update(pdf=pdf.relative_to(root).as_posix(), pdf_sha256=digest)
        if split == "holdout":
            if "currency" in entry:
                currency = entry["currency"]
                if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
                    raise ValueError(f"invalid currency for {doc_id}")
                record["currency"] = currency
            truth = asset(root, entry["truth"], ".json")
            content = truth.read_bytes()
            try:
                check_truth(json.loads(content))
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid truth for {doc_id}: {exc}") from exc
            record.update(truth=truth.relative_to(root).as_posix(),
                          truth_sha256=hashlib.sha256(content).hexdigest())
        documents[doc_id] = record
    if {doc["split"] for doc in documents.values()} != {"development", "holdout"}:
        raise ValueError("the roster must contain both development and holdout documents")
    return {"version": 1, "documents": documents}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roster", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        manifest = build_manifest(args.roster)
        if args.verify:
            if manifest != json.loads(args.manifest.read_bytes()):
                raise ValueError("roster, PDF or truth differs from the frozen manifest")
        else:
            with args.manifest.open("x", encoding="utf-8", newline="\n") as output:
                output.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")


if __name__ == "__main__":
    main()
