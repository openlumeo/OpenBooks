import time
import zipfile
from decimal import Decimal

import pytest

openpyxl = pytest.importorskip("openpyxl")

from openbooks.core import Params, process  # noqa: E402
from openbooks.core.frontends import xlsx  # noqa: E402
from openbooks.core.frontends.xlsx import XlsxBudget  # noqa: E402

HEAD = ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
ROWS = [["01/01/2026", "Salary", None, 500.0, 1500.0], ["02/01/2026", "Rent", 200.5, None, 1299.5], ["03/01/2026", "Coffee", 4.5, None, 1295.0]]
P = Params(currency="INR", opening=Decimal("1000.00"), date_order="dmy")
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
COLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def col_letter(index: int) -> str:
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = COLS[rem] + out
    return out


def text_cell(ref: str, value: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'


def number_cell(ref: str, value: float) -> str:
    text = str(int(value)) if float(value).is_integer() else repr(value)
    return f'<c r="{ref}"><v>{text}</v></c>'


def statement_xml(rows=ROWS, dimension="A1:E4") -> str:
    body = ['<row r="1">' + "".join(text_cell(f"{COLS[i]}1", h) for i, h in enumerate(HEAD)) + "</row>"]
    for n, row in enumerate(rows, start=2):
        cells = []
        for i, v in enumerate(row):
            if v is None:
                continue
            ref = f"{COLS[i]}{n}"
            cells.append(number_cell(ref, v) if isinstance(v, float) else text_cell(ref, str(v)))
        body.append(f'<row r="{n}">' + "".join(cells) + "</row>")
    return f'<worksheet {NS}><dimension ref="{dimension}"/><sheetData>{"".join(body)}</sheetData></worksheet>'


def dense_xml(cells: int, dimension: str) -> str:
    per_row = 1000
    rows = []
    for n in range(1, cells // per_row + 1):
        rows.append(f'<row r="{n}">' + "".join(number_cell(f"{col_letter(c)}{n}", 1.5) for c in range(1, per_row + 1)) + "</row>")
    return f'<worksheet {NS}><dimension ref="{dimension}"/><sheetData>{"".join(rows)}</sheetData></worksheet>'


def book(path, sheets, hidden=()):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, _ in sheets:
        wb.create_sheet(title)
    for title in hidden:
        wb[title].sheet_state = "hidden"
    wb.save(path)
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    for k, (_, xml) in enumerate(sheets, start=1):
        if xml is not None:
            parts[f"xl/worksheets/sheet{k}.xml"] = xml.encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return path


FRONTEND_CODES = {"UNSUPPORTED_INPUT", "UNKNOWN_LAYOUT", "PARSE_ERROR"}


def reached_layout(doc) -> bool:
    return doc["status"] == "ok" or doc["error"]["code"] not in FRONTEND_CODES


def refused_code(doc) -> str:
    assert doc["status"] == "refused", doc.get("data")
    return doc["error"]["code"]


def test_a_dense_sheet_past_the_default_cell_budget_is_refused_by_counting_its_cells(tmp_path):
    f = book(tmp_path / "dense.xlsx", [("Data", dense_xml(2_100_000, "A1:AMJ2100"))])
    start = time.perf_counter()
    doc = process(f, P)
    assert refused_code(doc) == "UNSUPPORTED_INPUT" and "cells" in doc["error"]["message"]
    assert time.perf_counter() - start < 60


def test_a_lying_dimension_tag_does_not_hide_a_dense_sheet(tmp_path):
    f = book(tmp_path / "lie.xlsx", [("Data", dense_xml(2_100_000, "A1:A1"))])
    assert refused_code(process(f, P)) == "UNSUPPORTED_INPUT"


def test_a_sparse_sheet_with_a_huge_declared_dimension_is_read_by_its_actual_cells(tmp_path):
    f = book(tmp_path / "sparse.xlsx", [("Statement", statement_xml(dimension="A1:XFD1048576"))])
    start = time.perf_counter()
    doc = process(f, P)
    assert reached_layout(doc), doc.get("error")
    assert time.perf_counter() - start < 30


def test_a_row_index_of_1048576_is_refused_before_the_sheet_is_materialised(tmp_path):
    xml = statement_xml().replace("</sheetData>", '<row r="1048576"><c r="A1048576"><v>1</v></c></row></sheetData>')
    f = book(tmp_path / "row.xlsx", [("Statement", xml)])
    start = time.perf_counter()
    assert refused_code(process(f, P)) == "UNSUPPORTED_INPUT"
    assert time.perf_counter() - start < 10


def test_a_column_beyond_xfd_is_refused(tmp_path):
    xml = statement_xml().replace("</sheetData>", '<row r="2"><c r="XFE2"><v>1</v></c></row></sheetData>')
    f = book(tmp_path / "col.xlsx", [("Statement", xml)])
    assert refused_code(process(f, P)) == "UNSUPPORTED_INPUT"


def test_a_workbook_with_more_zip_entries_than_budget_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(xlsx, "DEFAULT_BUDGET", XlsxBudget(max_zip_entries=3))
    f = book(tmp_path / "entries.xlsx", [("Statement", statement_xml())])
    assert refused_code(process(f, P)) == "UNSUPPORTED_INPUT"


def test_sheet_bytes_are_capped_by_the_budget_even_when_declared_size_is_honest(tmp_path, monkeypatch):
    monkeypatch.setattr(xlsx, "DEFAULT_BUDGET", XlsxBudget(max_member_bytes=2_000))
    rows = [[f"{1 + i % 28:02d}/01/2026", f"row {i}", None, 1.25, 1000.0 + i] for i in range(300)]
    f = book(tmp_path / "bytes.xlsx", [("Statement", statement_xml(rows=rows))])
    assert refused_code(process(f, P)) == "UNSUPPORTED_INPUT"


def test_a_hidden_matching_sheet_is_refused_not_dropped(tmp_path):
    f = book(tmp_path / "hidden.xlsx", [("Statement", statement_xml()), ("Other", None)], hidden=("Statement",))
    assert refused_code(process(f, P)) == "UNKNOWN_LAYOUT"


def test_a_hidden_non_matching_sheet_still_counts_against_budget_and_does_not_block_a_match(tmp_path):
    f = book(tmp_path / "side.xlsx", [("Statement", statement_xml()), ("Notes", f'<worksheet {NS}><dimension ref="A1"/><sheetData/></worksheet>')], hidden=("Notes",))
    assert reached_layout(process(f, P))


def test_budget_overrides_apply_and_defaults_accept_a_thousand_row_statement(tmp_path, monkeypatch):
    rows = [[f"{1 + i % 28:02d}/01/2026", f"row {i}", None, 1.25, round(1000.0 + 1.25 * (i + 1), 2)] for i in range(1000)]
    f = book(tmp_path / "k.xlsx", [("Statement", statement_xml(rows=rows))])
    assert reached_layout(process(f, P))
    monkeypatch.setattr(xlsx, "MAX_TOTAL_CELLS", 100)
    assert refused_code(process(f, P)) == "UNSUPPORTED_INPUT"


def test_the_default_budget_is_a_frozen_dataclass_with_documented_values():
    budget = xlsx.DEFAULT_BUDGET
    assert isinstance(budget, XlsxBudget)
    assert budget.max_total_cells == 2_000_000
    assert budget.max_row_index == 1_048_576
    assert budget.max_column_index == 16_384
    with pytest.raises(Exception):
        budget.max_total_cells = 1


def test_cell_budget_is_inclusive_at_the_limit_for_explicit_budgets(tmp_path):
    from openbooks.core.errors import Refusal
    from openbooks.core.frontends.xlsx import XlsxBudget, parse_xlsx

    f = book(tmp_path / "edge.xlsx", [("Data", dense_xml(3_000, "A1:AMJ3"))])
    with pytest.raises(Refusal) as over:
        parse_xlsx(f, P, budget=XlsxBudget(max_total_cells=2_999))
    assert over.value.code == "UNSUPPORTED_INPUT"
    with pytest.raises(Refusal) as at_limit:
        parse_xlsx(f, P, budget=XlsxBudget(max_total_cells=3_000))
    assert at_limit.value.code == "UNKNOWN_LAYOUT"


def test_lowered_defaults_are_two_million_cells_and_256_mib_uncompressed():
    from openbooks.core.frontends.xlsx import DEFAULT_BUDGET

    assert DEFAULT_BUDGET.max_total_cells == 2_000_000
    assert DEFAULT_BUDGET.max_uncompressed_bytes == 256 * 1024 * 1024


def test_a_column_past_xfd_stops_the_scan_at_the_first_chunk_that_shows_it(tmp_path, monkeypatch):
    xml = dense_xml(200_000, "A1:AMJ200").replace('<row r="1">', '<row r="1"><c r="XFE1"><v>1</v></c>', 1)
    f = book(tmp_path / "col.xlsx", [("Data", xml)])
    chunk_bytes = 4096
    reads = []
    original = xlsx._member_chunks

    def counting(*args, **kwargs):
        for chunk in original(*args, **kwargs):
            reads.append(len(chunk))
            yield chunk

    monkeypatch.setattr(xlsx, "_member_chunks", counting)
    assert len(xml.encode()) > 100 * chunk_bytes
    with pytest.raises(xlsx.Refusal) as refusal:
        xlsx.parse_xlsx(f, P, budget=XlsxBudget(chunk_bytes=chunk_bytes))
    assert refusal.value.code == "UNSUPPORTED_INPUT" and "column" in str(refusal.value)
    assert len(reads) < 10
