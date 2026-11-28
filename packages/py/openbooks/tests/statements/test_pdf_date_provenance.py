from decimal import Decimal

from pdfmaker import statement_pdf

from openbooks.core import Params, process

DAY_PROOF = [("13/01/2026", "Salary", "", "500.00", "1500.00"), ("14/01/2026", "Rent", "200.00", "", "1300.00")]
AMBIGUOUS = [("03/04/2026", "Salary", "", "500.00", "1500.00"), ("04/04/2026", "Rent", "200.00", "", "1300.00")]


def run(tmp_path, rows, **params):
    f = tmp_path / "statement.pdf"
    f.write_bytes(statement_pdf(rows))
    return process(f, Params(**{"currency": "INR", "opening": Decimal("1000.00"), "ocr": False, **params}))


def test_pdf_file_proving_day_first_records_file_evidence(tmp_path):
    doc = run(tmp_path, DAY_PROOF)
    assert doc["status"] == "ok"
    assert doc["evidence"]["batch-1.date_order"]["raw_text"] == "dmy"
    assert doc["evidence"]["batch-1.date_order"]["provenance"] == "FILE_EVIDENCE"


def test_pdf_ambiguous_dates_refuse(tmp_path):
    doc = run(tmp_path, AMBIGUOUS)
    assert doc["error"]["code"] == "AMBIGUOUS_DATE"


def test_pdf_declared_order_is_recorded_as_caller_supplied(tmp_path):
    doc = run(tmp_path, AMBIGUOUS, date_order="mdy")
    assert doc["evidence"]["batch-1.date_order"]["raw_text"] == "mdy"
    assert doc["evidence"]["batch-1.date_order"]["provenance"] == "CALLER_SUPPLIED"
