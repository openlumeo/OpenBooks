"""Reproducible unseen-family baseline: render N seeds of each synthetic family and run the header parser (no --model).

Prints released / typed refusals / wrong releases per family and writes docs/evidence/family_baseline.json.
A wrong release (released ledger != the rows rendered) is a hard failure. S3 compares against the S2 numbers
(branch 12/12, sign 4/12, skew 4/12). Usage: python scripts/family_baseline.py [n_seeds=12]
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from openbooks.golden_docs import _pdf_rows  # noqa: E402
from openbooks.pipeline import Params, process  # noqa: E402
from openbooks.synth import FAMILIES, SKEW_MERCHANTS, merchant_rows, random_layout, render  # noqa: E402


def build(family: str, seed: int):
    rng = random.Random(500 + seed)
    lay = random_layout(rng, family=family)
    lay.has_header = True
    rows = _pdf_rows(random.Random(seed), rng.randint(8, 30))
    if family == "skew":
        rows = merchant_rows(rows, rng, SKEW_MERCHANTS)
    pdf, _ = render(rows, "1000.00", lay, rng, closing=rows[-1][4])
    return rows, pdf


def main(n_seeds: int = 12) -> dict:
    out: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "f.pdf"
        for family in FAMILIES:
            refusals, released, wrong = Counter(), 0, 0
            for s in range(n_seeds):
                rows, pdf = build(family, s)
                path.write_bytes(pdf)
                doc = process(path, Params(currency="INR"))
                if doc["status"] != "ok":
                    refusals[doc["error"]["code"]] += 1
                    continue
                want = [(("debit", r[2]) if r[2] else ("credit", r[3])) for r in rows if r[2] or r[3]]
                got = [(t["direction"], t["amount"]["amount"]) for t in doc["data"]["transactions"]]
                if got == [(d, f"{Decimal(a):.2f}") for d, a in want]:
                    released += 1
                else:
                    wrong += 1
            out[family] = {"seeds": n_seeds, "released": released, "wrong_releases": wrong, "refusals": dict(refusals)}
            print(f"{family:7} released {released}/{n_seeds}  wrong {wrong}  refusals {dict(refusals)}", flush=True)
    (ROOT / "docs" / "evidence").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "evidence" / "family_baseline.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    if any(v["wrong_releases"] for v in out.values()):
        raise SystemExit("WRONG RELEASE: a family PDF produced a ledger that differs from the rendered rows")
    return out


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
