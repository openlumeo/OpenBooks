from openbooks.core import Params, process

TDS_HEAD = "Deductor Name,TAN,Section,Transaction Date,Amount Paid/Credited,Tax Deducted,TDS Deposited"
FIRA_HEAD = "FIRA No,Date,Remitter,Currency,Foreign Amount,Exchange Rate,INR Amount,Bank Charges,Net Credited"


def run(tmp_path, text, **params):
    f = tmp_path / "in.csv"
    f.write_text(text, encoding="utf-8")
    return process(f, Params(**params))


def test_tds_numeric_dates_with_no_day_month_proof_refuse_instead_of_defaulting_to_day_first(tmp_path):
    text = "\n".join([TDS_HEAD,
                      "Acme Ltd,MUMA12345B,194C,03/04/2025,100000.00,2000.00,2000.00",
                      "Globex Pvt Ltd,DELG54321A,194J,05/06/2025,50000.00,5000.00,5000.00",
                      "Total,,,,150000.00,7000.00,7000.00"]) + "\n"
    doc = run(tmp_path, text, currency="INR")
    assert doc["status"] == "refused" and doc["error"]["code"] == "AMBIGUOUS_DATE"


def test_fira_numeric_dates_with_no_day_month_proof_refuse_instead_of_defaulting_to_day_first(tmp_path):
    text = "\n".join([FIRA_HEAD, "F1,03/04/2026,Acme,USD,100.00,83.00,8300.00,0.00,8300.00"]) + "\n"
    doc = run(tmp_path, text)
    assert doc["status"] == "refused" and doc["error"]["code"] == "AMBIGUOUS_DATE"


def test_tds_records_the_day_month_order_it_read_dates_with_as_provenance(tmp_path):
    text = "\n".join([TDS_HEAD,
                      "Acme Ltd,MUMA12345B,194C,15/04/2025,100000.00,2000.00,2000.00",
                      "Globex Pvt Ltd,DELG54321A,194J,20/05/2025,50000.00,5000.00,5000.00",
                      "Total,,,,150000.00,7000.00,7000.00"]) + "\n"
    doc = run(tmp_path, text, currency="INR")
    assert doc["status"] == "ok"
    assert doc["evidence"]["batch-1.date_order"]["raw_text"] == "dmy"
    assert doc["evidence"]["batch-1.date_order"]["provenance"] == "FILE_EVIDENCE"


def test_trial_balance_file_currency_that_contradicts_the_caller_currency_refuses(tmp_path):
    text = "Account,Debit,Credit,Currency\nCash,5000.00,,USD\nCapital,,5000.00,USD\n"
    doc = run(tmp_path, text, currency="INR")
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


def test_fira_row_declaring_inr_as_its_foreign_currency_is_refused(tmp_path):
    text = "\n".join([FIRA_HEAD, "F1,13/04/2026,Acme,INR,100.00,1.00,100.00,0.00,100.00"]) + "\n"
    doc = run(tmp_path, text)
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"
