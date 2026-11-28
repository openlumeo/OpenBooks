import re
import time
import zipfile
from decimal import Decimal

import pytest

openpyxl = pytest.importorskip("openpyxl")

from openbooks.core import Params, process  # noqa: E402

HEAD = ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
ROWS = [["01/01/2026", "Salary", None, 500.0, 1500.0], ["02/01/2026", "Rent", 200.5, None, 1299.5], ["03/01/2026", "Coffee", 4.5, None, 1295.0]]
P = Params(currency="INR", opening=Decimal("1000.00"), date_order="dmy")
SHEET = "xl/worksheets/sheet1.xml"


def workbook(path, rows=ROWS, pre=(), total=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Statement"
    for r in pre:
        ws.append(r)
    ws.append(HEAD)
    for r in rows:
        ws.append(r)
    if total is not None:
        ws.append(total)
    wb.save(path)
    return path


def rewrite(src, dst, edit, extra=None):
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts[SHEET] = edit(parts[SHEET].decode()).encode()
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return dst


def test_a_formula_above_the_header_is_refused_not_skipped(tmp_path):
    doc = process(workbook(tmp_path / "a.xlsx", pre=[["Memo", "=SUM(D5:D9)"]]), P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


def test_a_total_row_formula_with_a_stored_result_is_refused_not_verified(tmp_path):
    src = workbook(tmp_path / "t.xlsx", total=["Total", None, "=SUM(C2:C4)", "=SUM(D2:D4)", None])
    dst = rewrite(src, tmp_path / "t2.xlsx", lambda s: re.sub(r'(<c r="C5"[^>]*><f>[^<]*</f>)', r"\1<v>204.5</v>", re.sub(r'(<c r="D5"[^>]*><f>[^<]*</f>)', r"\1<v>500</v>", s)))
    doc = process(dst, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


def test_a_data_table_formula_is_refused(tmp_path):
    src = workbook(tmp_path / "d.xlsx")
    dst = rewrite(src, tmp_path / "d2.xlsx", lambda s: re.sub(r'(<c r="E3"[^>]*>)<v>', r'\1<f t="dataTable" ref="E3:E5" dt2D="0" dtr="0" r1="A1"/><v>', s, count=1))
    doc = process(dst, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


def test_a_sparse_sheet_at_the_last_cell_is_refused_before_it_is_read(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Statement"
    for r in [HEAD, *ROWS]:
        ws.append(r)
    ws["XFD1048576"] = "x"
    f = tmp_path / "sparse.xlsx"
    wb.save(f)
    start = time.perf_counter()
    doc = process(f, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT"
    assert time.perf_counter() - start < 10


def test_a_high_ratio_sheet_is_refused_before_it_is_expanded(tmp_path):
    src = workbook(tmp_path / "r.xlsx")
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    bomb = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in parts.items():
            z.writestr(name, data + (b" " * (20 * 1024 * 1024) if name == SHEET else b""))
    assert bomb.stat().st_size < 1024 * 1024
    doc = process(bomb, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and "compresses" in doc["error"]["message"]


def test_a_large_but_honest_sheet_is_not_refused_by_the_ratio_cap(tmp_path):
    rows = [[f"{1 + i % 28:02d}/01/2026", f"row {i}", None, 1.25, round(1000.0 + 1.25 * (i + 1), 2)] for i in range(300)]
    doc = process(workbook(tmp_path / "h.xlsx", rows=rows), P)
    assert doc.get("error", {}).get("message", "") == "" or "compresses" not in doc["error"]["message"]
