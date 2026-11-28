""".xlsx front end: finds the one sheet that matches a known layout and hands its rows to that layout's parser.

Cross-family by nature (bank, gateway and tax exports all arrive as workbooks), so it lives in core and resolves the
parser through the registry. Before openpyxl materialises anything, every sheet is tallied from bounded reads of its
XML, so the budget is enforced on what the file actually contains rather than on what its headers declare.
"""
from __future__ import annotations

import re
import zipfile
import zlib
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree

from ..builders import TOTAL_LABELS
from ..errors import EngineFault, Refusal
from ..params import Params
from ..registry import Registry, default_registry, find_header

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
TAG_OVERLAP = 4096
UNBOUNDED = 10**9
CELL_OPEN = re.compile(rb"<c[\s>/]")
ROW_OPEN = re.compile(rb"<row[\s>/]")
CELL_REF = re.compile(rb'<c\b[^>]*?\br="([A-Za-z]+)(\d+)"')
ROW_REF = re.compile(rb'<row\b[^>]*?\br="(\d+)"')


@dataclass(frozen=True)
class XlsxBudget:
    max_sheets: int = 20
    max_rows: int = 2_000_000
    max_total_cells: int = 2_000_000
    max_row_index: int = 1_048_576
    max_column_index: int = 16_384
    max_empty_row_gap: int = 100_000
    max_zip_entries: int = 5_000
    max_uncompressed_bytes: int = 256 * 1024 * 1024
    max_member_bytes: int = 256 * 1024 * 1024
    max_part_bytes: int = 4 * 1024 * 1024
    max_ratio: int = 100
    ratio_floor_bytes: int = 1024 * 1024
    chunk_bytes: int = 1024 * 1024


DEFAULT_BUDGET = XlsxBudget()
MAX_SHEETS = DEFAULT_BUDGET.max_sheets
MAX_ROWS = DEFAULT_BUDGET.max_rows
MAX_TOTAL_CELLS = DEFAULT_BUDGET.max_total_cells
MAX_UNCOMPRESSED_BYTES = DEFAULT_BUDGET.max_uncompressed_bytes
MAX_RATIO = DEFAULT_BUDGET.max_ratio
MAX_RATIO_FLOOR_BYTES = DEFAULT_BUDGET.ratio_floor_bytes


def _active_budget() -> XlsxBudget:
    return replace(
        DEFAULT_BUDGET,
        max_sheets=MAX_SHEETS,
        max_rows=MAX_ROWS,
        max_total_cells=MAX_TOTAL_CELLS,
        max_uncompressed_bytes=MAX_UNCOMPRESSED_BYTES,
        max_ratio=MAX_RATIO,
        ratio_floor_bytes=MAX_RATIO_FLOOR_BYTES,
    )


@dataclass
class _Tally:
    cells: int = 0
    rows: int = 0
    max_row: int = 0
    max_col: int = 0


@dataclass(frozen=True)
class _SheetScan:
    state: str
    tally: _Tally


def _to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == datetime.min.time() else v.isoformat(" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        raise Refusal("PARSE_ERROR", "boolean cell where a value was expected")
    if isinstance(v, float):
        return format(Decimal(repr(v)), "f")
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v).strip()


def _bounded_int(raw: bytes) -> int:
    return int(raw) if len(raw) <= 9 else UNBOUNDED


def _column_index(letters: bytes) -> int:
    if len(letters) > 3:
        return UNBOUNDED
    value = 0
    for code in letters.upper():
        value = value * 26 + code - 64
    return value


def _count_cells_and_rows(head: bytes, tally: _Tally, title: str) -> None:
    cells = CELL_OPEN.findall(head)
    tally.cells += len(cells)
    tally.rows += len(ROW_OPEN.findall(head))
    refs = CELL_REF.findall(head)
    if len(refs) != len(cells):
        raise Refusal("UNSUPPORTED_INPUT", f"sheet {title!r} has a cell without a reference")
    if refs:
        tally.max_col = max(tally.max_col, max(_column_index(column) for column in {column for column, _ in refs}))
        tally.max_row = max(tally.max_row, max(_bounded_int(row) for row in {row for _, row in refs}))
    row_refs = ROW_REF.findall(head)
    if row_refs:
        tally.max_row = max(tally.max_row, max(_bounded_int(row) for row in set(row_refs)))


