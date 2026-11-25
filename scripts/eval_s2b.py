"""Compare strict, row-local, and document-wide RoleNet resolution on frozen synthetic inputs.

For each seed a statement with no header row is rendered (rich + shifted layouts alternate). A file counts as
correct when it is released AND every transaction matches the rows it was rendered from; wrong = released but
different; abstained = LOW_CONFIDENCE. The release gate is the same in both runs.
Usage: python scripts/eval_s2b.py [N] --out out/roles/headerless-comparison.json
"""
from __future__ import annotations

import argparse
import json
import random
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]

from openbooks.statements import roles  # noqa: E402
from openbooks_lab.golden import OPEN  # noqa: E402
from openbooks_lab.golden_docs import _pdf_rows  # noqa: E402
from openbooks.pipeline import Params, Refusal, process  # noqa: E402
from openbooks_lab.synth import random_layout, render  # noqa: E402

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
    want = [(datetime.strptime(r[0], "%d/%m/%Y").date().isoformat(), "debit" if r[2] else "credit",
             Decimal(r[2] or r[3]), Decimal(r[4])) for r in rows if r[2] or r[3]]
    return [(t["date"], t["direction"], Decimal(t["amount"]["amount"]),
             Decimal(t["balance_after"]["amount"])) for t in tx] == want


def row_local(self, rows, opening, closing, value):
    """The previous row-local rule commits or refuses one row before seeing the next."""
    result = []
    previous = opening
    for tokens in rows:
        assignment = self.resolve(tokens, previous, value)
        balances = [token for token, role in assignment.items() if role == "balance"]
        if len(balances) != 1:
            raise Refusal("PARSE_ERROR", "expected one balance")
        previous = value(balances[0])
        result.append(assignment)
    return result


def run(inputs) -> dict:
    out = {"correct": 0, "wrong": 0, "abstained": 0, "other_refusal": 0, "files": len(inputs)}
    for path, rows in inputs:
        doc = process(path, Params("INR", Decimal(str(OPEN)), model=True), strict=True)
        if doc["status"] == "ok":
            out["correct" if matches(doc, rows) else "wrong"] += 1
        elif doc["error"]["code"] == "LOW_CONFIDENCE":
            out["abstained"] += 1
        else:
            out["other_refusal"] += 1
    return out


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("files", nargs="?", type=int, default=60)
    cli.add_argument("--out", type=Path, default=ROOT / "docs/evidence/s2b_headerless.json")
    args = cli.parse_args()
    if args.files <= 0:
        cli.error("files must be positive")
    torch.set_num_threads(4)
    with tempfile.TemporaryDirectory(prefix="ob_s2b_") as scratch:
        inputs = []
        for seed, rows, pdf in cases(args.files):
            file = Path(scratch) / f"{seed}.pdf"
            file.write_bytes(pdf)
            inputs.append((file, rows))
        with patch.object(roles.Predictions, "resolve_chain", row_local):
            with patch.object(roles.Predictions, "resolve", strict_resolve):
                strict = run(inputs)
            local = run(inputs)
        result = {"strict_before": strict, "chain_after": local, "document_chain": run(inputs)}
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return int(result["document_chain"]["wrong"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
