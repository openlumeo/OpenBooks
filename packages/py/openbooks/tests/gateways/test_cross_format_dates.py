from decimal import Decimal

from openbooks.core import Params, process

BANK_HEAD = "Date,Description,Debit,Credit,Balance"
TDS_HEAD = "Deductor Name,TAN,Section,Transaction Date,Amount Paid/Credited,Tax Deducted,TDS Deposited"
FIRA_HEAD = "FIRA No,Date,Remitter,Currency,Foreign Amount,Exchange Rate,INR Amount,Bank Charges,Net Credited"


def run(tmp_path, lines, **params):
    f = tmp_path / "in.csv"
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return process(f, Params(**{"currency": "INR", "opening": Decimal("1000.00"), **params}))


def test_bank_csv_mixed_day_and_month_first_dates_refuse_even_with_one_unambiguous_date(tmp_path):
    doc = run(tmp_path, [BANK_HEAD, "13/01/2026,A,10.00,,990.00", "01/13/2026,B,,5.00,995.00"])
    assert doc["error"]["code"] == "PARSE_ERROR"


def test_bank_csv_declared_order_contradicting_the_data_names_the_conflict(tmp_path):
    doc = run(tmp_path, [BANK_HEAD, "05/01/2026,A,10.00,,990.00", "04/13/2026,B,,5.00,995.00"], date_order="dmy")
    assert doc["error"]["code"] == "PARSE_ERROR"
    assert "contradicts" in doc["error"]["message"]


def test_tds_mixed_formats_refuse_even_with_one_unambiguous_date(tmp_path):
    doc = run(tmp_path, [TDS_HEAD, "ACME,TAN1,194J,13/01/2026,1000.00,100.00,100.00",
                         "ACME,TAN1,194J,04/13/2026,1000.00,100.00,100.00"])
    assert doc["error"]["code"] == "PARSE_ERROR"


def test_fira_mixed_formats_refuse_even_with_one_unambiguous_date(tmp_path):
    doc = run(tmp_path, [FIRA_HEAD, "F1,13/01/2026,Acme,USD,100.00,83.00,8300.00,0.00,8300.00",
                         "F2,04/13/2026,Acme,USD,100.00,83.00,8300.00,0.00,8300.00"])
    assert doc["error"]["code"] == "PARSE_ERROR"


def test_fira_ambiguous_dates_refuse_instead_of_defaulting_to_day_first(tmp_path):
    doc = run(tmp_path, [FIRA_HEAD, "F1,03/04/2026,Acme,USD,100.00,83.00,8300.00,0.00,8300.00"])
    assert doc["error"]["code"] == "AMBIGUOUS_DATE"
