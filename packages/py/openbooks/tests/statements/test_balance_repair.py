from __future__ import annotations

import random
from dataclasses import replace
from decimal import Decimal

import pytest

from openbooks.statements.balance_repair import Repair, Row, repair_by_running_balance

CASE_COUNT = 200
SEED = 20260601
DIGIT_CONFUSIONS = {"0": "8", "1": "7", "2": "7", "3": "8", "5": "6", "6": "8", "7": "1"}
FIELDS = ("debit", "credit", "balance")


def _money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def _consistent_statement(rng: random.Random) -> tuple[str, str, list[Row]]:
    opening_cents = rng.randint(100_000, 9_000_000)
    running = opening_cents
    rows: list[Row] = []
    for _ in range(rng.randint(3, 8)):
        amount = rng.randint(100, 99_999)
        if rng.random() < 0.5:
            running -= amount
            rows.append(Row(debit=_money(amount), credit=None, balance=_money(running)))
        else:
            running += amount
            rows.append(Row(debit=None, credit=_money(amount), balance=_money(running)))
    return _money(opening_cents), _money(running), rows


def _inject_digit_confusion(rng: random.Random, rows: list[Row]) -> tuple[list[Row], Repair]:
    candidates = [
        (index, field)
        for index, row in enumerate(rows)
        for field in FIELDS
        if getattr(row, field) is not None
        and any(char in DIGIT_CONFUSIONS for char in getattr(row, field))
    ]
    index, field = rng.choice(candidates)
    clean = getattr(rows[index], field)
    position = rng.choice([p for p, char in enumerate(clean) if char in DIGIT_CONFUSIONS])
    corrupted = clean[:position] + DIGIT_CONFUSIONS[clean[position]] + clean[position + 1 :]
    damaged = [*rows[:index], replace(rows[index], **{field: corrupted}), *rows[index + 1 :]]
    return damaged, Repair(index, field, corrupted, clean)


def _build_cases() -> list[tuple[str, str, list[Row], Repair]]:
    rng = random.Random(SEED)
    cases = []
    for _ in range(CASE_COUNT):
        opening, closing, clean_rows = _consistent_statement(rng)
        damaged_rows, expected = _inject_digit_confusion(rng, clean_rows)
        cases.append((opening, closing, damaged_rows, expected))
    return cases


CASES = _build_cases()


@pytest.mark.parametrize("case_index", range(CASE_COUNT))
def test_random_digit_confusion_never_yields_wrong_repair(case_index: int) -> None:
    opening, closing, damaged_rows, expected = CASES[case_index]
    repair = repair_by_running_balance(opening, closing, damaged_rows)
    assert repair is None or repair == expected


def test_at_least_half_of_random_digit_confusions_are_repaired() -> None:
    repaired = sum(
        repair_by_running_balance(opening, closing, rows) is not None
        for opening, closing, rows, _ in CASES
    )
    assert repaired >= CASE_COUNT // 2


def test_consistent_statement_returns_none() -> None:
    rows = [
        Row(debit="10.00", credit=None, balance="90.00"),
        Row(debit=None, credit="5.00", balance="95.00"),
    ]
    assert repair_by_running_balance("100.00", "95.00", rows) is None


def test_unique_digit_confusion_is_repaired_to_original_digit() -> None:
    rows = [Row(debit="70.00", credit=None, balance="90.00")]
    assert repair_by_running_balance("100.00", "90.00", rows) == Repair(
        0, "debit", "70.00", "10.00"
    )


def test_decimal_shift_is_repaired_to_original_amount() -> None:
    rows = [
        Row(debit=None, credit="500.00", balance="500.00"),
        Row(debit="123.40", credit=None, balance="487.66"),
    ]
    repair = repair_by_running_balance("0.00", "487.66", rows)
    assert repair is not None
    assert (repair.row_index, repair.field) == (1, "debit")
    assert Decimal(repair.repaired) == Decimal("12.34")


def test_no_candidate_fix_returns_none() -> None:
    rows = [Row(debit=None, credit="100.00", balance=None)]
    assert repair_by_running_balance("0.00", "999.00", rows) is None


def test_ambiguous_two_candidate_fixes_return_none() -> None:
    rows = [
        Row(debit=None, credit="8.00", balance=None),
        Row(debit=None, credit="8.00", balance=None),
    ]
    assert repair_by_running_balance("0.00", "8.00", rows) is None


@pytest.mark.parametrize("max_edits", [0, 2, 3])
def test_max_edits_other_than_one_raises_value_error(max_edits: int) -> None:
    rows = [Row(debit="70.00", credit=None, balance="90.00")]
    with pytest.raises(ValueError):
        repair_by_running_balance("100.00", "90.00", rows, max_edits=max_edits)


@pytest.mark.parametrize(
    ("opening", "closing", "debit"),
    [
        ("abc", "0.00", None),
        ("0.00", "not-a-number", None),
        ("0.00", "0.00", "x.yz"),
        ("NaN", "0.00", None),
    ],
)
def test_invalid_decimal_string_raises_value_error(
    opening: str, closing: str, debit: str | None
) -> None:
    rows = [Row(debit=debit, credit=None, balance="0.00")]
    with pytest.raises(ValueError):
        repair_by_running_balance(opening, closing, rows)


def test_input_rows_are_not_mutated_by_repair() -> None:
    rows = [Row(debit="70.00", credit=None, balance="90.00")]
    snapshot = list(rows)
    repair_by_running_balance("100.00", "90.00", rows)
    assert rows == snapshot
    assert len(rows) == 1
