"""S2b measurement: header-less synthetic PDFs through the typed-head fallback, strict (old) vs chain-resolved (new).

For each seed a statement with no header row is rendered (rich + shifted layouts alternate). A file counts as
correct when it is released AND every transaction matches the rows it was rendered from; wrong = released but
different; abstained = LOW_CONFIDENCE. The release gate is the same in both runs.
Usage: python scripts/eval_s2b.py [N] -> docs/evidence/s2b_headerless.json
"""
from __future__ import annotations

import json
import random
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from openbooks import roles  # noqa: E402
from openbooks.golden import OPEN  # noqa: E402
from openbooks.golden_docs import _pdf_rows  # noqa: E402
from openbooks.pipeline import Params, Refusal, process  # noqa: E402
from openbooks.synth import random_layout, render  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
NEW_RESOLVE = roles.Predictions.resolve


def strict_resolve(self, tokens, prev, value):
    """The behaviour before S2b: every token's conformal set must be exactly one amount role."""
    out = {}
    for w in tokens:
        p = self.table.get(w)
        if p is None or p.role not in roles.AMOUNT or p.role_set != (p.role,):
            raise Refusal("LOW_CONFIDENCE", f"page {w.page}: the typed head is not sure which column {w.text!r} is in")
        out[w] = p.role
    return out


def cases(n: int):
    for seed in range(n):
        rng = random.Random(9000 + seed)
        rows = _pdf_rows(rng, 12)
        lay = random_layout(rng, shifted=seed % 2 == 1, rich=seed % 4 >= 2)
        lay.has_header = False
        pdf = render(rows, str(OPEN), lay, rng, closing=rows[-1][4])[0]
        yield seed, rows, pdf


def matches(doc: dict, rows: list[list[str]]) -> bool:
    tx = doc["data"]["transactions"]
    want = [(("debit", r[2]) if r[2] else ("credit", r[3])) for r in rows if r[2] or r[3]]
    return [(t["direction"], t["amount"]["amount"]) for t in tx] == [(d, f"{Decimal(a):.2f}") for d, a in want]


def run(resolve) -> dict:
    roles.Predictions.resolve = resolve
    tmp = ROOT / "data" / "_s2b.pdf"
    tmp.parent.mkdir(exist_ok=True)
    out = {"correct": 0, "wrong": 0, "abstained": 0, "other_refusal": 0, "files": N}
    for seed, rows, pdf in cases(N):
        tmp.write_bytes(pdf)
        doc = process(tmp, Params("INR", Decimal(str(OPEN)), None, False, model=True))
        if doc["status"] == "ok":
            out["correct" if matches(doc, rows) else "wrong"] += 1
        elif doc["error"]["code"] == "LOW_CONFIDENCE":
            out["abstained"] += 1
        else:
            out["other_refusal"] += 1
    tmp.unlink(missing_ok=True)
    return out


if __name__ == "__main__":
    result = {"strict_before": run(strict_resolve), "chain_after": run(NEW_RESOLVE)}
    (ROOT / "docs" / "evidence" / "s2b_headerless.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
