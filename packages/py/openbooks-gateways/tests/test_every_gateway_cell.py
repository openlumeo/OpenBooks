"""Mutation of every numeric cell: move any one amount in a released export by a cent either way and the file must be refused.

The only cells allowed to change without a refusal are listed below with the reason each one cannot reach a released number
(a payout or settlement row is a claim, not a transaction; a pending row is excluded; a fee column is not emitted; a derived
opening moves with the first row by design). A new entry here means a new number is released without proof: justify it."""
import csv
import io
import re
from decimal import Decimal

import pytest
from test_gateways import PAYPAL, RAZORPAY, STRIPE, WISE

from openbooks_core import Params, process

NUMBER = re.compile(r"^-?[\d,]+\.\d+$")
CASES = [("stripe", STRIPE, {}), ("razorpay", RAZORPAY, {}), ("paypal", PAYPAL, {}), ("wise", WISE, {"allow_derived_opening": True})]

# (layout, data row, column) -> why changing it cannot change a released number
NOT_RELEASED = {
    **{("stripe", 4, c): "payout row: only its net is used, as the claim the other rows are proven against" for c in ("gross", "fee")},
    **{("razorpay", 3, c): "settlement row: only its debit is used, as the claim" for c in ("credit", "amount", "fee", "tax")},
    **{("paypal", 2, c): "pending authorisation: excluded from the balance and from the output" for c in ("Gross", "Fee", "Net")},
    **{("wise", r, "Total fees"): "informational column, not emitted" for r in (1, 2, 3)},
    ("wise", 3, "Amount"): "first row: the opening balance is derived from it (allow_derived_opening), so it moves with it",
}


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
                    yield r, rows[0][c], delta, out.getvalue()


@pytest.mark.parametrize("name,text,params", CASES, ids=[c[0] for c in CASES])
def test_a_cent_moved_in_any_released_cell_is_refused(tmp_path, name, text, params):
    f = tmp_path / "m.csv"
    survivors, checked = set(), 0
    for r, col, delta, mutated in mutations(text):
        checked += 1
        f.write_text(mutated, encoding="utf-8")
        doc = process(f, Params(**params))
        assert doc["status"] in ("ok", "refused") and not doc.get("error", {}).get("internal"), (name, r, col, doc.get("error"))
        if doc["status"] == "ok":
            survivors.add((name, r, col))
    unexplained = {s for s in survivors if s not in NOT_RELEASED}
    assert checked > 10 and not unexplained, f"released with a changed number and no documented reason: {sorted(unexplained)}"
    stale = {k for k in NOT_RELEASED if k[0] == name} - survivors
    assert not stale, f"documented as unchecked but now refused (remove from NOT_RELEASED): {sorted(stale)}"


def test_the_excluded_rows_really_are_not_in_the_output(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text(PAYPAL.replace("50.00,0.00,50.00,a@x.com", "50.01,0.00,50.00,a@x.com"), encoding="utf-8")
    doc = process(f, Params())
    assert [t["id"] for t in doc["data"]["transactions"]] == ["txn-00001", "txn-00002"]
    assert "50.01" not in str(doc["data"])
    f.write_text(STRIPE.replace("-125.05,0.00,-125.05", "-125.06,0.00,-125.05"), encoding="utf-8")
    assert "125.06" not in str(process(f, Params())["data"]["transactions"])