def _check_running(title: str, tally: _Tally, prior_cells: int, limits: XlsxBudget) -> None:
    if tally.rows > limits.max_rows:
        raise Refusal("UNSUPPORTED_INPUT", f"sheet {title!r} has more than {limits.max_rows} rows")
    if prior_cells + tally.cells > limits.max_total_cells:
        raise Refusal("UNSUPPORTED_INPUT", f"sheet {title!r} takes the workbook past {limits.max_total_cells} cells")
    if tally.max_row > limits.max_row_index:
        raise Refusal("UNSUPPORTED_INPUT", f"sheet {title!r} uses row {tally.max_row}, beyond {limits.max_row_index}")
    if tally.max_col > limits.max_column_index:
        raise Refusal("UNSUPPORTED_INPUT", f"sheet {title!r} uses column {tally.max_col}, beyond {limits.max_column_index}")
    if tally.max_row * tally.max_col > limits.max_total_cells:
        raise Refusal("UNSUPPORTED_INPUT", f"sheet {title!r} used range is {tally.max_row} x {tally.max_col}, more than {limits.max_total_cells} cells")


def _settle(buf: bytes, final: bool) -> int:
    if final:
        return len(buf)
    limit = max(len(buf) - TAG_OVERLAP, 0)
    cut = buf.rfind(b"<", 0, limit)
    return cut if cut > 0 else limit


def _check_sheet(title: str, tally: _Tally, limits: XlsxBudget) -> None:
    gap = tally.max_row - tally.rows
    if gap > limits.max_empty_row_gap:
        raise Refusal("UNSUPPORTED_INPUT", f"sheet {title!r} has {gap} empty rows between data rows; refusing sparse layout")


def _check_read(label: str, info: zipfile.ZipInfo, read_total: int, limits: XlsxBudget, remaining: int) -> None:
    if read_total > min(limits.max_member_bytes, remaining):
        raise Refusal("UNSUPPORTED_INPUT", f"{label!r} expands beyond its read budget; refusing before expansion completes")
    if read_total > limits.ratio_floor_bytes and read_total > limits.max_ratio * max(info.compress_size, 1):
        raise Refusal("UNSUPPORTED_INPUT", f"{info.filename!r} compresses beyond {limits.max_ratio}:1; refusing before expansion")


def _read_chunk(stream, size: int, label: str) -> bytes:
    try:
        return stream.read(size)
    except (zipfile.BadZipFile, zlib.error, EOFError, OSError, RuntimeError, ValueError):
        raise Refusal("UNSUPPORTED_INPUT", f"unreadable workbook: {label!r}") from None


