""".xlsx front end: finds the one sheet that matches a known layout and hands its rows to that layout's parser.

Cross-family by nature (bank, gateway and tax exports all arrive as workbooks), so it lives in core and resolves the
parser through the registry. Moved verbatim from parsers_extra.py.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..builders import TOTAL_LABELS
from ..errors import EngineFault, Refusal
from ..params import Params
from ..registry import Registry, default_registry, find_header

MAX_SHEETS, MAX_ROWS = 20, 100_000
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # a workbook is a zip: a few KB can claim to hold gigabytes


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


def _sheet_rows(ws) -> list[list[str]]:
    rows = []
    for k, r in enumerate(ws.iter_rows(values_only=True)):
        if k >= MAX_ROWS:
            raise Refusal("UNSUPPORTED_INPUT", f"sheet {ws.title!r} has more than {MAX_ROWS} rows")
        rows.append([_to_str(c) for c in r])
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


@contextmanager
def _open_workbook(path: Path, *, data_only: bool):
    try:
        import openpyxl
    except ImportError as e:
        raise EngineFault("reading .xlsx needs openpyxl: pip install 'openbooks-core[xlsx]'") from e

    # Own the source handle even if row iteration stops with a partially read ZIP entry.
    with ExitStack() as stack:
        try:
            source = stack.enter_context(path.open("rb"))
            book = openpyxl.load_workbook(source, data_only=data_only, read_only=True)
        except Exception:
            raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook") from None
        stack.callback(book.close)
        yield book


def _formula_scan(formulas, cached, header_row: int) -> bool:
    """Returns True if the total row holds formulas. Formulas in data rows, or without a stored result, are refused."""
    total_formula = False
    for k, (a, b) in enumerate(zip(formulas.iter_rows(values_only=True), cached.iter_rows(values_only=True))):
        if k <= header_row:
            continue
        label = [c for c in a if c not in (None, "")]
        in_total = bool(label) and isinstance(label[0], str) and label[0].strip().lower().rstrip(":") in TOTAL_LABELS
        for x, y in zip(a, b):
            if isinstance(x, str) and x.startswith("="):
                if y is None:
                    raise Refusal("PARSE_ERROR", "workbook has formulas without stored results; open and save it in Excel first")
                if not in_total:
                    raise Refusal("PARSE_ERROR", "formulas in data rows are not independent evidence; export values")
                total_formula = True
    return total_formula


def parse_xlsx(path: Path, p: Params, registry: Registry | None = None):
    import zipfile

    try:
        with zipfile.ZipFile(path) as z:  # declared sizes only: nothing is decompressed to find out
            declared = sum(i.file_size for i in z.infolist())
    except Exception:
        raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook") from None
    if declared > MAX_UNCOMPRESSED_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", f"workbook expands to more than {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB")
    with _open_workbook(path, data_only=True) as cached:
        hits = []
        for ws in cached.worksheets[:MAX_SHEETS]:
            rows = _sheet_rows(ws)
            hit = find_header(rows)
            if hit:
                hits.append((ws.title, rows, hit))
        if len(hits) != 1:
            raise Refusal("UNKNOWN_LAYOUT", "no sheet matches a known layout" if not hits else "more than one sheet matches a layout")
        title, rows, (hi, layout, hs) = hits[0]
        with _open_workbook(path, data_only=False) as formulas:
            total_formula = _formula_scan(formulas[title], cached[title], hi)
    data, ev = (registry or default_registry()).run_layout(layout, (rows, hi, hs), p)
    if total_formula:
        for b in data["batches"]:
            b["totals_are_formulas"] = True
    return data, ev, "xlsx", layout
