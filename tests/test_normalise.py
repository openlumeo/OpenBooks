"""Stage 3 (normalise): amounts, dates and currency exponents. A value is either read exactly or refused, never guessed."""
from decimal import Decimal

import pytest

from openbooks.pipeline import Refusal, fmt, to_date, to_dec


@pytest.mark.parametrize("raw,want", [
    ("1,23,456.78", "123456.78"), ("1,234,567.89", "1234567.89"), ("12,34,567", "1234567"), ("1,00,00,000.5", "10000000.5"),
    ("99,99,999.99", "9999999.99"), ("1,000", "1000"), ("1234.5", "1234.5"), ("0.00", "0.00"), ("+500", "500"),
    ("-1,000.00", "-1000.00"), ("(1,000.00)", "-1000.00"),
])
def test_amounts_read_exactly(raw, want):
    assert to_dec(raw, "x") == Decimal(want)


@pytest.mark.parametrize("raw", ["12,345,67", "1,234,56.78", "1,23", "1,2,3", "1,0000", "0,5", "1.000,50", "1 000,50", "1e3",
                                 "--5", "100.", "1,000.", "Rs. 1,000", "", "  "])
def test_ragged_or_foreign_numbers_refuse(raw):
    with pytest.raises(Refusal):
        to_dec(raw, "x")


def test_dr_cr_suffix_sets_the_sign_only_when_asked():
    assert to_dec("1,000.00 Dr", "x", dr_cr=True) == Decimal("-1000.00")
    assert to_dec("1,000.00Cr", "x", dr_cr=True) == Decimal("1000.00")
    with pytest.raises(Refusal):
        to_dec("1,000.00 Dr", "x")


@pytest.mark.parametrize("raw,want", [
    ("2026-01-05", "2026-01-05"), ("05/01/2026", "2026-01-05"), ("05-01-2026", "2026-01-05"), ("5-Jan-2026", "2026-01-05"),
    ("05 January 2026", "2026-01-05"), ("05/01/26", "2026-01-05"), ("05-Jan-26", "2026-01-05"), ("05.01.2026", "2026-01-05"),
    ("2026/01/05", "2026-01-05"), ("20260105", "2026-01-05"), ("Jan 5, 2026", "2026-01-05"), ("5 Sept 2026", "2026-09-05"),
    ("2026-01-05 14:30:00", "2026-01-05"), ("29/02/2028", "2028-02-29"),
])
def test_dates_read_to_iso(raw, want):
    assert to_date(raw, "x", "dmy") == want


@pytest.mark.parametrize("raw", ["05/13/2026", "31/02/2026", "29/02/2027", "05/01/0026", "202601055", "2026105", "tomorrow", ""])
def test_impossible_or_implausible_dates_refuse(raw):
    with pytest.raises(Refusal):
        to_date(raw, "x", "dmy")


def test_two_digit_years_are_this_century():
    assert to_date("01/01/69", "x", "dmy") == "2069-01-01"
    assert to_date("31-12-99", "x", "dmy") == "2099-12-31"


@pytest.mark.parametrize("amount,cur,want", [
    ("100", "JPY", "100"), ("5", "CLP", "5"), ("12.345", "KWD", "12.345"), ("12.345", "BHD", "12.345"), ("1000", "INR", "1000.00"),
    ("-0.00", "INR", "0"), ("1E+3", "USD", "1000.00"),
])
def test_amounts_are_formatted_to_the_currency_exponent(amount, cur, want):
    assert fmt(Decimal(amount), cur) == want


@pytest.mark.parametrize("amount,cur", [("1.005", "INR"), ("100.5", "JPY"), ("12.3456", "KWD")])
def test_extra_decimals_refuse_instead_of_rounding(amount, cur):
    with pytest.raises(Refusal):
        fmt(Decimal(amount), cur)
