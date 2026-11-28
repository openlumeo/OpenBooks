from __future__ import annotations

import random
from decimal import Decimal, localcontext

import pytest

import balance_repair_reference as reference
from openbooks.statements import balance_repair as indexed

SEED = 20260611
RANDOM_CASES = 400
LARGE_CASES = 60
DIGIT_SWAPS = {"0": "8", "8": "0", "1": "7", "7": "1", "5": "6", "6": "5", "2": "7", "3": "8"}
FIELDS = ("debit", "credit", "balance")


def _money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def _random_amount(rng: random.Random) -> str:
    kind = rng.random()
    if kind < 0.55:
        return _money(rng.randint(0, 9_999_999))
    if kind < 0.65:
        return str(rng.randint(0, 999))
    if kind < 0.75:
        return f"{rng.randint(0, 10**15)}.{rng.randint(0, 99):02d}"
    if kind < 0.85:
        return f"{rng.randint(1, 9999)}.{rng.randint(0, 10**9):09d}"
    return rng.choice(["0", "0.00", "00012.50", "1E+3", "-4.20", "123456789012345678901234567890.12", "7.5E-9"])


def _statement(rng: random.Random, size: int) -> tuple[str, str, list[tuple[str | None, str | None, str | None]]]:
    with localcontext() as ctx:
        ctx.prec = 80
        running = Decimal(_random_amount(rng)) if rng.random() < 0.8 else Decimal(0)
        opening = format(running, "f")
        rows = []
        for _ in range(size):
            amount = Decimal(_random_amount(rng))
            if rng.random() < 0.5:
                running -= amount
                rows.append([format(amount, "f"), None, None])
            else:
                running += amount
                rows.append([None, format(amount, "f"), None])
            rows[-1][2] = format(running, "f") if rng.random() < 0.9 else None
        closing = format(running, "f")
    return opening, closing, [tuple(r) for r in rows]


def _mutate_digit(rng: random.Random, text: str) -> str:
    positions = [p for p, char in enumerate(text) if char in DIGIT_SWAPS]
    if not positions:
        return text
    position = rng.choice(positions)
    return text[:position] + DIGIT_SWAPS[text[position]] + text[position + 1 :]


def _mutate_rows(rng: random.Random, rows: list[tuple]) -> list[tuple]:
    damaged = list(rows)
    for _ in range(rng.choice([0, 1, 1, 1, 2, 3])):
        if not damaged:
            break
        index = rng.randrange(len(damaged))
        debit, credit, balance = damaged[index]
        kind = rng.random()
        if kind < 0.3:
            field = rng.choice([f for f, v in zip(FIELDS, damaged[index]) if v is not None] or ["balance"])
            current = dict(zip(FIELDS, damaged[index]))[field]
            if current is not None:
                damaged[index] = tuple(_mutate_digit(rng, current) if f == field else v for f, v in zip(FIELDS, damaged[index]))
        elif kind < 0.45:
            shifted = Decimal(debit or credit or "0").scaleb(rng.choice([-1, 1, -2, 2]))
            if debit is not None:
                damaged[index] = (format(shifted, "f"), credit, balance)
            elif credit is not None:
                damaged[index] = (debit, format(shifted, "f"), balance)
        elif kind < 0.6:
            damaged[index] = (credit, debit, balance)
        elif kind < 0.7 and len(damaged) > 1:
            other = rng.randrange(len(damaged))
            damaged[index] = damaged[other]
        elif kind < 0.8:
            damaged[index] = (debit, credit, _random_amount(rng))
        elif kind < 0.9 and len(damaged) > 1:
            other = rng.randrange(len(damaged))
            delta = _random_amount(rng)
            d_debit, d_credit, d_balance = damaged[index]
            o_debit, o_credit, o_balance = damaged[other]
            if d_credit is not None and o_debit is not None:
                damaged[index] = (d_debit, format(Decimal(d_credit) + Decimal(delta), "f"), d_balance)
                damaged[other] = (format(Decimal(o_debit) + Decimal(delta), "f"), o_credit, o_balance)
        else:
            damaged[index] = (debit, credit, None)
    return damaged


