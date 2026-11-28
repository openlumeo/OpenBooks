"""Build and verify a synthetic RoleNet cache with the exact words and boxes needed for proof replay."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pickle
from dataclasses import asdict
from itertools import takewhile
from pathlib import Path

import train_roles as tr
from openbooks.statements.pdf_words import Word
from role_candidates import sha256, split_sha256, write_json

TOKENS = "tokens.pkl"
EVIDENCE = "evidence.jsonl.gz"
MANIFEST = "manifest.json"
FIELDS = ("w", "s", "b", "y", "t")


def evidence_record(split, seed, source, method, pages, cells) -> dict:
    return {"split": split, "seed": seed, "source_sha256": hashlib.sha256(source).hexdigest(),
            "method": method, "pages": [[asdict(word) for word in page] for page in pages], "cells": cells}


def write_manifest(directory: Path, splits: dict, text_count: int, scan_count: int, **provenance) -> None:
    write_json(directory / MANIFEST, {
        "version": 1,
        "source": "OpenBooks synthetic statement generator",
        "recipe": {"training_text_documents": text_count, "training_scan_documents": scan_count},
        "artifacts_sha256": {name: sha256(directory / name) for name in (TOKENS, EVIDENCE)},
        "split_sha256": {name: split_sha256(windows) for name, windows in splits.items()},
        **provenance,
    })


def build(directory: Path, text_count: int, scan_count: int) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    evidence = directory / EVIDENCE
    tokens = directory / TOKENS
    with gzip.open(evidence, "xt", encoding="utf-8", newline="\n") as stream:
        def capture(split, seed, source, method, pages, cells):
            record = evidence_record(split, seed, source, method, pages, cells)
            stream.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")

        splits = tr.make_base_splits(text_count, scan_count, capture=capture)
    tokens.write_bytes(pickle.dumps(splits))
    write_manifest(directory, splits, text_count, scan_count)


def same_window(pair) -> bool:
    actual, expected = pair
    return all(actual[field] == expected[field] for field in FIELDS)


def verify(directory: Path, against: Path | None = None, *, replay: bool = False) -> dict:
    manifest = json.loads((directory / MANIFEST).read_bytes())
    if manifest["version"] != 1:
        raise ValueError("unsupported replay cache version")
    for name in (TOKENS, EVIDENCE):
        if sha256(directory / name) != manifest["artifacts_sha256"][name]:
            raise ValueError(f"artifact changed: {name}")
    splits = pickle.loads((directory / TOKENS).read_bytes())
    fingerprints = {name: split_sha256(windows) for name, windows in splits.items()}
    if fingerprints != manifest["split_sha256"]:
        raise ValueError("token split fingerprints changed")
    if replay:
        import numpy as np

        from research_direction_head import document_features

    stats = {name: {"documents": 0, "windows": 0} for name in splits}
    if replay:
        for name in ("test", "shifted"):
            stats[name].update(proof_documents=0, proof_directions=0, proof_label_mismatches=0)
    with gzip.open(directory / EVIDENCE, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            name = record["split"]
            pages = [[Word(**word) for word in page] for page in record["pages"]]
            reconstructed = tr.items_of(pages, record["cells"])
            start = stats[name]["windows"]
            stop = start + len(reconstructed)
            expected = splits[name][start:stop]
            if len(expected) != len(reconstructed) or not all(map(same_window, zip(reconstructed, expected))):
                raise ValueError(f"{name} document {record['seed']} differs from its token windows")
            stats[name]["windows"] = stop
            stats[name]["documents"] += 1
            if replay and name in ("test", "shifted"):
                neutral = np.zeros((sum(map(len, pages)), len(tr.ROLES)))
                _, proved = document_features(pages, neutral)
                stats[name]["proof_documents"] += bool(proved)
                stats[name]["proof_directions"] += len(proved)
                labels = [tr.RID[role] for page in pages for role in tr.label_words(page, record["cells"])]
                stats[name]["proof_label_mismatches"] += sum(labels[i] != role for i, role in proved.items())
    for name, windows in splits.items():
        if stats[name]["windows"] != len(windows):
            raise ValueError(f"{name} has token windows with no replay evidence")

    result = {"manifest_sha256": sha256(directory / MANIFEST),
              "split_sha256": fingerprints, "splits": stats}
    if against is not None:
        original = pickle.loads(against.read_bytes())
        result["comparison_sha256"] = sha256(against)
        result["comparison"] = {}
        for name, windows in splits.items():
            base = original[name]
            matched = sum(1 for _ in takewhile(same_window, zip(windows, base)))
            result["comparison"][name] = {"matching_prefix_windows": matched,
                                          "original_windows": len(base),
                                          "exact": matched == len(windows) == len(base)}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("build", help="Generate a new, separate cache directory")
    create.add_argument("directory", type=Path)
    create.add_argument("--text", type=int, default=8, help="Number of text-layer training PDFs")
    create.add_argument("--scans", type=int, default=0, help="Number of OCR training PDFs")
    check = commands.add_parser("verify", help="Rebuild window records from saved evidence")
    check.add_argument("directory", type=Path)
    check.add_argument("--against", type=Path, help="Compare against a trusted local original pickle")
    check.add_argument("--replay", action="store_true", help="Run arithmetic proof on saved evaluation words")
    args = parser.parse_args()
    try:
        if args.command == "build":
            if not (0 < args.text and 0 <= args.scans and args.text + args.scans <= 10_000):
                parser.error("require positive text count and at most 10,000 total training PDFs")
            build(args.directory, args.text, args.scans)
            print(args.directory / MANIFEST)
        else:
            print(json.dumps(verify(args.directory, args.against, replay=args.replay), indent=2))
    except (OSError, KeyError, TypeError, ValueError, pickle.UnpicklingError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")


if __name__ == "__main__":
    main()
