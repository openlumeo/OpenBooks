from __future__ import annotations

import math
import time
from decimal import Decimal

from openbooks.statements.balance_repair import Row, repair_by_running_balance

ROW_COUNT = 1600
BUDGET_SECONDS = 2.0
SCALING_ROW_COUNTS = (1600, 3200, 6400, 9999, 10001, 20000)
MAX_LOG_LOG_SLOPE = 1.5


def _money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def _unrepairable_statement(count: int) -> tuple[str, str, list[Row]]:
    running = 10_000_000
    rows: list[Row] = []
    for index in range(count):
        amount = 100 + (index * 37) % 99_000
        if index % 2:
            running -= amount
            rows.append(Row(_money(amount), None, _money(running)))
        else:
            running += amount
            rows.append(Row(None, _money(amount), _money(running)))
    middle = count // 2
    rows[middle] = Row(rows[middle].debit, rows[middle].credit, _money(777_777_777_777))
    return _money(10_000_000), _money(running + 12_345_678), rows


def _best_seconds(opening: str, closing: str, rows: list[Row], repeats: int = 2) -> float:
    best = math.inf
    for _ in range(repeats):
        started = time.perf_counter()
        assert repair_by_running_balance(opening, closing, rows) is None
        best = min(best, time.perf_counter() - started)
    return best


def log_log_slope(sizes: tuple[int, ...], seconds: list[float]) -> float:
    xs = [math.log(size) for size in sizes]
    ys = [math.log(value) for value in seconds]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    return numerator / denominator


def test_worst_case_chain_with_no_repair_finishes_at_1600_rows_within_budget() -> None:
    opening, closing, rows = _unrepairable_statement(ROW_COUNT)
    started = time.perf_counter()
    assert repair_by_running_balance(opening, closing, rows) is None
    assert time.perf_counter() - started < BUDGET_SECONDS


def test_indexed_path_scales_near_linearly_up_to_the_fallback_threshold() -> None:
    seconds = []
    for size in SCALING_ROW_COUNTS:
        opening, closing, rows = _unrepairable_statement(size)
        seconds.append(_best_seconds(opening, closing, rows))
    assert log_log_slope(SCALING_ROW_COUNTS, seconds) < MAX_LOG_LOG_SLOPE


def test_wide_amounts_beyond_the_exact_range_fail_fast_within_the_work_budget() -> None:
    opening, closing, rows = _unrepairable_statement(ROW_COUNT)
    rows[10] = Row("12345678901234567890123.00", None, None)
    started = time.perf_counter()
    try:
        result = repair_by_running_balance(opening, closing, rows)
    except ValueError as error:
        assert "work budget" in str(error)
    else:
        assert result is None
    assert time.perf_counter() - started < BUDGET_SECONDS * 30
