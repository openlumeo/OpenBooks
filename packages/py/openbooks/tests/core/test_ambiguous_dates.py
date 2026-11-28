from decimal import Decimal

import pytest

from openbooks.core import Params, default_registry, process
from openbooks.core.errors import Refusal
from openbooks.core.process import _extract
from openbooks.core.normalise import date_order

HEAD = "Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance"


def _csv(rows):
    return "\n".join([HEAD, *rows]) + "\n"


def test_an_ambiguous_numeric_date_refuses_with_the_typed_code():
    with pytest.raises(Refusal) as err:
        date_order(["03/04/2026"], where="date column")
    assert err.value.code == "AMBIGUOUS_DATE"


def test_a_declared_format_resolves_an_ambiguous_date():
    assert date_order(["03/04/2026"], "mdy") == "mdy"
    assert date_order(["03/04/2026"], "dmy") == "dmy"


def test_a_component_above_12_in_the_same_document_fixes_the_order():
    assert date_order(["03/04/2026", "25/04/2026"]) == "dmy"
    assert date_order(["03/04/2026", "04/25/2026"]) == "mdy"


def test_iso_and_month_name_dates_need_no_order_and_do_not_refuse():
    assert date_order(["2026-04-03", "2026-03-04"]) == "dmy"
    assert date_order(["03 Apr 2026", "04 Mar 2026"]) == "dmy"


def test_a_bank_csv_with_ambiguous_dates_is_refused_not_guessed(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text(_csv(["03/04/2026,Salary,,500.00,1500.00", "04/04/2026,Rent,200.00,,1300.00"]), encoding="utf-8")
    doc = process(f, Params(currency="INR", opening=Decimal("1000.00")))
    assert doc["status"] == "refused"
    assert doc["error"]["code"] == "AMBIGUOUS_DATE"


def test_a_bank_csv_with_a_declared_order_is_read_with_that_order_and_a_caller_opening_is_refused(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text(_csv(["03/04/2026,Salary,,500.00,1500.00"]), encoding="utf-8")
    params = Params(currency="INR", opening=Decimal("1000.00"), date_order="mdy")
    doc = process(f, params)
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"
    data, *_ = _extract(f, params, default_registry(), lambda _name: None)
    assert data["transactions"][0]["date"] == "2026-03-04"
