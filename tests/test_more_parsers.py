"""PayPal, Wise and 1099-B parsers, and day/month order handling. Synthetic fixtures only; layouts are unverified against
real exports. Every tampered fixture must refuse, and an ambiguous date order must never be guessed for US-style layouts."""
from decimal import Decimal

import pytest

from openbooks.pipeline import Params, process

PAYPAL = """Date,Time,TimeZone,Name,Type,Status,Currency,Gross,Fee,Net,From Email Address,To Email Address,Transaction ID,Balance Impact
01/15/2026,10:00:00,PST,Acme,Payment,Completed,USD,"1,100.00",-3.20,"1,096.80",a@x.com,b@y.com,T1,Credit
01/16/2026,11:00:00,PST,Acme,Authorization,Pending,USD,50.00,0.00,50.00,a@x.com,b@y.com,T2,Memo
02/03/2026,12:00:00,PST,Bob,Payment,Completed,USD,-50.00,0.00,-50.00,b@y.com,c@z.com,T3,Debit
"""

WISE = """TransferWise ID,Date,Amount,Currency,Description,Payment Reference,Running Balance,Total fees
CARD-3,13-01-2026,-25.50,EUR,Coffee,,1074.50,0.00
TRANSFER-2,02-01-2026,-100.00,EUR,Sent to Bob,rent,1100.00,0.50
TRANSFER-1,01-01-2026,200.00,EUR,Received from Ann,inv 1,1200.00,0.00
"""

B1099 = """Description,Date Acquired,Date Sold,Proceeds,Cost Basis,Wash Sale Loss Disallowed,Gain/Loss
100 sh ACME,01/15/2025,03/20/2026,1500.00,1000.00,,500.00
50 sh FOO,VARIOUS,04/21/2026,800.00,900.00,25.00,-75.00
TOTAL,,,2300.00,1900.00,,425.00
"""

BANK = """Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance
,Opening Balance,,,1000.00
{d1},TXN 0,,500.00,1500.00
{d2},TXN 1,200.00,,1300.00
"""


def _run(tmp_path, text: str, **params) -> dict:
    path = tmp_path / "in.csv"
    path.write_text(text, encoding="utf-8")
    return process(path, Params(**params))


def test_paypal_releases_and_reads_month_first_dates(tmp_path):
    doc = _run(tmp_path, PAYPAL)
    assert doc["status"] == "ok" and doc["file"]["layout_version"] == "paypal_activity.v1"
    txns = doc["data"]["transactions"]
    assert [t["date"] for t in txns] == ["2026-01-15", "2026-02-03"]
    assert txns[0]["fee"]["amount"] == "3.20" and txns[0]["net"]["amount"] == "1096.80"


@pytest.mark.parametrize("old,new", [("1,096.80", "1,096.81"), ("-3.20", "-3.10")])
def test_paypal_tampered_row_refuses(tmp_path, old, new):
    doc = _run(tmp_path, PAYPAL.replace(old, new))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_paypal_ambiguous_date_order_is_never_guessed(tmp_path):
    ambiguous = PAYPAL.replace("01/15/2026", "01/05/2026").replace("01/16/2026", "01/06/2026")
    doc = _run(tmp_path, ambiguous)
    assert doc["status"] == "refused" and "ambiguous" in doc["error"]["message"]
    assert _run(tmp_path, ambiguous, date_order="mdy")["data"]["transactions"][0]["date"] == "2026-01-05"
    assert _run(tmp_path, ambiguous, date_order="dmy")["data"]["transactions"][0]["date"] == "2026-05-01"


def test_wise_with_only_a_caller_opening_is_not_released(tmp_path):
    doc = _run(tmp_path, WISE, opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"
    assert "independent evidence" in doc["error"]["message"]


def test_wise_needs_an_opening_and_refuses_a_broken_balance(tmp_path):
    assert _run(tmp_path, WISE)["error"]["code"] == "PARSE_ERROR"
    doc = _run(tmp_path, WISE.replace("1100.00", "1101.00"), opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_1099b_releases_with_wash_sale_and_printed_totals(tmp_path):
    doc = _run(tmp_path, B1099, currency="USD")
    assert doc["status"] == "ok" and doc["file"]["layout_version"] == "form_1099b.v1"
    t = doc["data"]["transactions"]
    assert t[0]["date"] == "2026-03-20" and t[0]["date_acquired"] == "2025-01-15"
    assert "date_acquired" not in t[1]
    assert t[1]["adjustment"]["amount"] == "25.00"


@pytest.mark.parametrize("old,new", [("500.00\n", "501.00\n"), ("2300.00", "2301.00"), ("-75.00", "-50.00")])
def test_1099b_tampered_figure_refuses(tmp_path, old, new):
    doc = _run(tmp_path, B1099.replace(old, new, 1), currency="USD")
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_bank_csv_month_first_dates_are_proven_by_a_day_above_12(tmp_path):
    doc = _run(tmp_path, BANK.format(d1="01/13/2026", d2="01/14/2026"), currency="USD", opening=Decimal("1000.00"))
    assert doc["status"] == "ok"
    assert [t["date"] for t in doc["data"]["transactions"]] == ["2026-01-13", "2026-01-14"]


def test_bank_csv_without_proof_is_refused_until_the_order_is_declared(tmp_path):
    text = BANK.format(d1="03/04/2026", d2="04/04/2026")
    kw = {"currency": "INR", "opening": Decimal("1000.00")}
    refused = _run(tmp_path, text, **kw)
    assert refused["status"] == "refused" and refused["error"]["code"] == "AMBIGUOUS_DATE"
    assert _run(tmp_path, text, date_order="dmy", **kw)["data"]["transactions"][0]["date"] == "2026-04-03"
    assert _run(tmp_path, text, date_order="mdy", **kw)["data"]["transactions"][0]["date"] == "2026-03-04"


def test_a_file_mixing_both_orders_refuses(tmp_path):
    doc = _run(tmp_path, BANK.format(d1="13/01/2026", d2="01/14/2026"), currency="INR", opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and "both day-first and month-first" in doc["error"]["message"]
