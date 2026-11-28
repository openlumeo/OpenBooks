from decimal import Decimal

from openbooks.core import Params, default_registry, process
from openbooks.core.process import _extract

BANK_HEAD = "Date,Description,Debit,Credit,Balance"


def run(tmp_path, text, **params):
    f = tmp_path / "in.csv"
    f.write_text(text, encoding="utf-8")
    return process(f, Params(**{"currency": "INR", "opening": Decimal("1000.00"), **params}))


def parse(tmp_path, text, **params):
    f = tmp_path / "parse.csv"
    f.write_text(text, encoding="utf-8")
    _, ev, *_ = _extract(f, Params(**{"currency": "INR", "opening": Decimal("1000.00"), **params}), default_registry(), lambda _name: None)
    return ev


def test_bank_csv_records_the_day_month_order_it_read_dates_with_as_provenance(tmp_path):
    text = "\n".join([BANK_HEAD, "13/01/2026,A,10.00,,990.00", "05/02/2026,B,,5.00,995.00"]) + "\n"
    doc = run(tmp_path, text)
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"
    ev = parse(tmp_path, text)
    assert ev["batch-1.date_order"]["raw_text"] == "dmy"
    assert ev["batch-1.date_order"]["provenance"] == "FILE_EVIDENCE"


def test_bank_csv_declared_date_order_is_recorded_as_caller_supplied(tmp_path):
    text = "\n".join([BANK_HEAD, "05/01/2026,A,10.00,,990.00", "06/02/2026,B,,5.00,995.00"]) + "\n"
    doc = run(tmp_path, text, date_order="mdy")
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"
    ev = parse(tmp_path, text, date_order="mdy")
    assert ev["batch-1.date_order"]["raw_text"] == "mdy"
    assert ev["batch-1.date_order"]["provenance"] == "CALLER_SUPPLIED"