def _run(module, opening: str, closing: str, rows, max_edits: int = 1):
    row_type = module.Row
    try:
        result = module.repair_by_running_balance(opening, closing, [row_type(*r) for r in rows], max_edits)
    except ValueError as error:
        return ("error", str(error))
    if result is None:
        return None
    return (result.row_index, result.field, result.original, result.repaired)


def _assert_same(opening: str, closing: str, rows) -> None:
    assert _run(indexed, opening, closing, rows) == _run(reference, opening, closing, rows)


def _random_cases():
    rng = random.Random(SEED)
    for _ in range(RANDOM_CASES):
        opening, closing, rows = _statement(rng, rng.randint(0, 12))
        yield opening, closing, _mutate_rows(rng, rows)
    for _ in range(LARGE_CASES):
        opening, closing, rows = _statement(rng, rng.randint(40, 120))
        yield opening, closing, _mutate_rows(rng, rows)


RANDOM = list(_random_cases())


@pytest.mark.parametrize("case_index", range(RANDOM_CASES + LARGE_CASES))
def test_random_statements_match_the_reference_exactly(case_index: int) -> None:
    opening, closing, rows = RANDOM[case_index]
    _assert_same(opening, closing, rows)


CLEAN = [("1000.00", None, "1000.00"), (None, "250.00", "1250.00"), ("100.00", None, "1150.00")]


@pytest.mark.parametrize(
    "opening, closing, rows",
    [
        ("1000.00", "1150.00", CLEAN),
        ("1000.00", "1150.00", [(None, "250.00", "1250.00"), ("100.00", None, "1150.00"), (None, None, None)]),
        ("1000.00", "1250.00", [("100.00", None, "900.00"), (None, "350.00", "1250.00")]),
        ("1000.00", "1150.00", [(None, "250.00", "1250.00"), (None, None, None), (None, None, None), ("100.00", None, "1150.00")]),
        ("1000.00", "1250.00", [(None, "250.00", "1260.00"), ("10.00", None, "1250.00")]),
        ("1000.00", "1250.00", [(None, "250.00", "1250.00"), ("10.00", None, "1240.00")]),
        ("1000.00", "1000.00", []),
        ("1000.00", "1001.00", []),
        ("1000.00", "1100.00", [(None, "100.00", None), (None, "100.00", "1200.00")]),
        ("1000.00", "1200.00", [(None, "100.00", "1100.00"), (None, "100.00", "1200.00")]),
        ("1000.00", "1200.00", [(None, "100.00", "1200.00"), (None, "100.00", "1300.00")]),
        ("1000.00", "1200.00", [(None, "100.00", "1100.00"), (None, "100.00", "1200.00"), (None, "100.00", "1300.00")]),
        ("0", "0", [(None, "0", "0"), (None, "0.00", "0.00")]),
        ("0", "5", [(None, "5", "5"), (None, "0", "5")]),
        ("1000.00", "1100.00", [("50.00", None, "950.00"), ("50.00", None, "900.00"), (None, "100.00", "1000.00")]),
        ("1000.00", "1000.00", [(None, "1", "1001.00"), (None, None, "1000.00")]),
        ("1000.00", "999.00", [(None, None, "1000.00"), (None, None, "1000.00")]),
        ("500.00", "500.00", [(None, "5000000000000000000000000000000.00", None)]),
        ("1000000000000000000000000000.00", "1000000000000000000000000000.00", [(None, "1.00", "1000000000000000000000000001.00")]),
        ("1000000000000000000000000000.00", "1000000000000000000000000001.00", [(None, "1.00", "1000000000000000000000000001.00")]),
        ("1000.00", "1250.00", [(None, "2.50", "1002.50"), (None, "247.50", "1250.00")]),
        ("1000.00", "1100.000000001", [(None, "100.000000001", "1100.000000001"), (None, None, "1100.000000001")]),
        ("1000.00", "1100.00", [(None, "100.00", "1100.0000000000000001")]),
        ("1E+3", "1100.00", [(None, "100.00", "1100.00")]),
        ("1000.00", "1150.00", [(None, "250.00", "1250.00"), ("abc", None, "1150.00")]),
        ("1000.00", "1150.00", [(None, "250.00", "1250.00"), ("100.00", None, "NaN")]),
        ("nope", "1150.00", CLEAN),
        ("1000.00", "1150.00", [(None, "250.00", "1250.00"), (None, None, None)]),
    ],
)
def test_adversarial_statements_match_the_reference(opening: str, closing: str, rows) -> None:
    _assert_same(opening, closing, rows)


