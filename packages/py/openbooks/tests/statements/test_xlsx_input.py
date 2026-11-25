"""Workbooks as input: the same rules as the CSV of the same statement, plus what only a spreadsheet can do (formulas, merged cells,
numbers stored as floats, several sheets, hidden sheets, a zip that claims to hold gigabytes)."""
import datetime
import zipfile
from decimal import Decimal

import pytest

openpyxl = pytest.importorskip("openpyxl")

from openbooks.core import Params, process  # noqa: E402
from openbooks.core.frontends.xlsx import MAX_UNCOMPRESSED_BYTES  # noqa: E402

HEAD = ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
ROWS = [["01/01/2026", "Salary", None, 500.0, 1500.0], ["02/01/2026", "Rent", 200.5, None, 1299.5], ["03/01/2026", "Coffee", 4.5, None, 1295.0]]
P = Params(currency="INR", opening=Decimal("1000.00"))


def workbook(tmp_path, rows=ROWS, head=HEAD, name="s.xlsx", sheets=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Statement"
    for r in [head, *rows]:
        ws.append(r)
    for title, content in (sheets or {}).items():
        extra = wb.create_sheet(title)
        for r in content:
            extra.append(r)
    f = tmp_path / name
    wb.save(f)
    return f


def amounts(doc):
    return [(t["date"], t["direction"], t["amount"]["amount"]) for t in doc["data"]["transactions"]]


EXPECTED = [("2026-01-01", "credit", "500.00"), ("2026-01-02", "debit", "200.50"), ("2026-01-03", "debit", "4.50")]


def test_a_statement_workbook_releases_the_same_data_as_its_csv(tmp_path):
    doc = process(workbook(tmp_path), P)
    assert doc["status"] == "ok" and doc["file"]["detected_format"] == "xlsx" and amounts(doc) == EXPECTED, doc.get("error")


def test_dates_stored_as_real_dates_work(tmp_path):
    rows = [[datetime.datetime(2026, 1, 1), "Salary", None, 500.0, 1500.0], [datetime.date(2026, 1, 2), "Rent", 200.5, None, 1299.5],
            [datetime.datetime(2026, 1, 3, 0, 0, 0), "Coffee", 4.5, None, 1295.0]]
    doc = process(workbook(tmp_path, rows), P)
    assert doc["status"] == "ok" and amounts(doc) == EXPECTED, doc.get("error")


def test_numbers_stored_as_text_work(tmp_path):
    rows = [[a, b, None if c is None else f"{c:.2f}", None if d is None else f"{d:.2f}", f"{e:.2f}"] for a, b, c, d, e in ROWS]
    doc = process(workbook(tmp_path, rows), P)
    assert doc["status"] == "ok" and amounts(doc) == EXPECTED, doc.get("error")


def test_a_stored_value_with_float_noise_is_refused_never_rounded(tmp_path):
    f = workbook(tmp_path, [["01/01/2026", "x", None, 0.3, 1000.3]])
    noisy = tmp_path / "noisy.xlsx"
    with zipfile.ZipFile(f) as src, zipfile.ZipFile(noisy, "w", zipfile.ZIP_DEFLATED) as out:
        for name in src.namelist():
            data = src.read(name)
            if name.startswith("xl/worksheets/sheet"):
                assert b"<v>0.3</v>" in data
                data = data.replace(b"<v>0.3</v>", b"<v>0.30000000000000004</v>")
            out.writestr(name, data)
    doc = process(noisy, P)
    assert doc["status"] == "refused" and not doc["error"].get("internal"), doc.get("data")


@pytest.mark.parametrize("old,new", [(1500.0, 1500.01), (200.5, 200.51), (1295.0, 1294.99), (500.0, 499.99)])
def test_a_tampered_workbook_is_refused(tmp_path, old, new):
    rows = [[new if v == old else v for v in r] for r in ROWS]
    doc = process(workbook(tmp_path, rows), P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_a_formula_in_a_data_row_is_refused_as_not_independent(tmp_path):
    f = workbook(tmp_path)
    wb = openpyxl.load_workbook(f)
    wb.active["E3"] = "=E2-C3+D3"
    wb.save(f)
    doc = process(f, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


def test_a_workbook_with_formulas_but_no_stored_results_is_refused_with_a_reason(tmp_path):
    f = workbook(tmp_path)
    wb = openpyxl.load_workbook(f)
    wb.active["E3"] = "=1+1"
    wb.save(f)
    doc = process(f, P)
    assert doc["status"] == "refused" and ("formula" in doc["error"]["message"])


def test_a_boolean_where_an_amount_belongs_is_refused(tmp_path):
    rows = [["01/01/2026", "x", None, True, 1001.0]]
    doc = process(workbook(tmp_path, rows), P)
    assert doc["status"] == "refused" and not doc["error"].get("internal")


def test_error_values_in_cells_are_refused(tmp_path):
    rows = [["01/01/2026", "x", None, "#DIV/0!", 1500.0]]
    assert process(workbook(tmp_path, rows), P)["status"] == "refused"


def test_two_sheets_that_both_look_like_statements_are_refused_not_merged(tmp_path):
    f = workbook(tmp_path, sheets={"Copy": [HEAD, *ROWS]})
    doc = process(f, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNKNOWN_LAYOUT"


def test_a_notes_sheet_beside_the_statement_is_ignored(tmp_path):
    f = workbook(tmp_path, sheets={"Notes": [["Prepared by", "A B"], ["Remarks", "none"]]})
    doc = process(f, P)
    assert doc["status"] == "ok" and amounts(doc) == EXPECTED


def test_a_workbook_with_no_statement_sheet_is_unknown_layout(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["hello", "world"])
    f = tmp_path / "n.xlsx"
    wb.save(f)
    assert process(f, P)["error"]["code"] == "UNKNOWN_LAYOUT"


def test_an_empty_workbook_is_refused(tmp_path):
    f = tmp_path / "e.xlsx"
    openpyxl.Workbook().save(f)
    doc = process(f, P)
    assert doc["status"] == "refused" and not doc["error"].get("internal")


def test_blank_rows_and_title_rows_around_the_table_are_tolerated_or_refused_cleanly(tmp_path):
    f = workbook(tmp_path)
    wb = openpyxl.load_workbook(f)
    ws = wb.active
    ws.insert_rows(1, 3)
    ws["A1"] = "Account Statement"
    wb.save(f)
    doc = process(f, P)
    assert doc["status"] == "ok" and amounts(doc) == EXPECTED or doc["status"] == "refused" and not doc["error"].get("internal")


def test_merged_cells_do_not_crash_the_engine(tmp_path):
    f = workbook(tmp_path)
    wb = openpyxl.load_workbook(f)
    wb.active.merge_cells("A1:B1")
    wb.save(f)
    doc = process(f, P)
    assert doc["status"] in ("ok", "refused") and not doc.get("error", {}).get("internal")


def test_a_hidden_sheet_is_treated_like_any_other(tmp_path):
    f = workbook(tmp_path, sheets={"Hidden": [HEAD, *ROWS]})
    wb = openpyxl.load_workbook(f)
    wb["Hidden"].sheet_state = "hidden"
    wb.save(f)
    assert process(f, P)["status"] == "refused"


def test_thousands_of_rows_in_a_workbook_release(tmp_path):
    rows, bal = [], 1000.0
    for i in range(5000):
        bal = round(bal + 1.25, 2)
        rows.append([f"{1 + i % 28:02d}/01/2026", f"row {i}", None, 1.25, bal])
    doc = process(workbook(tmp_path, rows), P)
    assert doc["status"] == "ok" and len(doc["data"]["transactions"]) == 5000, doc.get("error")


@pytest.mark.parametrize("payload", [b"", b"PK\x03\x04", b"PK\x03\x04" + b"\x00" * 100, b"not a zip", bytes(range(256)) * 8])
def test_corrupt_workbooks_are_refused(tmp_path, payload):
    f = tmp_path / "bad.xlsx"
    f.write_bytes(payload)
    doc = process(f, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and not doc["error"].get("internal")


def test_a_valid_zip_that_is_not_a_workbook_is_refused(tmp_path):
    f = tmp_path / "z.xlsx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("hello.txt", "hi")
    doc = process(f, P)
    assert doc["status"] == "refused" and not doc["error"].get("internal")


def test_a_workbook_that_claims_to_expand_past_the_limit_is_refused_without_being_unpacked(tmp_path):
    f = workbook(tmp_path)
    bomb = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(f) as src, zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as out:
        for name in src.namelist():
            out.writestr(name, src.read(name))
        with out.open("xl/worksheets/padding.xml", "w", force_zip64=True) as pad:
            for _ in range(MAX_UNCOMPRESSED_BYTES // (1024 * 1024) + 10):
                pad.write(b"0" * (1024 * 1024))
    assert bomb.stat().st_size < 2 * 1024 * 1024
    doc = process(bomb, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and "expands" in doc["error"]["message"]


def test_the_input_workbook_is_never_modified(tmp_path):
    f = workbook(tmp_path)
    before = (f.read_bytes(), f.stat().st_mtime_ns)
    process(f, P)
    assert (f.read_bytes(), f.stat().st_mtime_ns) == before


@pytest.mark.parametrize("has_formula", [False, True])
def test_workbook_source_handles_close_after_release_or_refusal(tmp_path, monkeypatch, has_formula):
    rows = [*ROWS, ["04/01/2026", "Refund", None, "=1+1", 1297.0]] if has_formula else ROWS
    f = workbook(tmp_path, rows)
    open_workbook = openpyxl.load_workbook
    sources = []

    def track_source(source, **kwargs):
        sources.append(source)
        return open_workbook(source, **kwargs)

    monkeypatch.setattr(openpyxl, "load_workbook", track_source)
    assert process(f, P)["status"] == ("refused" if has_formula else "ok")
    assert sources and all(source.closed for source in sources)
    f.unlink()
