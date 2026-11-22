"""Run staging, execution and cleanup, plus parse_params and safe_name edge cases not covered by test_security."""
import asyncio
import io
from decimal import Decimal
from types import SimpleNamespace

import pytest
from openbooks.pipeline import Params

from openbooks_server import runs
from openbooks_server.app import _run_params, _sse, _stage_uploads
from openbooks_server.runs import Run, parse_params, safe_name


class BrokenStream:
    def read(self, _n: int = -1) -> bytes:
        raise OSError("client went away")


@pytest.mark.parametrize("name, expected", [
    ("CON.csv", "_CON.csv"),
    ("nul", "_nul"),
    ("com1.txt", "_com1.txt"),
    ("LPT9", "_LPT9"),
    ("CONSOLE.csv", "CONSOLE.csv"),
    ("lpt0.csv", "lpt0.csv"),
])
def test_safe_name_prefixes_windows_device_names(name, expected):
    assert safe_name(name, 0) == expected


def test_safe_name_keeps_unicode_letters_and_replaces_null_bytes():
    assert safe_name("фактура.csv", 0) == "фактура.csv"
    assert safe_name("a\x00b.csv", 0) == "a_b.csv"


@pytest.mark.parametrize("name", ["", None, "   ", "..", "/"])
def test_safe_name_falls_back_to_index_for_unusable_names(name):
    assert safe_name(name, 4) == "file-4"


def test_safe_name_bounds_a_huge_name_to_the_limit():
    assert len(safe_name("n" * 10_000, 0)) == runs.MAX_NAME_CHARS


def test_parse_params_without_input_returns_engine_defaults():
    assert parse_params(None) == Params()
    assert parse_params({}) == Params()


def test_parse_params_normalises_currency_and_clears_empty_values():
    parsed = parse_params({"currency": "usd", "account": "", "date_order": ""})

    assert (parsed.currency, parsed.account, parsed.date_order) == ("USD", None, None)
    assert parse_params({"currency": ""}).currency is None


@pytest.mark.parametrize("raw, expected", [
    ("1,000.50", Decimal("1000.50")),
    (" -12 ", Decimal("-12")),
    ("", None),
    (None, None),
])
def test_parse_params_reads_opening_balance_as_exact_decimal(raw, expected):
    assert parse_params({"opening": raw}).opening == expected


def test_parse_params_accepts_very_long_amounts_as_exact_decimals():
    assert parse_params({"opening": "9" * 500}).opening == Decimal("9" * 500)


def test_parse_params_inherits_unspecified_fields_from_the_base():
    base = Params(currency="EUR", ocr=False, date_order="dmy")

    parsed = parse_params({"model": True}, base)

    assert (parsed.currency, parsed.ocr, parsed.date_order, parsed.model) == ("EUR", False, "dmy", True)


@pytest.mark.parametrize("raw", [{"currency": "U\x00D"}, {"currency": "ÉUR"}, {"date_order": "mdy "}])
def test_parse_params_rejects_currency_and_order_outside_the_allowed_set(raw):
    with pytest.raises(ValueError):
        parse_params(raw)


def test_run_stage_records_name_size_and_defaults_empty_names():
    run = Run()
    try:
        run.stage("", io.BytesIO(b"abc"))

        staged = run.files[0]
        assert (staged.name, staged.size, staged.path.name) == ("file-0", 3, "file-0")
    finally:
        run.cleanup()


def test_run_cleanup_removes_the_temporary_directory():
    run = Run()
    run.stage("a.csv", io.BytesIO(b"x"))

    run.cleanup()

    assert not run.root.exists()


def test_run_cleanup_is_safe_to_call_twice():
    run = Run()
    run.cleanup()
    run.cleanup()

    assert not run.root.exists()


def test_failed_upload_removes_the_run_directory_and_reraises():
    run = Run()
    upload = SimpleNamespace(filename="a.csv", file=BrokenStream())

    with pytest.raises(OSError):
        asyncio.run(_stage_uploads(run, [upload]))

    assert not run.root.exists()


def test_execute_emits_events_in_order_and_counts_outcomes(monkeypatch):
    run = Run()
    run.stage("a.csv", io.BytesIO(b"x"))
    run.stage("b.pdf", io.BytesIO(b"y"))
    docs = iter([{"status": "ok", "file": {"method": "pdf_text"}}, {"status": "refused", "file": {}}])

    def fake_process(path, params, on_stage):
        on_stage("detect")
        return next(docs)

    monkeypatch.setattr(runs, "process", fake_process)
    events: list[tuple[str, dict]] = []
    observed: list[tuple] = []

    run.execute(Params(), {}, lambda event, data: events.append((event, data)),
                lambda method, suffix, stages: observed.append((method, suffix)))

    assert [name for name, _ in events] == ["file.started", "file.stage", "file.done",
                                            "file.started", "file.stage", "file.done", "run.done"]
    assert events[-1][1] == {"released": 1, "refused": 1}
    assert observed == [("pdf_text", ".csv"), (None, ".pdf")]
    assert not run.root.exists()


def test_execute_stops_early_when_the_client_cancelled(monkeypatch):
    run = Run()
    run.stage("a.csv", io.BytesIO(b"x"))
    run.cancelled.set()
    monkeypatch.setattr(runs, "process", lambda *a, **k: pytest.fail("must not process a cancelled run"))
    events: list = []

    run.execute(Params(), {}, lambda event, data: events.append(event))

    assert events == [] and not run.root.exists()


def test_execute_removes_the_directory_even_when_the_engine_raises(monkeypatch):
    run = Run()
    run.stage("a.csv", io.BytesIO(b"x"))

    def exploding(*_args, **_kwargs):
        raise RuntimeError("engine fault")

    monkeypatch.setattr(runs, "process", exploding)

    with pytest.raises(RuntimeError):
        run.execute(Params(), {}, lambda event, data: None)
    assert not run.root.exists()


def test_run_params_applies_per_file_overrides_on_top_of_the_base():
    base, per_file = _run_params(2, '{"currency": "usd"}', '{"1": {"currency": "eur"}}')

    assert base.currency == "USD"
    assert per_file[1].currency == "EUR"
    assert 0 not in per_file


@pytest.mark.parametrize("file_count, params, file_params", [
    (0, None, None),
    (21, None, None),
    (1, "{not json", None),
    (1, None, "[]"),
    (1, None, "0"),
    (2, None, '{"5": {}}'),
    (1, None, "nope"),
])
def test_run_params_rejects_bad_counts_and_fields_with_422(file_count, params, file_params):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as refused:
        _run_params(file_count, params, file_params)

    assert refused.value.status_code == 422


def test_run_params_treats_empty_file_params_as_no_overrides():
    _, per_file = _run_params(1, None, "")

    assert per_file == {}


def test_sse_frames_keep_unicode_and_use_compact_json():
    frame = _sse("file.done", {"name": "日本.csv", "n": 1}).decode()

    assert frame == 'event: file.done\ndata: {"name":"日本.csv","n":1}\n\n'
