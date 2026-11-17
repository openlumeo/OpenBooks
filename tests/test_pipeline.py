from decimal import Decimal

import pytest

from openbooks.golden import build
from openbooks.pipeline import Params, Refusal, dumps, fx_check, main, process, run_eval, to_dec


@pytest.fixture(scope="module")
def golden(tmp_path_factory):
    root = tmp_path_factory.mktemp("golden")
    build(root, n_random=150)
    return root


def test_golden_set_all_codes_match_and_zero_false_accepts(golden, capsys):
    assert run_eval(golden) == 0
    assert "false_accepts=0" in capsys.readouterr().out


def test_ok_output_has_evidence_and_decimal_strings(golden):
    doc = process(golden / "ok_bank_csv" / "in.csv", Params("INR", Decimal("1000.00")))
    assert doc["status"] == "ok"
    for t in doc["data"]["transactions"]:
        assert f"{t['id']}.amount" in doc["evidence"]
        assert isinstance(t["amount"]["amount"], str)
    assert all(a["passed"] for a in doc["assertions"])


def test_output_is_byte_identical_across_runs(golden):
    src = golden / "ok_mt940" / "in.sta"
    assert dumps(process(src)) == dumps(process(src))


def test_refusal_has_no_data(golden):
    doc = process(golden / "bad_mt940_closing" / "in.sta")
    assert doc["status"] == "refused" and doc["data"] is None
    assert doc["error"]["code"] == "BALANCE_MISMATCH" and len(doc["error"]["file_sha256"]) == 64


@pytest.mark.parametrize("raw,want", [("1,00,000.50", "100000.50"), ("(5.00)", "-5.00"), ("5.00", "5.00")])
def test_to_dec_ok(raw, want):
    assert to_dec(raw, "t") == Decimal(want)


def test_to_dec_dr_suffix_is_negative():
    assert to_dec("10.00 Dr", "t", dr_cr=True) == Decimal("-10.00")


@pytest.mark.parametrize("raw", ["1.000,50", "abc", "1,2,3", ""])
def test_to_dec_refuses_ambiguous(raw):
    with pytest.raises(Refusal):
        to_dec(raw, "t")


def test_fx_tolerance():
    assert fx_check(Decimal("100"), Decimal("83.254"), Decimal("8325.40"))
    assert not fx_check(Decimal("100"), Decimal("83.254"), Decimal("8325.50"))


def test_cli_dedupes_by_sha(golden, tmp_path, capsys):
    src = str(golden / "ok_stripe" / "in.csv")
    out = tmp_path / "out"
    assert main(["run", src, "--out", str(out)]) == 0
    assert main(["run", src, "--out", str(out)]) == 0
    assert len(list(out.glob("*.json"))) == 1
