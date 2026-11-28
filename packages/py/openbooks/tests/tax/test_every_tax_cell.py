"""Mutation of every numeric cell of every tax layout: a cent moved anywhere is refused, except where a column carries no proof.

KNOWN GAP (strict xfail below): AIS `modified_value` is released without any check, because the printed total covers
`reported_value` only. Fix it (check a printed modified total, or stop emitting the column) and the xfail turns into a failure
that tells you to delete the marker."""
import csv
import io
import re
from decimal import Decimal

import pytest
from test_tax import AIS_HEAD, AIS_ROWS, AIS_TOTAL, cases, csv as make_csv

from openbooks.core import Params, process

NUMBER = re.compile(r"^-?[\d,]+\.\d+$")
UNPROVEN = {("ais.v1", "Modified Value")}


def mutations(text):
    rows = list(csv.reader(io.StringIO(text)))
    for r in range(1, len(rows)):
        for c, v in enumerate(rows[r]):
            if NUMBER.match(v):
                for delta in (Decimal("0.01"), Decimal("-0.01")):
                    new = [x[:] for x in rows]
                    new[r][c] = f"{Decimal(v.replace(',', '')) + delta:.2f}"
                    out = io.StringIO()
                    csv.writer(out, lineterminator="\n").writerows(new)
                    yield r, rows[0][c], out.getvalue()


@pytest.mark.parametrize("text,layout,params", cases(), ids=[c[1] for c in cases()])
def test_a_cent_moved_in_any_cell_is_refused(tmp_path, text, layout, params):
    f = tmp_path / "m.csv"
    checked, survivors = 0, set()
    for r, col, mutated in mutations(text):
        checked += 1
        f.write_text(mutated, encoding="utf-8")
        doc = process(f, Params(**params))
        assert not doc.get("error", {}).get("internal"), (layout, r, col, doc["error"])
        if doc["status"] == "ok":
            survivors.add((layout, col))
    assert checked > 5
    assert survivors <= UNPROVEN, f"released with a changed number: {sorted(survivors - UNPROVEN)}"


@pytest.mark.xfail(strict=True, reason="AIS modified_value is released without proof: the printed total covers reported_value only")
def test_a_changed_ais_modified_value_is_refused(tmp_path):
    f = tmp_path / "ais.csv"
    f.write_text(make_csv(AIS_HEAD, AIS_ROWS, AIS_TOTAL).replace("12345.67,12345.67", "12345.67,99999.99"), encoding="utf-8")
    assert process(f, Params(currency="INR"))["status"] == "refused"
