import pytest

from openbooks.core import Params, process
from openbooks.core.errors import Refusal
from openbooks.core.gates import coverage, release_eligible, require_balance, run_gate


def _m(amount: str, cur: str = "INR") -> dict:
    return {"amount": amount, "currency": cur}


def _batch(bid: str, opening: str, closing: str, prov: str = "SOURCE_OBSERVED") -> dict:
    return {"id": bid, "kind": "statement", "account_id": bid, "currency": "INR", "opening": _m(opening),
            "closing": _m(closing), "opening_derived": prov == "DETERMINISTICALLY_DERIVED", "opening_provenance": prov}


def _row(tid: str, bid: str, direction: str, amount: str, after: str | None = None) -> dict:
    row = {"id": tid, "batch_id": bid, "direction": direction, "amount": _m(amount)}
    if after is not None:
        row["balance_after"] = _m(after)
    return row


def _release(data: dict) -> str:
    return require_balance(data, run_gate(data))


def test_caller_opening_with_all_later_balances_printed_is_refused_and_per_transition_independence_is_reported():
    data = {"batches": [_batch("b1", "100", "130", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "b1", "credit", "10", "110"), _row("t2", "b1", "credit", "10", "120"),
                             _row("t3", "b1", "credit", "10", "130")]}
    assert release_eligible(data, run_gate(data)) is False
    assert coverage(data) == {"transactions": 3, "covered_transactions": 3, "independent_covered": 2,
                              "conditional_transactions": 1}
    with pytest.raises(Refusal) as exc:
        _release(data)
    assert exc.value.code == "BALANCE_MISMATCH"
    assert "insufficient independent evidence" in exc.value.message


def test_source_printed_opening_with_printed_balances_is_released():
    data = {"batches": [_batch("b1", "100", "130")],
            "transactions": [_row("t1", "b1", "credit", "10", "110"), _row("t2", "b1", "credit", "10", "120"),
                             _row("t3", "b1", "credit", "10", "130")]}
    assert release_eligible(data, run_gate(data)) is True
    assert coverage(data) == {"transactions": 3, "covered_transactions": 3, "independent_covered": 3,
                              "conditional_transactions": 0}
    assert _release(data) == "independent"


def test_partial_coverage_across_statements_is_refused():
    data = {"batches": [_batch("b1", "100", "110"), _batch("b2", "50", "60", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "b1", "credit", "10", "110"), _row("t2", "b2", "credit", "10")]}
    counts = coverage(data)
    assert counts["transactions"] == 2 and counts["independent_covered"] == 1
    assert release_eligible(data, run_gate(data)) is False
    with pytest.raises(Refusal, match="1 of 2 transactions"):
        _release(data)


def test_partial_coverage_inside_a_statement_is_refused_when_its_first_transition_is_conditional():
    data = {"batches": [_batch("b1", "100", "120", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "b1", "credit", "10", "110"), _row("t2", "b1", "credit", "10", "120")]}
    assert coverage(data)["independent_covered"] == 1
    with pytest.raises(Refusal, match="insufficient independent evidence"):
        _release(data)


def test_duplicated_independent_provider_assertions_do_not_release_a_caller_opening_statement():
    def payments_gate(b, tx):
        return [("payments: receipt matches", "1", "1", True)] * 3

    data = {"batches": [_batch("b1", "100", "100", "CALLER_SUPPLIED"),
                        {"id": "p1", "kind": "payments", "account_id": "b1", "currency": "INR"}],
            "transactions": [_row("t1", "b1", "credit", "10"), _row("t2", "b1", "debit", "10")]}
    assertions = run_gate(data, [("payments", payments_gate)])
    assert sum(a["independent"] for a in assertions) == 1
    assert coverage(data)["independent_covered"] == 0
    assert release_eligible(data, assertions) is False


