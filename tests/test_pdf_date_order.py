"""PDF statements follow the same day/month rule as bank CSV: a forced --date-order wins, a field above 12 proves the
order, and with no proof the default is day-first. Before this, PDF dates ignored --date-order entirely."""
import random

from openbooks.golden import OPEN
from openbooks.golden_docs import _clean_layout, _pdf_rows
from openbooks.pipeline import Params, process
from openbooks.synth import render


def _pdf(tmp_path, n_rows: int, date_fmt: str) -> tuple:
    rows = _pdf_rows(random.Random(7), n_rows)
    lay = _clean_layout(random.Random(3))
    lay.date_fmt = date_fmt
    path = tmp_path / "s.pdf"
    path.write_bytes(render(rows, str(OPEN), lay, random.Random(5), closing=rows[-1][4])[0])
    return path, rows


def _dates(doc) -> list[str]:
    return [t["date"] for t in doc["data"]["transactions"]]


def test_forced_month_first_is_honoured(tmp_path):
    # 10 rows span 1-5 January: written month-first, every date is also a valid (wrong) day-first date.
    path, _ = _pdf(tmp_path, 10, "%m/%d/%Y")
    doc = process(path, Params(currency="INR", date_order="mdy"))
    assert doc["status"] == "ok", doc.get("error")
    assert _dates(doc)[0] == "2026-01-01" and _dates(doc)[-1] == "2026-01-05"


def test_month_first_is_proven_from_a_day_above_12(tmp_path):
    path, _ = _pdf(tmp_path, 30, "%m/%d/%Y")  # reaches 01/15/2026, which only month-first can read
    doc = process(path, Params(currency="INR"))
    assert doc["status"] == "ok", doc.get("error")
    assert _dates(doc)[-1] == "2026-01-15"


def test_unproven_pdf_defaults_to_day_first(tmp_path):
    path, _ = _pdf(tmp_path, 10, "%d/%m/%Y")
    doc = process(path, Params(currency="INR"))
    assert doc["status"] == "ok" and _dates(doc)[-1] == "2026-01-05"


def test_forced_order_that_cannot_read_the_file_refuses(tmp_path):
    path, _ = _pdf(tmp_path, 30, "%d/%m/%Y")  # 15/01/2026 is not a month-first date
    doc = process(path, Params(currency="INR", date_order="mdy"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"
