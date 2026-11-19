"""What the command line does with wrong, missing, hostile and odd input. Exit codes are the contract:
0 released | 1 refused | 2 a bad flag or argument | 3 the engine could not run (including an input it cannot open)."""
import importlib.util
import json

import pytest

from openbooks.core.cli import main

needs_a_provider = pytest.mark.skipif(importlib.util.find_spec("openbooks.statements") is None,
                                      reason="releasing a bank statement needs openbooks.statements registered")
needs_xlsx = pytest.mark.skipif(importlib.util.find_spec("openpyxl") is None, reason="needs openpyxl")
GOOD = "Date,Description,Debit,Credit,Balance\n02/01/2026,Pay,100.00,,900.00\n03/01/2026,Dep,,50.00,950.00\n"
RUN = ["--currency", "INR", "--opening", "1000.00"]


@pytest.fixture
def good(tmp_path):
    f = tmp_path / "good.csv"
    f.write_text(GOOD, encoding="utf-8")
    return f


def code(argv, capsys):
    rc = main(argv)
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


# ---- bad arguments are exit 2, unreadable inputs exit 3, and neither leaves a trace -----------------------------------------------------------------

def test_a_missing_file_is_an_engine_problem_never_a_refusal(tmp_path, capsys):
    rc, _, err = code(["run", str(tmp_path / "nope.csv"), "--out", str(tmp_path / "o")], capsys)
    assert rc == 3 and "engine error" in err and "no such file" in err and "nope.csv" in err and "Traceback" not in err
    assert not (tmp_path / "o").exists()


def test_a_directory_instead_of_a_file_is_reported_as_one(tmp_path, capsys):
    rc, _, err = code(["run", str(tmp_path), "--out", str(tmp_path / "o")], capsys)
    assert rc == 3 and "is a directory" in err


def test_one_bad_path_stops_the_whole_batch_before_anything_is_written(good, tmp_path, capsys):
    out = tmp_path / "o"
    rc, stdout, err = code(["run", str(good), str(tmp_path / "typo.csv"), "--out", str(out), *RUN, "--machine"], capsys)
    assert rc == 3 and stdout == "" and "typo.csv" in err
    assert not out.exists(), "a batch must not be half-processed because its last name had a typo"


def test_every_bad_path_is_named(good, tmp_path, capsys):
    rc, _, err = code(["run", str(tmp_path / "a.csv"), str(good), str(tmp_path / "b.csv")], capsys)
    assert rc == 3 and "a.csv" in err and "b.csv" in err


def test_no_files_at_all_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as e:
        main(["run"])
    assert e.value.code == 2


def test_an_unknown_command_is_a_usage_error():
    with pytest.raises(SystemExit) as e:
        main(["frobnicate"])
    assert e.value.code == 2


@pytest.mark.parametrize("bad", ["abc", "NaN", "nan", "Infinity", "-Infinity", "1e400", "1e3", "0x10", "1,000.00", "1 000", "--5", "", " ", "1.2.3", "٣٤٥", "1000.00."])
def test_an_opening_balance_must_be_a_plain_number(good, bad, capsys):
    with pytest.raises(SystemExit) as e:
        main(["run", str(good), "--currency", "INR", "--opening", bad])
    assert e.value.code == 2
    assert "--opening" in capsys.readouterr().err


@pytest.mark.parametrize("ok", ["1000", "1000.00", "+1000.00", "-5.25", ".5", "5.", " 1000.00 ", "0", "0.00", "123456789012345678.99"])
def test_plain_numbers_are_accepted_as_opening_balances(good, ok, tmp_path, capsys):
    rc, _, _ = code(["run", str(good), "--currency", "INR", "--opening", ok, "--out", str(tmp_path / "o")], capsys)
    assert rc in (0, 1)  # released, or refused because that opening does not tie: never a usage error


@pytest.mark.parametrize("bad", ["rupees", "", "IN", "INRR", "I1R", "₹", "12 ", "in r"])
def test_a_currency_must_be_a_three_letter_code(good, bad, capsys):
    with pytest.raises(SystemExit) as e:
        main(["run", str(good), "--currency", bad, "--opening", "1000.00"])
    assert e.value.code == 2
    assert "--currency" in capsys.readouterr().err


