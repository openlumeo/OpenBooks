from datetime import date
from decimal import Decimal

import pytest

from openbooks.core.errors import Refusal
from openbooks.core.iso4217 import exponent_of, lookup
from openbooks.core.normalise import fmt


@pytest.mark.parametrize(
    "code,exponent",
    [
        ("USD", 2),
        ("INR", 2),
        ("JPY", 0),
        ("KRW", 0),
        ("KWD", 3),
        ("BHD", 3),
        ("CLF", 4),
        ("UYW", 4),
        ("XCG", 2),
        ("XAD", 2),
        ("VED", 2),
        ("ZWG", 2),
    ],
)
def test_current_codes_have_their_iso_minor_unit(code, exponent):
    assert exponent_of(code) == exponent


@pytest.mark.parametrize("code", ["XAU", "XXX", "XTS", "XDR", "XAG"])
def test_codes_without_a_defined_minor_unit_refuse(code):
    with pytest.raises(Refusal) as err:
        exponent_of(code)
    assert err.value.code == "PARSE_ERROR"
    assert "minor unit" in err.value.message


@pytest.mark.parametrize("code", ["ANG", "CUC", "ZWL", "BGN", "HRK", "VEF"])
def test_withdrawn_codes_refuse_without_an_as_of_date(code):
    with pytest.raises(Refusal) as err:
        exponent_of(code)
    assert err.value.code == "PARSE_ERROR"


def test_withdrawn_code_refuses_because_its_minor_unit_is_not_published():
    with pytest.raises(Refusal) as err:
        exponent_of("CUC", as_of=date(2020, 1, 1))
    assert "does not publish its minor unit" in err.value.message


def test_historical_lookup_returns_the_withdrawal_that_covers_the_as_of_date():
    record = lookup("CUC", as_of=date(2020, 1, 1))
    assert record.current is False
    assert record.withdrawn == "2021-06"
    assert record.minor_unit is None


def test_historical_lookup_picks_the_first_withdrawal_on_or_after_the_as_of_date():
    assert lookup("VEF", as_of=date(2012, 1, 1)).withdrawn == "2016-02"
    assert lookup("VEF", as_of=date(2017, 1, 1)).withdrawn == "2018-08"


def test_historical_lookup_refuses_when_the_currency_was_withdrawn_before_the_as_of_date():
    with pytest.raises(Refusal) as err:
        lookup("CUC", as_of=date(2022, 1, 1))
    assert err.value.code == "PARSE_ERROR"


def test_historical_lookup_refuses_a_withdrawal_that_is_only_a_year_range():
    with pytest.raises(Refusal) as err:
        lookup("ARY", as_of=date(1979, 1, 1))
    assert err.value.code == "PARSE_ERROR"
    assert "range" in err.value.message


@pytest.mark.parametrize("code", ["XYZ", "usd", "", "US", "EURO"])
def test_an_unknown_code_refuses_instead_of_defaulting_to_two_decimals(code):
    with pytest.raises(Refusal) as err:
        exponent_of(code)
    assert err.value.code == "PARSE_ERROR"


def test_fmt_uses_the_real_exponent_and_refuses_an_unknown_code():
    assert fmt(Decimal("1500"), "JPY") == "1500"
    assert fmt(Decimal("1.500"), "KWD") == "1.500"
    with pytest.raises(Refusal):
        fmt(Decimal("1.00"), "XYZ")
    with pytest.raises(Refusal):
        fmt(Decimal("1.5"), "JPY")