@pytest.mark.parametrize("max_edits", [0, 2, -1])
def test_max_edits_other_than_one_is_rejected_by_both(max_edits: int) -> None:
    assert _run(indexed, "1000.00", "1100.00", CLEAN, max_edits) == _run(reference, "1000.00", "1100.00", CLEAN, max_edits)


def _signed_money(rng: random.Random, decimals: int, bound: int) -> str:
    return f"{Decimal(rng.randint(-bound, bound)) / 10**decimals:.{decimals}f}"


def _duplicate_amount(rng: random.Random) -> str:
    return rng.choice(("10.00", "10.00", "25.00", "-10.00", "0.00"))


def _negative_amount(rng: random.Random) -> str:
    return _signed_money(rng, 2, 500_000)


def _huge_amount(rng: random.Random) -> str:
    digits = rng.choice((13, 20, 28, 29, 33, 40))
    return f"{rng.randint(10 ** (digits - 1), 10**digits - 1)}.{rng.randint(0, 99):02d}"


def _precision_amount(decimals: int):
    return lambda rng: _signed_money(rng, decimals, 9_999_999)


CHAIN_KINDS = (
    ("duplicates", _duplicate_amount, 0.9),
    ("negatives", _negative_amount, 0.9),
    ("missing_balances", _negative_amount, 0.3),
    ("huge_decimals", _huge_amount, 0.9),
    ("precision_0", _precision_amount(0), 0.9),
    ("precision_2", _precision_amount(2), 0.9),
    ("precision_3", _precision_amount(3), 0.9),
)
CHAIN_CASES_PER_KIND = 40
LONG_CASES = 12


def _chain(rng: random.Random, size: int, amount, balance_rate: float):
    with localcontext() as ctx:
        ctx.prec = 80
        running = Decimal(amount(rng))
        opening = format(running, "f")
        rows = []
        for _ in range(size):
            value = Decimal(amount(rng))
            if rng.random() < 0.5:
                running -= value
                rows.append([format(value, "f"), None, None])
            else:
                running += value
                rows.append([None, format(value, "f"), None])
            rows[-1][2] = format(running, "f") if rng.random() < balance_rate else None
        closing = format(running, "f")
    return opening, closing, [tuple(r) for r in rows]


def _chain_cases():
    for kind_index, (_name, amount, balance_rate) in enumerate(CHAIN_KINDS):
        rng = random.Random(SEED + 1 + kind_index)
        for _ in range(CHAIN_CASES_PER_KIND):
            opening, closing, rows = _chain(rng, rng.randint(0, 12), amount, balance_rate)
            yield opening, closing, _mutate_rows(rng, rows)


def _long_cases():
    rng = random.Random(SEED + 100)
    for _ in range(LONG_CASES):
        opening, closing, rows = _chain(rng, rng.randint(150, 250), _random_amount, 0.9)
        yield opening, closing, _mutate_rows(rng, rows)


CHAIN_CASES = list(_chain_cases())
LONG_STATEMENTS = list(_long_cases())


@pytest.mark.parametrize("case_index", range(len(CHAIN_CASES)))
def test_category_statements_match_the_reference(case_index: int) -> None:
    _assert_same(*CHAIN_CASES[case_index])


@pytest.mark.parametrize("case_index", range(LONG_CASES))
def test_long_statements_match_the_reference(case_index: int) -> None:
    _assert_same(*LONG_STATEMENTS[case_index])


AMBIGUOUS = [
    ("0", "110.00", [(None, "100.00", None), (None, "100.00", None)]),
    ("0", "110.00", [(None, "100.00", None), (None, "100.00", None), (None, "100.00", None)]),
    ("0", "-110.00", [("100.00", None, None), ("100.00", None, None)]),
    ("0", "110.00", [(None, "100.00", None), (None, "100.00", "100.00"), (None, "100.00", None)]),
]


@pytest.mark.parametrize("opening, closing, rows", AMBIGUOUS)
def test_multiple_possible_repairs_are_reported_as_ambiguous(opening: str, closing: str, rows) -> None:
    _assert_same(opening, closing, rows)
    assert _run(indexed, opening, closing, rows) is None


