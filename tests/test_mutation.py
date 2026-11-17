"""Stage 4 (balance checks) by mutation: change ONE cell of a valid statement and it must never be released.

A valid bank CSV carries a running balance on every row, so any single wrong amount, balance or debit/credit flip breaks
the chain. (Dropping the last row is not tested: the remaining file is internally consistent.)"""
import csv
import io
from decimal import Decimal
from pathlib import Path

import pytest

from openbooks.golden import build
from openbooks.pipeline import Params, process

PARAMS = Params(currency="INR", opening=Decimal("1000.00"))


@pytest.fixture(scope="module")
def rows(tmp_path_factory) -> list[list[str]]:
    root = tmp_path_factory.mktemp("golden")
    build(root, 7, 0, False)
    return list(csv.reader(io.StringIO((root / "ok_bank_csv" / "in.csv").read_text(encoding="utf-8"))))


def _run(rows: list[list[str]], tmp: Path) -> dict:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    path = tmp / "m.csv"
    path.write_text(buf.getvalue(), encoding="utf-8")
    return process(path, PARAMS)


def _mutations(rows: list[list[str]]):
    head = rows[0]
    amount_cols = [i for i, h in enumerate(head) if any(k in h.lower() for k in ("withdrawal", "deposit", "balance"))]
    debit, credit = (next(i for i, h in enumerate(head) if k in h.lower()) for k in ("withdrawal", "deposit"))
    for r in range(1, len(rows)):
        for c in amount_cols:
            if not rows[r][c]:
                continue
            value = Decimal(rows[r][c])
            for label, new in (("cent", value + Decimal("0.01")), ("tenfold", value * 10), ("zeroed", Decimal("0.00"))):
                mutated = [list(x) for x in rows]
                mutated[r][c] = f"{new:.2f}"
                yield f"row{r}.col{c}.{label}", mutated
        if rows[r][debit] != rows[r][credit]:  # swap debit and credit on one row
            mutated = [list(x) for x in rows]
            mutated[r][debit], mutated[r][credit] = rows[r][credit], rows[r][debit]
            yield f"row{r}.dr_cr_swap", mutated
    for r in range(1, len(rows) - 1):  # a dropped row in the middle
        yield f"row{r}.dropped", [x for i, x in enumerate(rows) if i != r]


def test_the_unmutated_statement_is_released(rows, tmp_path):
    assert _run(rows, tmp_path)["status"] == "ok"


def test_no_single_cell_mutation_is_released(rows, tmp_path):
    released = [name for name, mutated in _mutations(rows) if _run(mutated, tmp_path)["status"] == "ok"]
    assert not released, f"released after a single mutation: {released}"