def _member(z: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
    try:
        return z.getinfo(name)
    except KeyError:
        raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook") from None


def _member_chunks(z: zipfile.ZipFile, info: zipfile.ZipInfo, label: str, limits: XlsxBudget, remaining: int) -> Iterator[bytes]:
    read_total = 0
    try:
        stream = z.open(info)
    except (zipfile.BadZipFile, zlib.error, RuntimeError, ValueError, OSError):
        raise Refusal("UNSUPPORTED_INPUT", f"unreadable workbook: {label!r}") from None
    with stream:
        while True:
            chunk = _read_chunk(stream, limits.chunk_bytes, label)
            read_total += len(chunk)
            _check_read(label, info, read_total, limits, remaining)
            yield chunk
            if not chunk:
                return


def _tally_member(z: zipfile.ZipFile, info: zipfile.ZipInfo, title: str, limits: XlsxBudget, remaining: int, prior_cells: int) -> tuple[_Tally, int]:
    tally = _Tally()
    tail = b""
    read = 0
    for chunk in _member_chunks(z, info, title, limits, remaining):
        read += len(chunk)
        buf = tail + chunk
        settled = _settle(buf, not chunk)
        head = buf[:settled]
        _count_cells_and_rows(head, tally, title)
        _check_running(title, tally, prior_cells, limits)
        tail = buf[settled:]
    return tally, read


def _read_part(z: zipfile.ZipFile, name: str, limits: XlsxBudget) -> bytes:
    info = _member(z, name)
    return b"".join(_member_chunks(z, info, name, limits, limits.max_part_bytes))


def _sheet_path(target: str) -> str:
    return target.lstrip("/") if target.startswith("/") else f"xl/{target}"


def _workbook_sheets(z: zipfile.ZipFile, limits: XlsxBudget) -> list[tuple[str, str, str]]:
    try:
        book = ElementTree.fromstring(_read_part(z, "xl/workbook.xml", limits))
        rels = ElementTree.fromstring(_read_part(z, "xl/_rels/workbook.xml.rels", limits))
    except ElementTree.ParseError:
        raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook") from None
    targets = {rel.get("Id"): rel.get("Target", "") for rel in rels.iter(PACKAGE_REL_NS + "Relationship")}
    return [
        (node.get("name", ""), node.get("state", "visible"), _sheet_path(targets.get(node.get(DOC_REL_NS + "id"), "")))
        for node in book.iter(MAIN_NS + "sheet")
    ]


def _scan_workbook(z: zipfile.ZipFile, limits: XlsxBudget) -> dict[str, _SheetScan]:
    sheets = _workbook_sheets(z, limits)
    if len(sheets) > limits.max_sheets:
        raise Refusal("UNSUPPORTED_INPUT", f"workbook has more than {limits.max_sheets} sheets")
    remaining = limits.max_uncompressed_bytes
    if "xl/sharedStrings.xml" in z.namelist():
        shared = z.getinfo("xl/sharedStrings.xml")
        remaining -= sum(len(chunk) for chunk in _member_chunks(z, shared, shared.filename, limits, remaining))
    total_cells = 0
    scans: dict[str, _SheetScan] = {}
    for title, state, path in sheets:
        tally, read = _tally_member(z, _member(z, path), title, limits, remaining, total_cells)
        remaining -= read
        _check_sheet(title, tally, limits)
        total_cells += tally.cells
        if total_cells > limits.max_total_cells:
            raise Refusal("UNSUPPORTED_INPUT", f"workbook has more than {limits.max_total_cells} cells")
        scans[title] = _SheetScan(state, tally)
    return scans


@contextmanager
def _open_workbook(path: Path, *, data_only: bool):
    try:
        import openpyxl
    except ImportError as e:
        raise EngineFault("reading .xlsx needs openpyxl: pip install openpyxl") from e

    with ExitStack() as stack:
        try:
            source = stack.enter_context(path.open("rb"))
            book = openpyxl.load_workbook(source, data_only=data_only, read_only=True)
        except Exception:
            raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook") from None
        stack.callback(book.close)
        yield book


def _check_expansion(members: list, limits: XlsxBudget) -> None:
    declared = 0
    for member in members:
        declared += member.file_size
        if declared > limits.max_uncompressed_bytes:
            raise Refusal("UNSUPPORTED_INPUT", f"workbook expands to more than {limits.max_uncompressed_bytes // (1024 * 1024)} MB")
        if member.file_size > limits.ratio_floor_bytes and member.file_size > limits.max_ratio * max(member.compress_size, 1):
            raise Refusal("UNSUPPORTED_INPUT", f"{member.filename!r} compresses beyond {limits.max_ratio}:1; refusing before expansion")


def _bounded_rows(ws: Worksheet, tally: _Tally) -> Iterable[tuple]:
    if tally.cells == 0:
        return []
    return ws.iter_rows(max_row=tally.max_row, max_col=tally.max_col, values_only=True)


def _sheet_rows(ws: Worksheet, tally: _Tally) -> list[list[str]]:
    rows = [[_to_str(c) for c in r] for r in _bounded_rows(ws, tally)]
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def _is_formula(value: object) -> bool:
    from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

    if isinstance(value, str):
        return value.startswith("=")
    return isinstance(value, (ArrayFormula, DataTableFormula))


def _refuse_formulas(formulas: Worksheet, tally: _Tally) -> None:
    for row in _bounded_rows(formulas, tally):
        for cell in row:
            if _is_formula(cell):
                raise Refusal("PARSE_ERROR", "workbook holds formulas; their stored results are not independent evidence, export values")


def parse_xlsx(path: Path, p: Params, registry: Registry | None = None, budget: XlsxBudget | None = None):
    limits = budget or _active_budget()
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook") from None
    with z:
        members = z.infolist()
        if len(members) > limits.max_zip_entries:
            raise Refusal("UNSUPPORTED_INPUT", f"workbook has more than {limits.max_zip_entries} zip entries")
        _check_expansion(members, limits)
        scans = _scan_workbook(z, limits)
    with _open_workbook(path, data_only=True) as cached:
        hits = []
        for ws in cached.worksheets:
            scan = scans.get(ws.title)
            if scan is None:
                raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook")
            rows = _sheet_rows(ws, scan.tally)
            hit = find_header(rows)
            if hit:
                hits.append((ws.title, rows, hit, scan.state))
        if len(hits) != 1:
            raise Refusal("UNKNOWN_LAYOUT", "no sheet matches a known layout" if not hits else "more than one sheet matches a layout")
        title, rows, (hi, layout, hs), state = hits[0]
        if state != "visible":
            raise Refusal("UNKNOWN_LAYOUT", f"matched sheet {title!r} is {state}; unhide it or export it as a visible sheet")
        with _open_workbook(path, data_only=False) as formulas:
            _refuse_formulas(formulas[title], scans[title].tally)
    return (registry or default_registry()).run_layout(layout, (rows, hi, hs), p) + ("xlsx", layout)
