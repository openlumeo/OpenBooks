"""process(..., on_stage=cb) reports each pipeline stage it completes, in order."""
from decimal import Decimal

from openbooks_lab.golden import OPEN, bank_csv, bank_rows
from openbooks.pipeline import Params, process
import random


def _run(tmp_path, name, text, params):
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    seen: list[str] = []
    doc = process(f, params, on_stage=seen.append)
    return doc, seen


def test_released_csv_reports_every_stage(tmp_path):
    rows = bank_rows(random.Random(3), 5)
    doc, seen = _run(tmp_path, "s.csv", bank_csv(rows), Params(currency="INR", opening=OPEN))
    assert doc["status"] == "ok"
    assert seen == ["detect", "parse", "normalise", "balance", "validate"]


def test_unknown_layout_stops_before_detect_completes(tmp_path):
    doc, seen = _run(tmp_path, "x.csv", "foo,bar\n1,2\n", Params())
    assert doc["error"]["code"] == "UNKNOWN_LAYOUT"
    assert seen == []


def test_balance_mismatch_stops_after_normalise(tmp_path):
    rows = bank_rows(random.Random(3), 5)
    rows[2][4] = f"{Decimal(rows[2][4]) + Decimal('0.01'):.2f}"
    doc, seen = _run(tmp_path, "t.csv", bank_csv(rows), Params(currency="INR", opening=OPEN))
    assert doc["error"]["code"] == "BALANCE_MISMATCH"
    assert seen == ["detect", "parse", "normalise"]


def test_callback_is_optional(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text(bank_csv(bank_rows(random.Random(3), 3)), encoding="utf-8")
    assert process(f, Params(currency="INR", opening=OPEN))["status"] == "ok"
