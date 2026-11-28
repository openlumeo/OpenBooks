import pytest

from openbooks.core.errors import Refusal
from openbooks.core.gates import coverage, require_balance, run_gate, verification_cycles


def _m(amount: str, cur: str = "INR") -> dict:
    return {"amount": amount, "currency": cur}


def _batch(opening: str, closing: str, prov: str = "SOURCE_OBSERVED", closing_prov: str | None = None,
           bid: str = "b1") -> dict:
    batch = {"id": bid, "kind": "statement", "account_id": "a", "currency": "INR", "opening": _m(opening),
             "closing": _m(closing), "opening_derived": prov == "DETERMINISTICALLY_DERIVED", "opening_provenance": prov}
    if closing_prov is not None:
        batch["closing_provenance"] = closing_prov
    return batch


def _row(tid: str, direction: str, amount: str, after: str | None = None, after_prov: str | None = None,
         bid: str = "b1") -> dict:
    row = {"id": tid, "batch_id": bid, "direction": direction, "amount": _m(amount)}
    if after is not None:
        row["balance_after"] = _m(after)
    if after_prov is not None:
        row["balance_after_provenance"] = after_prov
    return row


def _verdict(data: dict) -> str:
    return require_balance(data, run_gate(data))


def _rule(data: dict, suffix: str) -> dict:
    return next(a for a in run_gate(data) if a["rule"].endswith(suffix))


def test_opening_inferred_from_closing_and_transactions_is_refused_without_printed_balances():
    data = {"batches": [_batch("90", "100", "DETERMINISTICALLY_DERIVED")],
            "transactions": [_row("t1", "credit", "10")]}
    with pytest.raises(Refusal, match="no independent balance evidence"):
        _verdict(data)


def test_opening_inferred_from_closing_and_transactions_only_its_first_transition_is_non_independent():
    data = {"batches": [_batch("90", "100", "DETERMINISTICALLY_DERIVED")],
            "transactions": [_row("t1", "credit", "10", "100"), _row("t2", "credit", "0", "100")]}
    assert _rule(data, "opening + sum(txns) = closing")["independent"] is False
    assert coverage(data) == {"transactions": 2, "covered_transactions": 2, "independent_covered": 1,
                              "conditional_transactions": 1}
    with pytest.raises(Refusal, match="insufficient independent evidence"):
        _verdict(data)


def test_closing_computed_from_the_same_transactions_is_not_independent():
    data = {"batches": [_batch("90", "100", closing_prov="DETERMINISTICALLY_DERIVED")],
            "transactions": [_row("t1", "credit", "10")]}
    sum_rule = _rule(data, "opening + sum(txns) = closing")
    assert sum_rule["independent"] is False and sum_rule["provenance"] == "DETERMINISTICALLY_DERIVED"
    with pytest.raises(Refusal, match="no independent balance evidence"):
        _verdict(data)


def test_closing_computed_from_transactions_cannot_back_independent_running_balances_it_does_not_print():
    data = {"batches": [_batch("100", "150", closing_prov="DETERMINISTICALLY_DERIVED")],
            "transactions": [_row("t1", "credit", "50", "150")]}
    assert _rule(data, "opening + sum(txns) = closing")["independent"] is False
    assert _verdict(data) == "independent"


def test_wrong_caller_opening_is_refused_when_the_printed_closing_does_not_tie():
    data = {"batches": [_batch("100", "120", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "credit", "10", "100")]}
    with pytest.raises(Refusal) as exc:
        _verdict(data)
    assert exc.value.code == "BALANCE_MISMATCH"


def test_caller_opening_with_all_later_balances_printed_is_refused_and_reports_per_transition_independence():
    data = {"batches": [_batch("100", "130", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "credit", "10", "110"), _row("t2", "credit", "10", "120"),
                             _row("t3", "credit", "10", "130")]}
    assert _rule(data, "opening + sum(txns) = closing")["provenance"] == "CALLER_SUPPLIED"
    assert _rule(data, "running balance ties on every row")["independent"] is False
    assert coverage(data) == {"transactions": 3, "covered_transactions": 3, "independent_covered": 2,
                              "conditional_transactions": 1}
    with pytest.raises(Refusal, match="insufficient independent evidence"):
        _verdict(data)


def test_caller_opening_with_a_single_printed_transition_is_refused():
    data = {"batches": [_batch("100", "110", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "credit", "10", "110")]}
    with pytest.raises(Refusal, match="no independent balance evidence"):
        _verdict(data)