def test_duplicated_running_balance_assertions_do_not_inflate_coverage():
    data = {"batches": [_batch("b1", "100", "130")],
            "transactions": [_row("t1", "b1", "credit", "10", "110"), _row("t2", "b1", "credit", "10", "120"),
                             _row("t3", "b1", "credit", "10", "130")]}
    assertions = run_gate(data)
    assert coverage(data)["independent_covered"] == 3
    assert len({a["rule"] for a in assertions}) == len(assertions)


MT940_PRINTED = """:20:STMT001
:25:12345678/9876543
:28C:1/1
:60F:C260101INR1000,00
:61:2601050105C500,00NTRFNONREF//BANKREF1
:86:Salary January
:61:2601060106D200,50NTRFINV1001//BR2
:86:Rent
:62F:C260106INR1299,50
"""

CAMT_PRINTED = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt><Id>S1</Id>'
    '<Acct><Id><IBAN>DE89370400440532013000</IBAN></Id><Ccy>EUR</Ccy></Acct>'
    '<Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">1000.00</Amt><CdtDbtInd>CRDT</CdtDbtInd>'
    '<Dt><Dt>2025-01-01</Dt></Dt></Bal>'
    '<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">1150.50</Amt><CdtDbtInd>CRDT</CdtDbtInd>'
    '<Dt><Dt>2025-01-31</Dt></Dt></Bal>'
    '<Ntry><Amt Ccy="EUR">200.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2025-01-05</Dt></BookgDt></Ntry>'
    '<Ntry><Amt Ccy="EUR">49.50</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2025-01-20</Dt></BookgDt></Ntry>'
    "</Stmt></BkToCstmrStmt></Document>"
)


def _process_text(tmp_path, text: str, ext: str) -> dict:
    f = tmp_path / f"in.{ext}"
    f.write_text(text, encoding="utf-8")
    return process(f, Params(date_order="dmy"))


def test_mt940_with_printed_opening_and_closing_is_released(tmp_path):
    out = _process_text(tmp_path, MT940_PRINTED, "sta")
    assert out["status"] == "ok"


def test_mt940_with_tampered_printed_closing_is_refused_on_the_sum(tmp_path):
    out = _process_text(tmp_path, MT940_PRINTED.replace("1299,50", "1299,60"), "sta")
    assert out["status"] == "refused" and out["error"]["code"] == "BALANCE_MISMATCH"
    assert "opening + sum(txns) = closing" in out["error"]["message"]


def test_camt053_with_printed_opening_and_closing_is_released(tmp_path):
    out = _process_text(tmp_path, CAMT_PRINTED, "xml")
    assert out["status"] == "ok"


def test_camt053_with_tampered_printed_closing_is_refused_on_the_sum(tmp_path):
    out = _process_text(tmp_path, CAMT_PRINTED.replace("1150.50", "1150.60"), "xml")
    assert out["status"] == "refused" and out["error"]["code"] == "BALANCE_MISMATCH"
    assert "opening + sum(txns) = closing" in out["error"]["message"]


def test_ofx_batch_with_printed_opening_and_closing_is_released_with_full_coverage():
    data = {"batches": [_batch("b1", "100", "130", "SOURCE_OBSERVED")],
            "transactions": [_row("t1", "b1", "credit", "10"), _row("t2", "b1", "credit", "10"),
                             _row("t3", "b1", "credit", "10")]}
    assert coverage(data)["independent_covered"] == 3
    assert _release(data) == "independent"


def test_ofx_batch_with_printed_opening_and_tampered_closing_is_refused_on_the_sum():
    data = {"batches": [_batch("b1", "100", "131", "SOURCE_OBSERVED")],
            "transactions": [_row("t1", "b1", "credit", "10"), _row("t2", "b1", "credit", "10"),
                             _row("t3", "b1", "credit", "10")]}
    with pytest.raises(Refusal) as exc:
        _release(data)
    assert exc.value.code == "BALANCE_MISMATCH"
    assert "opening + sum(txns) = closing" in exc.value.message
