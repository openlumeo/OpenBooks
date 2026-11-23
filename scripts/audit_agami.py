"""Audit local Agami PDF/JSON pairs and write a manifest without copying transaction text."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from eval_agami import BASE, ties, truth_rows


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def audit(root: Path) -> dict:
    families = {}
    documents = []
    duplicate_groups = {}
    for folder in sorted(root.glob("India_Bank_Statement_*")):
        if not folder.is_dir():
            continue
        stats = Counter()
        pdfs = {p.stem: p for p in folder.glob("*.pdf")}
        labels = {p.stem: p for p in folder.glob("*.json")}
        for stem in sorted(pdfs.keys() | labels.keys()):
            if stem not in pdfs or stem not in labels:
                stats["unpaired"] += 1
                continue
            pdf, label = pdfs[stem], labels[stem]
            stats["pairs"] += 1
            try:
                raw = json.loads(label.read_text(encoding="utf-8"))
                rows = truth_rows(raw)
                consistent = bool(rows) and ties(raw, rows)
                outcome = "balanced" if consistent else "unbalanced" if rows else "empty"
            except (KeyError, TypeError, ValueError, ArithmeticError):
                stats["invalid_labels"] += 1
                continue
            stats[outcome] += 1
            stats["transactions"] += len(rows)
            fingerprint = hashlib.sha256(repr(rows).encode()).hexdigest()
            document = {
                "pdf": pdf.relative_to(root).as_posix(),
                "labels": label.relative_to(root).as_posix(),
                "pdf_sha256": sha256(pdf),
                "label_sha256": sha256(label),
                "transactions": len(rows),
                "running_balance": outcome,
                "label_group_sha256": fingerprint,
                "layout_group": folder.name.rsplit("_", 1)[-1],
            }
            duplicate_groups.setdefault(fingerprint, []).append(document["pdf"])
            documents.append(document)
        families[folder.name] = dict(stats)
    if not documents:
        raise ValueError(f"No usable PDF/JSON pairs under {root}")
    return {
        "source": "https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements",
        "source_kind": "synthetic",
        "license": "Apache-2.0",
        "families": families,
        "identical_transaction_groups": [paths for paths in duplicate_groups.values() if len(paths) > 1],
        "documents": documents,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=BASE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["families"], indent=2))
    print(f"Identical transaction groups: {len(result['identical_transaction_groups'])}")


if __name__ == "__main__":
    main()
