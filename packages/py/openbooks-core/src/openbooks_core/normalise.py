"""Decimal, date and currency normalisation. Money is Decimal end to end; nothing is rounded silently."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from .errors import Refusal

# ISO 4217 minor units; every other currency is 2.
EXPONENT = {**dict.fromkeys(("BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI", "VND", "VUV",
                             "XAF", "XOF", "XPF"), 0),
            **dict.fromkeys(("BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"), 3)}

_PLAIN = re.compile(r"\d+(\.\d+)?")
# Digit grouping must be one consistent system. Mixed or ragged groups (12,345,67  1,23) are a dropped or mistyped digit,
# not a number, so they refuse instead of being read as something else.
_WESTERN = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")
_INDIAN = re.compile(r"\d{1,2}(,\d{2})*,\d{3}(\.\d+)?")


MAX_AMOUNT_DIGITS = 18


def to_dec(raw: str, where: str, *, blank_zero: bool = False, dr_cr: bool = False) -> Decimal:
    s = raw.strip()
    if not s:
        if blank_zero:
            return Decimal(0)
        raise Refusal("PARSE_ERROR", f"{where}: empty amount")
    sign = 1
    if dr_cr and s.lower().endswith("dr"):
        sign, s = -1, s[:-2].strip()
    elif dr_cr and s.lower().endswith("cr"):
        s = s[:-2].strip()
    if s.startswith("(") and s.endswith(")"):
        sign, s = -sign, s[1:-1].strip()
    if s[:1] == "-":
        sign, s = -sign, s[1:].strip()
    elif s[:1] == "+":
        s = s[1:].strip()
    ok = (_WESTERN.fullmatch(s) or _INDIAN.fullmatch(s)) if "," in s else _PLAIN.fullmatch(s)
    if not ok:
        raise Refusal("PARSE_ERROR", f"{where}: not a number: {raw!r}")
    digits = sum(c.isdigit() for c in s)
    if digits > MAX_AMOUNT_DIGITS:
        # Decimal arithmetic silently rounds to 28 significant digits; an amount this long could make a wrong total look equal.
        raise Refusal("PARSE_ERROR", f"{where}: amount has more than {MAX_AMOUNT_DIGITS} digits: {raw.strip()[:40]!r}")
    return Decimal(s.replace(",", "")) * sign


_TEXT_DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%d-%B-%Y", "%Y/%m/%d", "%Y%m%d", "%d-%b-%y",
                      "%d %b %y", "%d/%b/%Y", "%d/%b/%y", "%b %d, %Y", "%B %d, %Y", "%d %b, %Y")
_NUMERIC_DATE_FORMATS = {"dmy": ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%Y", "%d.%m.%y"),
                         "mdy": ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%m.%d.%Y", "%m.%d.%y")}
_TIME_TAIL = re.compile(r"[ T]\d{1,2}:\d{2}(:\d{2})?(\s?[APap][Mm])?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")
_NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}\b")
YEAR_RANGE = (1970, 2100)  # outside this is an OCR or typing error, not a statement date


def date_order(raws, forced: str | None = None, *, default: str | None = None, where: str = "dates") -> str:
    """Day/month order of a file's numeric dates. A forced order wins. Otherwise any first field above 12 proves day-first
    and any second field above 12 proves month-first; both is a mixed file and refuses. A file with no proof uses `default`,
    or refuses when there is none: guessing 03/04 as 3 April or 4 March silently moves money between periods."""
    if forced in ("dmy", "mdy"):
        return forced
    first_big = second_big = False
    for raw in raws:
        if m := _NUMERIC_DATE.match(raw or ""):
            first_big |= int(m[1]) > 12
            second_big |= int(m[2]) > 12
    if first_big and second_big:
        raise Refusal("PARSE_ERROR", f"{where}: both day-first and month-first dates in one file")
    if first_big or second_big:
        return "dmy" if first_big else "mdy"
    if default:
        return default
    raise Refusal("PARSE_ERROR", f"{where}: day/month order is ambiguous; supply --date-order dmy or mdy")


def to_date(raw: str, where: str, order: str = "dmy") -> str:
    """Numeric dates follow `order` (default day-first: 05/01/2026 is 5 January); the other order is never tried, so a
    month-first file cannot be read day-first by fallback. Two-digit years are 20yy. A year outside YEAR_RANGE refuses."""
    s = re.sub(r"\bSept\b", "Sep", _TIME_TAIL.sub("", raw.strip()))
    for fmt_ in _TEXT_DATE_FORMATS + _NUMERIC_DATE_FORMATS[order]:
        if fmt_ == "%Y%m%d" and not (s.isdigit() and len(s) == 8):
            continue
        try:
            d = datetime.strptime(s, fmt_).date()
        except ValueError:
            continue
        if "%y" in fmt_ and d.year < 2000:
            d = d.replace(year=d.year + 100)
        if not YEAR_RANGE[0] <= d.year <= YEAR_RANGE[1]:
            raise Refusal("PARSE_ERROR", f"{where}: implausible year in date {raw!r}")
        return d.isoformat()
    raise Refusal("PARSE_ERROR", f"{where}: unreadable date {raw!r}")


def fmt(d: Decimal, cur: str) -> str:
    if not d.is_finite() or d.adjusted() >= MAX_AMOUNT_DIGITS:  # every parser's amounts pass through here on the way into a document
        raise Refusal("PARSE_ERROR", f"amount is not a finite number with at most {MAX_AMOUNT_DIGITS} integer digits")
    q = Decimal(1).scaleb(-EXPONENT.get(cur, 2))
    if d != d.quantize(q):
        raise Refusal("PARSE_ERROR", f"{d} has more decimals than {cur} allows")
    d = d.quantize(q)
    return format(Decimal(0) if d == 0 else d, "f")


def money(d: Decimal, cur: str) -> dict:
    return {"amount": fmt(d, cur), "currency": cur}


def norm(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_")