AMBIGUOUS_GENERATED_CASES = 300


def _repair_count(opening: str, closing: str, rows) -> int:
    start = reference._amount(opening)
    end = reference._amount(closing)
    row_objects = [reference.Row(*r) for r in rows]
    return sum(
        1
        for edit in reference._single_edits(row_objects)
        if reference._chain_holds(start, end, reference._with_edit(row_objects, edit))
    )


def _forced_ambiguous(rng: random.Random):
    with localcontext() as ctx:
        ctx.prec = 80
        amount = _money(rng.randint(100, 9_999_999))
        variant = rng.choice(sorted(set(reference._variants(amount)) - {amount}))
        rows = []
        for _ in range(rng.randint(0, 4)):
            value = _money(rng.randint(0, 9_999_999))
            rows.append((value, None, None) if rng.random() < 0.5 else (None, value, None))
        for _ in range(rng.randint(2, 4)):
            rows.insert(rng.randint(0, len(rows)), (None, amount, None))
        opening = _money(rng.randint(0, 9_999_999))
        total = Decimal(opening)
        for debit, credit, _balance in rows:
            total += Decimal(credit or 0) - Decimal(debit or 0)
        closing = format(total + Decimal(variant) - Decimal(amount), "f")
    return opening, closing, rows


FORCED_AMBIGUOUS = [_forced_ambiguous(random.Random(SEED + 500 + index)) for index in range(AMBIGUOUS_GENERATED_CASES)]


@pytest.mark.parametrize("case_index", range(AMBIGUOUS_GENERATED_CASES))
def test_forced_ambiguous_statements_report_no_repair_in_both_implementations(case_index: int) -> None:
    opening, closing, rows = FORCED_AMBIGUOUS[case_index]
    assert _repair_count(opening, closing, rows) >= 2
    _assert_same(opening, closing, rows)
    assert _run(indexed, opening, closing, rows) is None


CONTROL_CASES = 60
NO_REPAIR_OFFSET = Decimal("123456.789")


def _controlled(rng: random.Random, mode: str, huge: bool):
    with localcontext() as ctx:
        ctx.prec = 80
        amount = f"{rng.randint(10**19, 10**20)}.00" if huge else _money(rng.randint(100, 9_999_999))
        variant = rng.choice(sorted(set(reference._variants(amount)) - {amount}))
        rows = []
        for _ in range(rng.randint(0, 4)):
            value = _money(rng.randint(0, 9_999_999))
            rows.append((value, None, None) if rng.random() < 0.5 else (None, value, None))
        copies = rng.randint(2, 4) if mode == "ambiguous" else 1
        for _ in range(copies):
            rows.insert(rng.randint(0, len(rows)), (None, amount, None))
        opening = _money(rng.randint(0, 9_999_999))
        total = Decimal(opening)
        for debit, credit, _balance in rows:
            total += Decimal(credit or 0) - Decimal(debit or 0)
        if mode == "none":
            closing = format(total + NO_REPAIR_OFFSET, "f")
        else:
            closing = format(total + Decimal(variant) - Decimal(amount), "f")
    return opening, closing, rows


def _controlled_case(seed: str, mode: str, huge: bool):
    rng = random.Random(seed)
    while True:
        case = _controlled(rng, mode, huge)
        if mode != "unique" or _repair_count(*case) == 1:
            return case


@pytest.mark.parametrize("huge", [False, True])
@pytest.mark.parametrize("mode", ["ambiguous", "unique", "none"])
@pytest.mark.parametrize("case_index", range(CONTROL_CASES))
def test_controlled_statements_match_and_never_auto_repair_ambiguity(mode: str, huge: bool, case_index: int) -> None:
    opening, closing, rows = _controlled_case(f"{mode}-{huge}-{case_index}", mode, huge)
    count = _repair_count(opening, closing, rows)
    if mode == "ambiguous":
        assert count >= 2
    elif mode == "unique":
        assert count == 1
    else:
        assert count == 0
    _assert_same(opening, closing, rows)
    result = _run(indexed, opening, closing, rows)
    if mode == "none" or mode == "ambiguous":
        assert result is None
    else:
        assert isinstance(result, tuple)
