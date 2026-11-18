"""File-level check of the shipped typed heads on synthetic PDFs (and scans with --scans).

Builds the golden set, runs every PDF/image with --model, and requires: every expected-ok file released, zero false
accepts (a refusal-expected file that was released). Exits 1 otherwise. Usage: python scripts/file_level.py [--scans]
"""
from __future__ import annotations

import json
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from openbooks.golden import build  # noqa: E402
from openbooks.pipeline import Params, process  # noqa: E402

DOC_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg")


def main(scans: bool) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ob_fl_"))
    build(tmp, 7, 0, scans)
    cases = []
    for d in sorted(p for p in tmp.iterdir() if p.is_dir()):
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        src = next(f for f in d.iterdir() if f.name != "expected.json")
        if src.suffix.lower() in DOC_SUFFIXES:
            cases.append((d.name, src, exp))
    released = false_accepts = 0
    for name, src, exp in cases:
        pr = exp.get("params", {})
        doc = process(src, Params(pr.get("currency"), Decimal(pr["opening"]) if "opening" in pr else None, pr.get("account"),
                                  pr.get("allow_derived_opening", False), model=True))
        got_ok = doc["status"] == "ok"
        released += got_ok and exp["status"] == "ok"
        bad = got_ok and exp["status"] == "refused"
        false_accepts += bad
        print(f"  {name:38} want={exp['status']:7} got={doc['status']:7} {doc.get('error', {}).get('code', '')}"
              f"{'  FALSE ACCEPT' if bad else ''}", flush=True)
    expected_ok = sum(1 for _, _, e in cases if e["status"] == "ok")
    print(f"released {released}/{expected_ok} expected-ok files, false accepts {false_accepts}", flush=True)
    return int(released != expected_ok or false_accepts > 0)


if __name__ == "__main__":
    raise SystemExit(main("--scans" in sys.argv))
