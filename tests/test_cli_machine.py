"""CLI contract for wrappers: machine output, exit codes that separate a refusal from an engine fault, atomic output."""
import json
import os
import subprocess
import sys

import pytest

from openbooks_core import cli
from openbooks_core.output import write_atomic

BANK = "Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,Pay,,5.00,1005.00\n"


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "openbooks_core", *args], capture_output=True, text=True)


def bank(tmp_path, text=BANK, name="in.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_a_released_file_exits_0_and_machine_output_is_json_lines(tmp_path):
    r = run_cli("run", bank(tmp_path), "--out", str(tmp_path / "o"), "--currency", "INR", "--opening", "1000.00", "--machine")
    assert r.returncode == 0, r.stderr
    lines = [json.loads(x) for x in r.stdout.splitlines()]
    assert lines[0]["status"] == "ok" and lines[0]["code"] is None and os.path.exists(lines[0]["output"])
    engine = lines[-1]["engine"]
    assert engine["schema_version"] == "openbooks.v1" and "bank_csv.v1" in engine["layouts"] and engine["layout_api"] == 1


def test_a_refused_file_exits_1_with_a_typed_code(tmp_path):
    r = run_cli("run", bank(tmp_path), "--out", str(tmp_path / "o"), "--currency", "INR", "--opening", "1000.01", "--machine")
    assert r.returncode == 1
    first = json.loads(r.stdout.splitlines()[0])
    assert first["status"] == "refused" and first["code"] == "BALANCE_MISMATCH"
    assert json.load(open(first["output"], encoding="utf-8"))["status"] == "refused"


def test_a_missing_input_is_an_engine_fault_not_a_refusal(tmp_path):
    r = run_cli("run", str(tmp_path / "nope.csv"), "--out", str(tmp_path / "o"), "--machine")
    assert r.returncode == 3 and "engine error" in r.stderr and "Traceback" not in r.stderr
    assert r.stdout == "" and not list((tmp_path / "o").glob("*.json"))


def test_a_bad_opening_is_a_usage_error(tmp_path):
    r = run_cli("run", bank(tmp_path), "--opening", "abc")
    assert r.returncode == 2 and "--opening" in r.stderr


def test_missing_library_is_an_engine_fault_in_strict_mode_and_a_refusal_otherwise(tmp_path, monkeypatch):
    from openbooks_core import process

    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4 not a real pdf")

    class Broken:
        def extract(self, path, params):
            raise ImportError("No module named 'fitz'")

    from openbooks_core.registry import default_registry

    reg = default_registry().__class__(frontends={"document": Broken()})
    doc = process(pdf, registry=reg)
    assert doc["status"] == "refused" and doc["error"]["internal"] is True  # 0.1 behaviour, now marked
    from openbooks_core.errors import EngineFault

    with pytest.raises(EngineFault):
        process(pdf, registry=reg, strict=True)


def test_output_is_written_whole_or_not_at_all(tmp_path, monkeypatch):
    target = tmp_path / "x.json"
    write_atomic(target, "old")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        write_atomic(target, "new content")
    assert target.read_text() == "old"  # the previous complete file is untouched
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]  # and no temp file is left behind


def test_default_output_format_is_unchanged(tmp_path, capsys):
    rc = cli.main(["run", bank(tmp_path), "--out", str(tmp_path / "o"), "--currency", "INR", "--opening", "1000.00"])
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith("in.csv: ok  -> ") and out.endswith(".json\n")
