from decimal import Decimal

import pytest

from openbooks.core import Params, default_registry, process
from openbooks.core.process import _extract

HEADER = "Date,Description,Amount,Balance\n"
BODY = (
    "02/01/2026,Salary January,45000.00,46000.00\n"
    "03/01/2026,Rent payment,-12500.00,33500.00\n"
    "05/01/2026,Grocery store,-1843.75,31656.25\n"
    "08/01/2026,Electricity bill,-2310.40,29345.85\n"
    "12/01/2026,Client invoice 1042,18250.00,47595.85\n"
    "15/01/2026,ATM withdrawal,-5000.00,42595.85\n"
    "20/01/2026,Insurance premium,-3999.99,38595.86\n"
    "28/01/2026,Interest credit,112.35,38708.21\n"
)
SAMPLE = HEADER + BODY


@pytest.fixture
def run(tmp_path):
    def _run(text, **params):
        f = tmp_path / "in.csv"
        f.write_text(text, encoding="utf-8")
        return process(f, Params(**{"currency": "INR", "date_order": "dmy", **params}))
    return _run


@pytest.fixture
def parse(tmp_path):
    def _parse(text, **params):
        f = tmp_path / "parse.csv"
        f.write_text(text, encoding="utf-8")
        data, *_ = _extract(f, Params(**{"currency": "INR", "date_order": "dmy", **params}), default_registry(), lambda _name: None)
        return data
    return _parse


def test_balanced_file_reads_with_signed_directions_and_refuses_a_caller_opening(run, parse):
    doc = run(SAMPLE, opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH", doc.get("error")
    data = parse(SAMPLE, opening=Decimal("1000.00"))
    txns = data["transactions"]
    assert len(txns) == 8
    assert [(t["direction"], t["amount"]["amount"]) for t in txns[:3]] == [
        ("credit", "45000.00"), ("debit", "12500.00"), ("debit", "1843.75")]
    batch = data["batches"][0]
    assert batch["opening"]["amount"] == "1000.00" and batch["closing"]["amount"] == "38708.21"


def test_tampered_amount_is_refused_by_the_balance_gate(run):
    doc = run(SAMPLE.replace("-12500.00", "-12950.00"), opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_thousands_separators_and_parenthesised_negatives_read_and_refuse_a_caller_opening(run, parse):
    text = HEADER + '01/01/2026,Pay,"1,000.00","2,000.00"\n02/01/2026,Fee,(250.50),"1,749.50"\n'
    doc = run(text, opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH", doc.get("error")
    data = parse(text, opening=Decimal("1000.00"))
    assert [(t["direction"], t["amount"]["amount"]) for t in data["transactions"]] == [("credit", "1000.00"), ("debit", "250.50")]


def test_parenthesised_negative_that_does_not_balance_is_refused(run):
    text = HEADER + "01/01/2026,Fee,(250.50),1250.50\n"
    doc = run(text, opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


@pytest.mark.parametrize("header", [
    "Date,Description,Amount,Debit,Balance",
    "Date,Description,Amount,Credit,Balance",
    "Date,Description,Amount,Type,Balance",
    "Date,Description,Amount,Dr/Cr,Balance",
    "Date,Description,Amount,Amt,Balance",
    "Date,Description,Amount,Amount,Balance",
])
def test_ambiguous_headers_are_refused_as_unknown_layout(run, header):
    width = header.count(",") + 1
    row = ",".join(["01/01/2026", "x"] + ["1.00"] * (width - 2))
    doc = run(f"{header}\n{row}\n", opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNKNOWN_LAYOUT"


def test_zero_amount_row_is_refused(run):
    doc = run(HEADER + "01/01/2026,Nothing,0.00,1000.00\n", opening=Decimal("1000.00"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"
