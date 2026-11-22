"""Property tests for the rules the financial guarantees rest on."""
from decimal import Decimal

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from openbooks.core import Refusal, date_order, fmt, to_date, to_dec  # noqa: E402

digits = st.text("0123456789", min_size=1, max_size=12)


def western(n: int, frac: str) -> str:
    s = f"{n:,}"
    return s + ("." + frac if frac else "")


@given(st.integers(0, 10**12), st.text("0123456789", max_size=4))
def test_well_formed_western_and_plain_numbers_round_trip_exactly(n, frac):
    expect = Decimal(f"{n}.{frac}" if frac else str(n))
    assert to_dec(western(n, frac), "t") == expect
    assert to_dec(str(n) + ("." + frac if frac else ""), "t") == expect


@given(st.integers(1000, 10**12))
def test_ragged_digit_grouping_is_refused_not_reinterpreted(n):
    s = f"{n:,}"
    ragged = s.replace(",", "", 1) if s.count(",") > 1 else s + ",5"
    if ragged.replace(",", "").isdigit() and "," not in ragged:
        return
    with pytest.raises(Refusal):
        to_dec(ragged, "t")


@given(st.text(max_size=12).filter(lambda s: s.strip() and not any(c in s for c in "0123456789")))
def test_text_with_no_digits_is_never_a_number(s):
    with pytest.raises(Refusal):
        to_dec(s, "t")


@given(st.integers(0, 10**9), st.sampled_from(["INR", "USD", "EUR", "JPY", "KWD"]))
def test_fmt_never_rounds(n, cur):
    exp = {"JPY": 0, "KWD": 3}.get(cur, 2)
    exact = Decimal(n).scaleb(-exp)
    assert Decimal(fmt(exact, cur)) == exact
    with pytest.raises(Refusal):
        fmt(exact + Decimal(1).scaleb(-(exp + 1)), cur)


@settings(max_examples=300)
@given(st.integers(1, 12), st.integers(1, 12), st.integers(2000, 2099))
def test_ambiguous_numeric_dates_are_never_guessed(a, b, y):
    raws = [f"{a:02d}/{b:02d}/{y}"]
    if a > 12 or b > 12:
        return
    with pytest.raises(Refusal):
        date_order(raws)
    assert date_order(raws, "dmy") == "dmy" and date_order(raws, "mdy") == "mdy"


@given(st.integers(13, 31), st.integers(1, 12), st.integers(2000, 2099))
def test_a_first_field_above_12_proves_day_first_and_a_second_above_12_proves_month_first(d, m, y):
    assert date_order([f"{d}/{m:02d}/{y}"]) == "dmy"
    assert date_order([f"{m:02d}/{d}/{y}"]) == "mdy"
    with pytest.raises(Refusal):
        date_order([f"{d}/{m:02d}/{y}", f"{m:02d}/{d}/{y}"])


@given(st.integers(2000, 2099), st.integers(1, 12), st.integers(1, 28))
def test_iso_dates_are_unaffected_by_the_day_month_order(y, m, d):
    iso = f"{y}-{m:02d}-{d:02d}"
    assert to_date(iso, "t", "dmy") == to_date(iso, "t", "mdy") == iso


@given(st.integers(1, 12), st.integers(1, 12), st.integers(2000, 2099))
def test_the_other_order_is_never_tried_as_a_fallback(a, b, y):
    if a > 12 or b > 12 or a == b:
        return
    s = f"{a:02d}/{b:02d}/{y}"
    assert to_date(s, "t", "dmy") == f"{y}-{b:02d}-{a:02d}"
    assert to_date(s, "t", "mdy") == f"{y}-{a:02d}-{b:02d}"