def test_printed_balances_with_a_missing_transaction_row_are_refused():
    data = {"batches": [_batch("100", "250")],
            "transactions": [_row("t1", "credit", "50", "150"), _row("t3", "credit", "50", "250")]}
    with pytest.raises(Refusal) as exc:
        _verdict(data)
    assert exc.value.code == "BALANCE_MISMATCH"


def test_derived_balances_are_never_recorded_as_printed_independent_evidence():
    data = {"batches": [_batch("100", "130")],
            "transactions": [_row("t1", "credit", "10", "110", "DETERMINISTICALLY_DERIVED"),
                             _row("t2", "credit", "10", "120", "DETERMINISTICALLY_DERIVED"),
                             _row("t3", "credit", "10", "130", "DETERMINISTICALLY_DERIVED")]}
    running = _rule(data, "running balance ties on every row")
    assert running["passed"] is True and running["independent"] is False
    assert running["provenance"] == "DETERMINISTICALLY_DERIVED"


def test_derived_balances_under_a_caller_opening_do_not_upgrade_the_document():
    data = {"batches": [_batch("100", "130", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "credit", "10", "110", "DETERMINISTICALLY_DERIVED"),
                             _row("t2", "credit", "10", "120", "DETERMINISTICALLY_DERIVED"),
                             _row("t3", "credit", "10", "130", "DETERMINISTICALLY_DERIVED")]}
    with pytest.raises(Refusal, match="no independent balance evidence"):
        _verdict(data)
    assert coverage(data)["independent_covered"] == 0


def test_duplicated_gate_assertions_do_not_inflate_the_independent_count():
    def gate(b, tx):
        return [("payments: receipt matches", "1", "1", True), ("payments: receipt matches", "1", "1", True)]

    data = {"batches": [_batch("100", "100"), {"id": "p1", "kind": "payments", "currency": "INR"}],
            "transactions": [_row("t1", "credit", "10"), _row("t2", "debit", "10")]}
    data["batches"][1]["account_id"] = "a"
    once = run_gate(data, [("payments", lambda b, tx: [("payments: receipt matches", "1", "1", True)])])
    twice = run_gate(data, [("payments", gate)])
    assert len(twice) == len(once)
    assert sum(a["independent"] for a in twice) == sum(a["independent"] for a in once)


def test_identical_core_assertions_are_kept_once():
    data = {"batches": [_batch("100", "100")], "transactions": [_row("t1", "credit", "0")]}
    rules = [a["rule"] for a in run_gate(data)]
    assert len(rules) == len(set(rules))


def test_derived_opening_feeding_its_own_running_balance_is_a_cycle_and_is_refused():
    data = {"batches": [_batch("90", "100", "DETERMINISTICALLY_DERIVED")],
            "transactions": [_row("t1", "credit", "10", "100")]}
    assert verification_cycles(data) == ("b1.opening", "b1.rows")
    with pytest.raises(Refusal):
        _verdict(data)


def test_partially_printed_running_balances_are_refused_as_a_partial_chain():
    data = {"batches": [_batch("100", "130")],
            "transactions": [_row("t1", "credit", "10", "110"), _row("t2", "credit", "10"),
                             _row("t3", "credit", "10", "130")]}
    with pytest.raises(Refusal, match="partial"):
        run_gate(data)


def test_coverage_counts_independent_transitions_per_transaction():
    data = {"batches": [_batch("100", "130", "CALLER_SUPPLIED")],
            "transactions": [_row("t1", "credit", "10", "110"), _row("t2", "credit", "10", "120"),
                             _row("t3", "credit", "10", "130")]}
    assert coverage(data) == {"transactions": 3, "covered_transactions": 3, "independent_covered": 2,
                              "conditional_transactions": 1}


def test_wrong_first_transaction_is_refused_even_when_later_printed_balances_are_valid():
    data = {"batches": [_batch("100", "130")],
            "transactions": [_row("t1", "credit", "20", "110"), _row("t2", "credit", "10", "120"),
                             _row("t3", "credit", "10", "130")]}
    with pytest.raises(Refusal) as exc:
        _verdict(data)
    assert exc.value.code == "BALANCE_MISMATCH"


@pytest.mark.xfail(strict=True, reason="contract decision: opening+closing with no row balances cannot see offsetting row errors")
def test_offsetting_row_errors_with_observed_endpoints_are_not_financially_correct():
    data = {"batches": [_batch("100", "100")],
            "transactions": [_row("t1", "credit", "10"), _row("t2", "debit", "10")]}
    with pytest.raises(Refusal):
        _verdict(data)
