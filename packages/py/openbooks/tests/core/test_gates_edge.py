"""Edge cases for core balance gates (run_gate) and the refusal rule (_require_balance). Documents current behaviour."""
import pytest

from openbooks.core.errors import Refusal
from openbooks.core.gates import run_gate
from openbooks.core.gates import require_balance as _require_balance


def _m(amount: str, cur: str = "INR") -> dict:
    """Money value as the parsers emit it: {"amount": str, "currency": str}."""
    return {"amount": amount, "currency": cur}


def _statement(bid="b1", account="acc", opening="0", closing="0", derived=False, **extra):
    return {"id": bid, "kind": "statement", "account_id": account, "currency": "INR",
            "opening": _m(opening), "closing": _m(closing), "opening_derived": derived, **extra}


def _txn(tid, bid, direction, amount, balance_after=None):
    row = {"id": tid, "batch_id": bid, "direction": direction, "amount": _m(amount)}
    if balance_after is not None:
        row["balance_after"] = _m(balance_after)
    return row


def _by_rule(out):
    return {a["rule"]: a for a in out}


def test_empty_document_has_no_assertions():
    assert run_gate({"batches": [], "transactions": []}) == []


def test_zero_balance_statement_with_no_rows_passes_its_closing_check():
    out = run_gate({"batches": [_statement()], "transactions": []})
    assert len(out) == 1
    assert out[0]["passed"] is True and out[0]["independent"] is True
    assert out[0]["id"] == "A1"


def test_exact_decimal_arithmetic_has_no_float_drift():
    data = {"batches": [_statement(opening="0.10", closing="0.30")],
            "transactions": [_txn("t1", "b1", "credit", "0.20", balance_after="0.30")]}
    assert _by_rule(run_gate(data))["b1: opening + sum(txns) = closing"]["passed"] is True


def test_debit_reduces_running_balance_to_the_stated_closing():
    data = {"batches": [_statement(opening="10", closing="5")],
            "transactions": [_txn("t1", "b1", "debit", "5", balance_after="5")]}
    checks = _by_rule(run_gate(data))
    assert checks["b1: opening + sum(txns) = closing"]["passed"] is True
    assert checks["b1: running balance ties on every row"]["passed"] is True


def test_mismatched_closing_fails_and_is_reported_not_raised():
    data = {"batches": [_statement(opening="10", closing="99")],
            "transactions": [_txn("t1", "b1", "credit", "5")]}
    first = run_gate(data)[0]
    assert first["passed"] is False
    assert first["computed"] != first["expected"]


def test_account_chain_links_consecutive_statements_only_within_an_account():
    data = {"batches": [_statement("s1", "A", "0", "10"), _statement("s2", "A", "10", "10"),
                        _statement("s3", "B", "7", "7")],
            "transactions": []}
    chain = [a for a in run_gate(data) if " closing = " in a["rule"]]
    assert [a["rule"] for a in chain] == ["s1 closing = s2 opening"]
    assert chain[0]["passed"] is True


def test_unicode_batch_id_is_kept_verbatim_in_rule_text():
    data = {"batches": [_statement(bid="période-é")], "transactions": []}
    assert run_gate(data)[0]["rule"].startswith("période-é: ")


def test_batch_kind_without_a_gate_is_refused_rather_than_released():
    data = {"batches": [{"id": "x", "kind": "exotic"}], "transactions": []}
    with pytest.raises(Refusal) as exc:
        run_gate(data)
    assert exc.value.code == "OUTPUT_INVALID"


def test_provider_gate_runs_only_for_its_kind():
    seen = []

    def gate(batch, tx):
        seen.append((batch["id"], len(tx)))
        yield ("provider rule", "1", "1", True)

    data = {"batches": [_statement(), {"id": "p1", "kind": "payments"}],
            "transactions": [_txn("t1", "p1", "credit", "1")]}
    out = run_gate(data, [("payments", gate)])
    assert seen == [("p1", 1)]
    assert out[-1]["rule"] == "provider rule" and out[-1]["id"] == f"A{len(out)}"


def test_settlement_batch_with_zero_rows_is_gated_not_crashed():
    data = {"batches": [{"id": "s", "kind": "settlement", "currency": "USD", "payout": None}],
            "transactions": []}
    out = run_gate(data)
    assert all(a["passed"] for a in out)
    assert not any(a["independent"] for a in out)


def test_require_balance_accepts_passing_independent_evidence():
    _require_balance([{"rule": "r", "expected": "1", "computed": "1", "passed": True, "independent": True}])


def test_require_balance_refuses_when_no_assertion_is_independent():
    with pytest.raises(Refusal, match="no independent balance evidence") as exc:
        _require_balance([{"rule": "r", "expected": "1", "computed": "1", "passed": True, "independent": False}])
    assert exc.value.code == "BALANCE_MISMATCH"


def test_require_balance_refuses_on_empty_assertion_list():
    with pytest.raises(Refusal, match="no independent balance evidence"):
        _require_balance([])


def test_require_balance_lists_every_failed_rule():
    failed = [{"rule": f"r{i}", "expected": "1", "computed": "2", "passed": False, "independent": True}
              for i in range(3)]
    with pytest.raises(Refusal) as exc:
        _require_balance(failed)
    assert exc.value.message.count("expected 1, got 2") == 3
