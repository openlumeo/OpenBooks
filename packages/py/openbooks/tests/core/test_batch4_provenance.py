import pytest

from openbooks.core.errors import Refusal
from openbooks.core.gates import require_balance, run_gate
from openbooks.core.iso4217 import exponent_of


def _m(amount: str, cur: str = "INR") -> dict:
    return {"amount": amount, "currency": cur}


def _batch(opening: str, closing: str, prov: str = "SOURCE_OBSERVED", derived: bool = False, bid: str = "b1") -> dict:
    return {"id": bid, "kind": "statement", "account_id": "a", "currency": "INR", "opening": _m(opening),
            "closing": _m(closing), "opening_derived": derived, "opening_provenance": prov}


def _row(tid: str, direction: str, amount: str, after: str | None = None, bid: str = "b1") -> dict:
    row = {"id": tid, "batch_id": bid, "direction": direction, "amount": _m(amount)}
    if after is not None:
        row["balance_after"] = _m(after)
    return row


def _verification(data: dict) -> str:
    return require_balance(data, run_gate(data))


def test_caller_opening_with_matching_running_balances_is_refused():
    data = {"batches": [_batch("100", "150", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "credit", "50", "150")]}
    with pytest.raises(Refusal, match="no independent balance evidence"):
        _verification(data)


def test_running_balance_inherits_the_observed_provenance_of_an_observed_opening():
    data = {"batches": [_batch("100", "150")], "transactions": [_row("t1", "credit", "50", "150")]}
    running = next(a for a in run_gate(data) if a["rule"].endswith("running balance ties on every row"))
    assert running["independent"] is True and running["provenance"] == "SOURCE_OBSERVED"


def test_offsetting_row_errors_are_refused_when_running_balances_are_printed():
    data = {"batches": [_batch("100", "100")],
            "transactions": [_row("t1", "credit", "10", "90"), _row("t2", "debit", "10", "100")]}
    with pytest.raises(Refusal) as exc:
        _verification(data)
    assert exc.value.code == "BALANCE_MISMATCH"


def test_offsetting_row_errors_under_a_caller_opening_are_never_independent():
    data = {"batches": [_batch("100", "100", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "credit", "10"), _row("t2", "debit", "10")]}
    with pytest.raises(Refusal):
        _verification(data)


@pytest.mark.xfail(strict=True, reason="contract decision: opening+closing with no row balances cannot see offsetting row errors")
def test_offsetting_row_errors_with_observed_endpoints_are_not_financially_correct():
    data = {"batches": [_batch("100", "100")],
            "transactions": [_row("t1", "credit", "10"), _row("t2", "debit", "10")]}
    with pytest.raises(Refusal):
        require_balance(data, run_gate(data))


def test_derived_opening_verified_only_by_its_own_running_balance_is_refused():
    data = {"batches": [_batch("90", "100", "DETERMINISTICALLY_DERIVED", derived=True)],
            "transactions": [_row("t1", "credit", "10", "100")]}
    with pytest.raises(Refusal, match="no independent balance evidence"):
        _verification(data)


def test_circular_dependencies_reports_the_nodes_on_a_cycle_only():
    from openbooks.core.provenance import circular_dependencies

    assert circular_dependencies({"a": {"b"}, "b": {"a"}, "c": {"a"}}) == ("a", "b")
    assert circular_dependencies({"a": {"b"}, "b": set()}) == ()


def test_a_derived_opening_that_feeds_its_own_running_balance_is_detected_as_circular():
    data = {"batches": [_batch("90", "100", "DETERMINISTICALLY_DERIVED", derived=True)],
            "transactions": [_row("t1", "credit", "10", "100")]}
    from openbooks.core.gates import verification_cycles

    assert verification_cycles(data) == ("b1.opening", "b1.rows")


@pytest.mark.parametrize("code", ["MGA", "MRU"])
def test_madagascar_and_mauritania_currencies_have_two_minor_units(code):
    assert exponent_of(code) == 2