@needs_a_provider
@pytest.mark.parametrize("given", ["inr", "Inr", " INR "])
def test_a_currency_is_normalised_to_upper_case(good, given, tmp_path, capsys):
    out = tmp_path / "o"
    rc, _, _ = code(["run", str(good), "--currency", given, "--opening", "1000.00", "--out", str(out)], capsys)
    (path,) = out.glob("*.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert rc == 0 and doc["data"]["transactions"][0]["amount"]["currency"] == "INR"


def test_a_date_order_must_be_dmy_or_mdy(good):
    with pytest.raises(SystemExit) as e:
        main(["run", str(good), "--date-order", "ymd"])
    assert e.value.code == 2


# ---- eval, report and link: same contract -------------------------------------------------------------------------------

def test_eval_of_a_missing_folder_is_exit_3_without_a_traceback(tmp_path, capsys):
    rc, _, err = code(["eval", str(tmp_path / "none")], capsys)
    assert rc == 3 and "Traceback" not in err


def test_report_of_a_missing_folder_or_a_file_is_exit_3(good, tmp_path, capsys):
    assert code(["report", str(tmp_path / "none")], capsys)[0] == 3
    assert code(["report", str(good)], capsys)[0] == 3


def test_report_of_a_folder_with_nothing_to_read_is_exit_2_not_a_clean_zero_of_zero(tmp_path, capsys):
    folder = tmp_path / "empty"
    folder.mkdir()
    (folder / "notes.docx").write_bytes(b"x")
    rc, _, err = code(["report", str(folder), "--out", str(tmp_path / "o")], capsys)
    assert rc == 2 and "no supported files" in err
    assert not (tmp_path / "o").exists()


@needs_a_provider
def test_report_exit_code_follows_the_documented_contract(good, tmp_path, capsys):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.csv").write_text(GOOD, encoding="utf-8")
    assert code(["report", str(folder), "--out", str(tmp_path / "r1"), *RUN], capsys)[0] == 0  # everything released
    (folder / "b.csv").write_text(GOOD.replace("900.00", "901.00"), encoding="utf-8")
    assert code(["report", str(folder), "--out", str(tmp_path / "r2"), *RUN], capsys)[0] == 1  # one refused
    report = json.loads((tmp_path / "r2" / "report.json").read_text(encoding="utf-8"))
    assert report["released"] == 1 and report["refused"] == {"BALANCE_MISMATCH": 1}


def test_report_with_a_malformed_params_file_is_a_usage_error(tmp_path, capsys):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.csv").write_text(GOOD, encoding="utf-8")
    (folder / "params.json").write_text("{not json", encoding="utf-8")
    rc, _, err = code(["report", str(folder), "--out", str(tmp_path / "o")], capsys)
    assert rc == 2 and "malformed" in err


def test_report_with_a_bad_opening_in_params_json_is_a_usage_error(tmp_path, capsys):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.csv").write_text(GOOD, encoding="utf-8")
    (folder / "params.json").write_text(json.dumps({"a.csv": {"opening": "lots"}}), encoding="utf-8")
    assert code(["report", str(folder), "--out", str(tmp_path / "o")], capsys)[0] == 2


@needs_a_provider
def test_report_lists_a_repeated_file_as_a_duplicate_once(tmp_path, capsys):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.csv").write_text(GOOD, encoding="utf-8")
    (folder / "b.csv").write_text(GOOD, encoding="utf-8")
    code(["report", str(folder), "--out", str(tmp_path / "o"), *RUN], capsys)
    rows = json.loads((tmp_path / "o" / "report.json").read_text(encoding="utf-8"))["files"]
    assert [r["status"] for r in rows] == ["ok", "duplicate"]


def test_link_without_a_linker_is_a_usage_error(good, tmp_path, monkeypatch, capsys):
    from openbooks.core import cli

    class NoLinker:
        def linker(self):
            return None

    monkeypatch.setattr(cli, "default_registry", lambda: NoLinker())
    rc, _, err = code(["link", str(good)], capsys)
    assert rc == 2 and "no linker" in err


def test_link_given_a_statement_instead_of_a_document_is_exit_2_not_a_traceback(good, monkeypatch, capsys):
    from openbooks.core import cli

    class Linker:
        def run_link(self, files, out):
            json.loads(open(files[0], encoding="utf-8").read())  # what a real linker does first
            return 0

    class Reg:
        def linker(self):
            return Linker()

    monkeypatch.setattr(cli, "default_registry", lambda: Reg())
    rc, _, err = code(["link", str(good)], capsys)
    assert rc == 2 and "openbooks.v1" in err and "Traceback" not in err


# ---- what the engine does with hostile bytes: a typed refusal, exit 1, never a crash ------------------------------------

HOSTILE = {
    "empty.csv": b"",
    "one_byte.csv": b"x",
    "nul_bytes.csv": b"Date,Description\x00,Debit\n",
    "random.csv": bytes(range(256)) * 16,
    "header_only.csv": b"Date,Description,Debit,Credit,Balance\n",
    "only_newlines.csv": b"\n" * 5000,
    "very_long_line.csv": b"Date," + b"a" * 2_000_000 + b"\n",
    "utf16.csv": "Date,Description,Debit,Credit,Balance\n".encode("utf-16"),
    "latin1_bytes.csv": b"Date,Description,Debit,Credit,Balance\n02/01/2026,Caf\xe9,100.00,,900.00\n",
    "random.pdf": bytes(range(256)) * 16,
    "random.xlsx": bytes(range(256)) * 16,
    "random.png": bytes(range(256)) * 16,
    "random.sta": bytes(range(256)) * 16,
    "random.ofx": bytes(range(256)) * 16,
    "notes.txt": b"hello",
    "x.json": b"{}",
    "x.docx": b"PK\x03\x04",
    "noext": b"Date,Description,Debit,Credit,Balance\n",
}


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_hostile_files_are_refused_with_a_typed_code_and_never_crash(tmp_path, name, capsys):
    needs = {".xlsx": "openpyxl", ".pdf": "pypdfium2", ".png": "PIL"}.get(name[name.rfind("."):])
    if needs and importlib.util.find_spec(needs) is None:
        pytest.skip(f"needs {needs}; without it the file is an engine problem with an install hint, which has its own test")
    f = tmp_path / name
    f.write_bytes(HOSTILE[name])
    rc, out, err = code(["run", str(f), *RUN, "--out", str(tmp_path / "o"), "--machine"], capsys)
    line = json.loads(out.splitlines()[0])
    assert rc in (0, 1) and "Traceback" not in err
    if line["status"] == "refused":
        assert line["code"] in {"UNKNOWN_LAYOUT", "PARSE_ERROR", "UNSUPPORTED_INPUT", "BALANCE_MISMATCH", "OUTPUT_INVALID"}
        assert not line.get("internal"), f"{name}: an internal error means the engine crashed on this file"
    else:
        doc = json.loads(open(line["output"], encoding="utf-8").read())
        assert doc["status"] == "ok" and name == "latin1_bytes.csv"


def test_a_file_over_the_size_limit_is_refused_without_being_read(tmp_path, capsys):
    f = tmp_path / "big.csv"
    with open(f, "wb") as fh:
        fh.seek(20 * 1024 * 1024)
        fh.write(b"x")  # 20 MB + 1 byte, sparse
    rc, out, _ = code(["run", str(f), "--machine", "--out", str(tmp_path / "o")], capsys)
    assert rc == 1 and json.loads(out.splitlines()[0])["code"] == "UNSUPPORTED_INPUT"


@needs_a_provider
def test_an_upper_case_extension_is_read_like_a_lower_case_one(tmp_path, capsys):
    f = tmp_path / "STATEMENT.CSV"
    f.write_text(GOOD, encoding="utf-8")
    assert code(["run", str(f), *RUN, "--out", str(tmp_path / "o")], capsys)[0] == 0


@needs_a_provider
def test_paths_with_spaces_and_unicode_work(tmp_path, capsys):
    d = tmp_path / "my statements é ₹"
    d.mkdir()
    f = d / "jan 2026 (final).csv"
    f.write_text(GOOD, encoding="utf-8")
    rc, out, _ = code(["run", str(f), *RUN, "--out", str(d / "out dir"), "--machine"], capsys)
    assert rc == 0 and json.loads(out.splitlines()[0])["file"] == "jan 2026 (final).csv"


# ---- the same input twice, and files that must never be touched ---------------------------------------------------------

def test_the_same_file_gives_byte_identical_output_every_time(good, tmp_path, capsys):
    outputs = []
    for i in range(3):
        out = tmp_path / f"o{i}"
        code(["run", str(good), *RUN, "--out", str(out)], capsys)
        (path,) = out.glob("*.json")
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1] == outputs[2]


