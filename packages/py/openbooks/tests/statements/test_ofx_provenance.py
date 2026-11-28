import json
from decimal import Decimal

import pytest

from openbooks.core.errors import Refusal
from openbooks.core.gates import require_balance, run_gate
from openbooks.core.params import Params
from openbooks.core.process import process
from openbooks.core.schema import validate_output
from openbooks.statements.parsers import parse_ofx


def ofx(closing: str) -> str:
    return (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n\n<OFX>\n<BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        "<CURDEF>INR\n<BANKACCTFROM><BANKID>X<ACCTID>123456789<ACCTTYPE>CHECKING</BANKACCTFROM>\n"
        "<BANKTRANLIST>\n"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20240105<TRNAMT>-100.00<FITID>1<NAME>Rent</STMTTRN>\n"
        "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240106<TRNAMT>250.00<FITID>2<NAME>Refund</STMTTRN>\n"
        "</BANKTRANLIST>\n"
        f"<LEDGERBAL><BALAMT>{closing}<DTASOF>20240106</LEDGERBAL>\n"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )


def ofx_file(tmp_path, closing: str):
    path = tmp_path / "statement.ofx"
    path.write_text(ofx(closing), encoding="ascii")
    return path


def opening_assertion(assertions):
    return next(a for a in assertions if a["rule"].endswith("opening + sum(txns) = closing"))


def test_correct_caller_opening_is_refused_never_released_as_independent(tmp_path):
    doc = process(ofx_file(tmp_path, "1150.00"), Params(currency="INR", opening=Decimal("1000.00")))
    assert doc["status"] == "refused"
    assert doc["error"]["code"] == "BALANCE_MISMATCH"


def test_fabricated_opening_that_closes_the_equation_is_refused(tmp_path):
    doc = process(ofx_file(tmp_path, "1384.56"), Params(currency="INR", opening=Decimal("1234.56")))
    assert doc["status"] == "refused"
    assert doc["error"]["code"] == "BALANCE_MISMATCH"


def test_wrong_caller_opening_is_refused_as_balance_mismatch(tmp_path):
    doc = process(ofx_file(tmp_path, "1150.00"), Params(currency="INR", opening=Decimal("1000.01")))
    assert doc["status"] == "refused"
    assert doc["error"]["code"] == "BALANCE_MISMATCH"


def test_a_caller_opening_is_never_reported_as_independently_verified(tmp_path):
    for opening in ("1000.00", "1234.56", "999.99"):
        doc = process(ofx_file(tmp_path, "1150.00"), Params(currency="INR", opening=Decimal(opening)))
        assert doc.get("verification") != "independent"


def test_schema_refuses_an_independent_claim_backed_only_by_a_caller_opening(tmp_path):
    doc = process(ofx_file(tmp_path, "1150.00"), Params(currency="INR", opening=Decimal("1000.00")))
    doc["verification"] = "independent"
    with pytest.raises(Refusal) as exc:
        validate_output(doc)
    assert exc.value.code == "OUTPUT_INVALID"


def test_a_derived_opening_cannot_be_used_as_independent_evidence_for_its_own_equation():
    money = lambda amount: {"amount": amount, "currency": "INR"}
    data = {
        "accounts": [{"id": "a", "number": "1", "currency": "INR"}],
        "batches": [{
            "id": "b1", "kind": "statement", "account_id": "a", "currency": "INR",
            "period_start": "2024-01-05", "period_end": "2024-01-05",
            "opening": money("1000.00"), "closing": money("1150.00"),
            "opening_derived": True, "opening_provenance": "DETERMINISTICALLY_DERIVED",
        }],
        "transactions": [{
            "id": "t1", "batch_id": "b1", "account_id": "a", "date": "2024-01-05",
            "direction": "credit", "amount": money("150.00"), "description": "", "reference": "1",
        }],
    }
    assertions = run_gate(data)
    assert opening_assertion(assertions)["independent"] is False
    with pytest.raises(Refusal, match="no independent balance evidence"):
        require_balance(data, assertions)


def test_refusal_for_caller_opening_survives_json_serialisation(tmp_path):
    doc = process(ofx_file(tmp_path, "1150.00"), Params(currency="INR", opening=Decimal("1000.00")))
    round_tripped = json.loads(json.dumps(doc))
    assert round_tripped["status"] == "refused"
    assert round_tripped["error"]["code"] == "BALANCE_MISMATCH"


def test_parse_ofx_marks_the_supplied_opening_as_caller_supplied():
    data, ev = parse_ofx(ofx("1150.00"), Params(currency="INR", opening=Decimal("1000.00")))
    assert data["batches"][0]["opening_provenance"] == "CALLER_SUPPLIED"
    assert ev["batch-1.opening"]["provenance"] == "CALLER_SUPPLIED"