def test_the_input_file_is_never_modified(good, tmp_path, capsys):
    before = (good.read_bytes(), good.stat().st_mtime_ns)
    code(["run", str(good), *RUN, "--out", str(tmp_path / "o")], capsys)
    assert (good.read_bytes(), good.stat().st_mtime_ns) == before


def test_the_output_folder_holds_only_finished_json_files(good, tmp_path, capsys):
    out = tmp_path / "o"
    code(["run", str(good), *RUN, "--out", str(out)], capsys)
    assert [p.suffix for p in out.iterdir()] == [".json"], "no temp files left behind"


def test_the_output_name_is_the_hash_of_the_input_and_differs_per_content(good, tmp_path, capsys):
    other = tmp_path / "other.csv"
    other.write_text(GOOD.replace("100.00", "100.01"), encoding="utf-8")
    out = tmp_path / "o"
    code(["run", str(good), str(other), *RUN, "--out", str(out)], capsys)
    assert len(list(out.glob("*.json"))) == 2


@needs_a_provider
def test_a_refusal_and_a_release_in_one_batch_exit_1_but_both_are_written(good, tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text(GOOD.replace("900.00", "901.00"), encoding="utf-8")
    rc, out, _ = code(["run", str(good), str(bad), *RUN, "--out", str(tmp_path / "o"), "--machine"], capsys)
    lines = [json.loads(x) for x in out.splitlines() if '"engine"' not in x]
    assert rc == 1 and [x["status"] for x in lines] == ["ok", "refused"]
    assert len(list((tmp_path / "o").glob("*.json"))) == 2


def test_the_output_folder_being_a_file_is_an_engine_problem_not_a_refusal(good, tmp_path, capsys):
    blocker = tmp_path / "o"
    blocker.write_text("i am a file", encoding="utf-8")
    rc, _, err = code(["run", str(good), *RUN, "--out", str(blocker)], capsys)
    assert rc == 3 and "engine error" in err


def test_engine_info_lists_every_known_layout_and_the_contract(capsys):
    rc, out, _ = code(["engine-info"], capsys)
    info = json.loads(out)
    assert rc == 0 and info["schema_version"] == "openbooks.v1"
    ids = {x["id"] for x in info["known_layouts"]}
    assert ids == {"stripe_balance.v1", "razorpay_settlement.v1", "paypal_activity.v1", "wise_statement.v1", "form_1099b.v1", "tds_26as.v1",
                   "ais.v1", "fira.v1", "bank_csv.v1", "trial_balance.v1", "ofx.v1", "mt940.v1"}, ids


def test_a_workbook_without_openpyxl_is_an_engine_problem_with_an_install_hint(tmp_path, monkeypatch, capsys):
    import sys

    monkeypatch.setitem(sys.modules, "openpyxl", None)  # makes `import openpyxl` raise ImportError
    f = tmp_path / "book.xlsx"
    import zipfile

    with zipfile.ZipFile(f, "w") as z:  # a real zip, so the size check passes and openpyxl is actually needed
        z.writestr("xl/workbook.xml", "<workbook/>")
    rc, _, err = code(["run", str(f), "--out", str(tmp_path / "o")], capsys)
    assert rc == 3 and "pip install openpyxl" in err and "Traceback" not in err
    assert "EngineFault: EngineFault" not in err  # one prefix, not the fault wrapped in itself
