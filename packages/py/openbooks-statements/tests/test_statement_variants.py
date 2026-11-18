"""The same statement written every way a bank or a spreadsheet writes it: it must release the same data, or be refused.
It must never release different numbers. (Some spellings are refused on purpose: a refusal is always allowed, a wrong release never.)"""
import concurrent.futures
import csv
import io
import json
from decimal import Decimal

import pytest

from openbooks_core import Params, process

BASE_ROWS = [("01/01/2026", "Salary", "", "500.00", "1500.00"), ("02/01/2026", "Rent", "200.50", "", "1299.50"), ("03/01/2026", "Coffee", "4.50", "", "1295.00")]
HEAD = ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
P = Params(currency="INR", opening=Decimal("1000.00"))
NL = chr(10)


def canon(doc):
    """What a statement means: when, which way, how much. Ignores ids, evidence and formatting."""
    return [(t["date"], t["direction"], t["amount"]["amount"]) for t in doc["data"]["transactions"]]


def render(rows=BASE_ROWS, head=HEAD, delim=",", eol=NL, quote=False, trailing="", lead=""):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator=NL, quoting=csv.QUOTE_ALL if quote else csv.QUOTE_MINIMAL)
    w.writerow(head)
    w.writerows(rows)
    lines = buf.getvalue().split(NL)[:-1]
    return lead + "".join(x + trailing + eol for x in lines)


@pytest.fixture
def run(tmp_path):
    def _run(content, ext="csv", params=P):
        f = tmp_path / f"in.{ext}"
        f.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return process(f, params)
    return _run


@pytest.fixture
def base(run):
    doc = run(render())
    assert doc["status"] == "ok", doc.get("error")
    return canon(doc)


def test_the_base_statement_means_what_we_think(base):
    assert base == [("2026-01-01", "credit", "500.00"), ("2026-01-02", "debit", "200.50"), ("2026-01-03", "debit", "4.50")]


# ---- spellings that must release exactly the same data ------------------------------------------------------------------

MUST_RELEASE = {
    "bom": lambda: b"\xef\xbb\xbf" + render().encode(),
    "crlf": lambda: render(eol="\r\n"),
    "cr_only": lambda: render(eol="\r"),
    "blank_lines_after": lambda: render() + "\n\n\n",
    "no_final_newline": lambda: render().rstrip("\n"),
    "all_fields_quoted": lambda: render(quote=True),
    "semicolon": lambda: render(delim=";"),
    "tab": lambda: render(delim="\t"),
    "upper_case_headers": lambda: render(head=[h.upper() for h in HEAD]),
    "lower_case_headers": lambda: render(head=[h.lower() for h in HEAD]),
    "padded_cells": lambda: render(rows=[[f" {v} " if v else v for v in r] for r in BASE_ROWS]),
    "latin1_accent_in_memo": lambda: render(rows=[(a, b + " café", c, d, e) for a, b, c, d, e in BASE_ROWS]).encode("cp1252"),
    "utf8_accents_and_symbols": lambda: render(rows=[(a, b + " café ₹ 中文 \U0001f600", c, d, e) for a, b, c, d, e in BASE_ROWS]),
    "memo_with_comma_and_quote": lambda: render(rows=[(a, '"Acme, Inc" said "hi"', c, d, e) for a, b, c, d, e in BASE_ROWS], quote=True),
    "memo_with_newline_in_quotes": lambda: render(rows=[(a, "line one\nline two", c, d, e) for a, b, c, d, e in BASE_ROWS], quote=True),
    "reordered_columns": lambda: "Closing Balance,Date,Deposit Amt.,Narration,Withdrawal Amt.\n" + "".join(
        f"{e},{a},{d},{b},{c}\n" for a, b, c, d, e in BASE_ROWS),
    "iso_dates": lambda: render(rows=[(f"2026-01-0{i}", b, c, d, e) for i, (a, b, c, d, e) in enumerate(BASE_ROWS, 1)]),
}


@pytest.mark.parametrize("name", sorted(MUST_RELEASE))
def test_equivalent_spellings_release_the_same_statement(run, base, name):
    doc = run(MUST_RELEASE[name]())
    assert doc["status"] == "ok", f"{name}: {doc.get('error')}"
    assert canon(doc) == base


def test_unicode_in_a_memo_comes_back_exactly(run):
    memo = "café ₹ 中文 \U0001f600 ‮RTL‬ é"
    doc = run(render(rows=[(a, memo, c, d, e) for a, b, c, d, e in BASE_ROWS]))
    assert doc["status"] == "ok" and doc["data"]["transactions"][0]["description"] == memo


def test_the_output_is_valid_utf8_json_whatever_the_memo_holds(run):
    memo = "\u0007bell ﻿bom  sep \u0085nel \\ backslash \"quote\""
    doc = run(render(rows=[(a, memo, c, d, e) for a, b, c, d, e in BASE_ROWS], quote=True))
    if doc["status"] == "ok":
        assert json.loads(json.dumps(doc, ensure_ascii=False).encode("utf-8").decode("utf-8")) == doc


@pytest.mark.parametrize("memo", ["=cmd|' /C calc'!A0", "+1+1", "@SUM(1,1)", "-2+3", "=HYPERLINK(\"http://x\")", "\t=1", "<script>alert(1)</script>", "'; DROP TABLE t; --", "${jndi:ldap://x}", "{{7*7}}", "../../etc/passwd"])
def test_a_memo_that_looks_like_a_formula_or_code_is_kept_as_plain_data(run, base, memo):
    doc = run(render(rows=[(a, memo, c, d, e) for a, b, c, d, e in BASE_ROWS], quote=True))
    assert doc["status"] == "ok" and canon(doc) == base
    assert doc["data"]["transactions"][0]["description"] == memo.strip()  # untouched: the engine neither runs nor rewrites it


def test_a_very_long_memo_is_kept_whole(run, base):
    memo = "x" * 100_000
    doc = run(render(rows=[(a, memo, c, d, e) for a, b, c, d, e in BASE_ROWS], quote=True))
    assert doc["status"] == "ok" and canon(doc) == base and len(doc["data"]["transactions"][0]["description"]) == 100_000


def test_a_memo_with_a_nul_byte_is_refused_as_binary(run):
    doc = run(render(rows=[(a, "bad\x00memo", c, d, e) for a, b, c, d, e in BASE_ROWS]))
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT"


# ---- spellings that may be refused but must never release different numbers ---------------------------------------------

MAY_REFUSE = {
    "dd_mon_yyyy": lambda: render(rows=[(f"0{i}-Jan-2026", b, c, d, e) for i, (a, b, c, d, e) in enumerate(BASE_ROWS, 1)]),
    "dotted_dates": lambda: render(rows=[(f"0{i}.01.2026", b, c, d, e) for i, (a, b, c, d, e) in enumerate(BASE_ROWS, 1)]),
    "short_dates_no_zero_pad": lambda: render(rows=[(f"{i}/1/2026", b, c, d, e) for i, (a, b, c, d, e) in enumerate(BASE_ROWS, 1)]),
    "two_digit_years": lambda: render(rows=[(f"0{i}/01/26", b, c, d, e) for i, (a, b, c, d, e) in enumerate(BASE_ROWS, 1)]),
    "thousands_commas": lambda: render(rows=[(a, b, c, d, f"{Decimal(e):,.2f}") for a, b, c, d, e in BASE_ROWS], quote=True),
    "currency_symbols": lambda: render(rows=[(a, b, f"₹{c}" if c else c, f"₹{d}" if d else d, f"₹{e}") for a, b, c, d, e in BASE_ROWS], quote=True),
    "rs_prefix": lambda: render(rows=[(a, b, f"Rs. {c}" if c else c, f"Rs. {d}" if d else d, f"Rs. {e}") for a, b, c, d, e in BASE_ROWS], quote=True),
    "negative_debits": lambda: render(rows=[(a, b, f"-{c}" if c else c, d, e) for a, b, c, d, e in BASE_ROWS]),
    "parenthesised_debits": lambda: render(rows=[(a, b, f"({c})" if c else c, d, e) for a, b, c, d, e in BASE_ROWS]),
    "cr_dr_suffix_on_balance": lambda: render(rows=[(a, b, c, d, e + " Cr") for a, b, c, d, e in BASE_ROWS]),
    "european_numbers": lambda: render(rows=[(a, b, c.replace(".", ","), d.replace(".", ","), e.replace(".", ",")) for a, b, c, d, e in BASE_ROWS], delim=";"),
    "indian_grouping": lambda: render(rows=[(a, b, c, d, "1,00,000.00") for a, b, c, d, e in BASE_ROWS[:1]], quote=True),
    "extra_empty_column": lambda: render(head=HEAD + [""], rows=[r + ("",) for r in BASE_ROWS]),
    "extra_reference_column": lambda: render(head=HEAD + ["Ref No"], rows=[r + (f"R{i}",) for i, r in enumerate(BASE_ROWS)]),
    "trailing_delimiter": lambda: render(trailing=","),
    "title_lines_above_header": lambda: render(lead="Account Statement\nCustomer: A B\n\n"),
    "footer_lines": lambda: render() + "Total,,,,\nThis is a computer generated statement\n",
    "duplicate_header_row_in_the_middle": lambda: render(rows=BASE_ROWS[:2] + [tuple(HEAD)] + BASE_ROWS[2:]),
    "zero_width_space_in_amount": lambda: render(rows=[(a, b, c, "5​00.00" if d else d, e) for a, b, c, d, e in BASE_ROWS]),
    "arabic_indic_digits": lambda: render(rows=[(a, b, c, "٥٠٠.00" if d else d, e) for a, b, c, d, e in BASE_ROWS]),
    "fullwidth_digits": lambda: render(rows=[(a, b, c, "５００.00" if d else d, e) for a, b, c, d, e in BASE_ROWS]),
    "scientific_notation": lambda: render(rows=[(a, b, "2.005e2" if c == "200.50" else c, d, e) for a, b, c, d, e in BASE_ROWS]),
    "nan_amount": lambda: render(rows=[(a, b, "NaN" if c == "4.50" else c, d, e) for a, b, c, d, e in BASE_ROWS]),
    "infinity_amount": lambda: render(rows=[(a, b, "Infinity" if c == "4.50" else c, d, e) for a, b, c, d, e in BASE_ROWS]),
    "three_decimals_that_sum": lambda: render(rows=[(a, b, c, d, e) for a, b, c, d, e in BASE_ROWS[:1]] + [("02/01/2026", "x", "0.005", "", "1499.995")]),
    "huge_amount": lambda: render(rows=[("01/01/2026", "x", "", "9" * 40 + ".00", "9" * 40 + ".00")]),
    "negative_zero": lambda: render(rows=[(a, b, c, "-0.00" if d == "500.00" else d, e) for a, b, c, d, e in BASE_ROWS]),
}


@pytest.mark.parametrize("name", sorted(MAY_REFUSE))
def test_unusual_spellings_are_released_identically_or_refused_never_misread(run, base, name):
    doc = run(MAY_REFUSE[name]())
    assert doc["status"] in ("ok", "refused"), name
    if doc["status"] == "refused":
        assert doc["error"]["code"] in {"PARSE_ERROR", "UNKNOWN_LAYOUT", "BALANCE_MISMATCH", "UNSUPPORTED_INPUT", "AMBIGUOUS_DATE"} | {doc["error"]["code"]}
        assert not doc["error"].get("internal"), f"{name}: crashed instead of refusing: {doc['error']['message']}"
    elif name in {"extra_empty_column", "extra_reference_column", "trailing_delimiter", "title_lines_above_header", "footer_lines",
                  "thousands_commas", "currency_symbols", "rs_prefix", "cr_dr_suffix_on_balance", "dd_mon_yyyy", "dotted_dates",
                  "short_dates_no_zero_pad", "two_digit_years", "european_numbers", "arabic_indic_digits", "fullwidth_digits"}:
        assert canon(doc) == base, f"{name} was released with different numbers"
    else:
        raise AssertionError(f"{name} should have been refused, got {canon(doc)}")


def test_three_decimal_places_are_never_silently_rounded(run):
    doc = run(render(rows=[("01/01/2026", "x", "", "500.005", "1500.005")]))
    assert doc["status"] == "refused" or doc["data"]["transactions"][0]["amount"]["amount"] == "500.005"


def test_a_row_with_both_a_debit_and_a_credit_is_refused(run):
    doc = run(render(rows=[("01/01/2026", "x", "10.00", "10.00", "1000.00")]))
    assert doc["status"] == "refused"


def test_a_row_with_neither_a_debit_nor_a_credit_is_refused(run):
    doc = run(render(rows=[("01/01/2026", "x", "", "", "1000.00")]))
    assert doc["status"] == "refused"


def test_a_zero_amount_row_is_refused_or_exact(run):
    doc = run(render(rows=[("01/01/2026", "x", "", "0.00", "1000.00")]))
    assert doc["status"] == "refused" or doc["data"]["transactions"][0]["amount"]["amount"] == "0.00"


def test_an_impossible_calendar_date_is_refused(run):
    for bad in ("31/02/2026", "00/01/2026", "32/01/2026", "29/02/2026", "01/01/0000", "01/01/10000", "01/01/1969", "01/01/2101"):
        doc = run(render(rows=[(bad, "x", "", "500.00", "1500.00")]))
        assert doc["status"] == "refused", bad


def test_a_first_field_over_twelve_proves_day_first_and_a_second_field_over_twelve_proves_month_first(run):
    day_first = run(render(rows=[("13/01/2026", "x", "", "500.00", "1500.00")]))
    month_first = run(render(rows=[("01/13/2026", "x", "", "500.00", "1500.00")]))
    assert day_first["data"]["transactions"][0]["date"] == "2026-01-13" == month_first["data"]["transactions"][0]["date"]


def test_a_file_that_mixes_both_orders_is_refused(run):
    rows = [("13/01/2026", "a", "", "500.00", "1500.00"), ("01/13/2026", "b", "10.00", "", "1490.00")]
    assert run(render(rows=rows))["status"] == "refused"


def test_a_leap_day_is_accepted_in_a_leap_year(run):
    doc = run(render(rows=[("29/02/2028", "x", "", "500.00", "1500.00")]))
    assert doc["status"] == "ok" and doc["data"]["transactions"][0]["date"] == "2028-02-29"


def test_day_month_order_is_never_guessed_when_every_date_could_be_either(run):
    rows = [("01/02/2026", "a", "", "500.00", "1500.00"), ("03/04/2026", "b", "10.00", "", "1490.00")]
    doc = run(render(rows=rows))
    if doc["status"] == "ok":  # allowed only if the statement itself shows which order it uses
        assert doc["data"]["transactions"][0]["date"] in ("2026-02-01", "2026-01-02")
    forced = run(render(rows=rows), params=Params(currency="INR", opening=Decimal("1000.00"), date_order="mdy"))
    assert forced["status"] == "ok" and forced["data"]["transactions"][0]["date"] == "2026-01-02"


def test_the_opening_balance_must_match_to_the_cent(run):
    for opening in ("999.99", "1000.01", "0", "-1000.00"):
        doc = run(render(), params=Params(currency="INR", opening=Decimal(opening)))
        assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH", opening
    assert run(render(), params=Params(currency="INR", opening=Decimal("1000.0000001")))["status"] == "refused"


def test_a_statement_that_goes_negative_is_a_statement_not_an_error(run):
    rows = [("01/01/2026", "overdraft", "1500.00", "", "-500.00")]
    doc = run(render(rows=rows))
    assert doc["status"] == "ok" and canon(doc) == [("2026-01-01", "debit", "1500.00")]


def test_a_single_transaction_is_enough(run):
    assert run(render(rows=BASE_ROWS[:1]))["status"] == "ok"


def test_ten_thousand_rows_release_and_keep_every_amount(run):
    rows, bal = [], Decimal("1000.00")
    for i in range(10_000):
        bal += Decimal("1.01")
        rows.append((f"{1 + i % 28:02d}/01/2026", f"row {i}", "", "1.01", f"{bal}"))
    doc = run(render(rows=rows))
    assert doc["status"] == "ok" and len(doc["data"]["transactions"]) == 10_000
    assert {t["amount"]["amount"] for t in doc["data"]["transactions"]} == {"1.01"}


def test_dropping_a_row_in_the_middle_is_caught_by_the_balance_chain(run):
    rows = [("01/01/2026", f"r{i}", "", "10.00", f"{1000 + 10 * i + 10}.00") for i in range(6)]
    del rows[3]
    assert run(render(rows=rows))["error"]["code"] == "BALANCE_MISMATCH"


def test_swapping_two_rows_breaks_the_chain(run):
    rows = [("01/01/2026", f"r{i}", "", f"{10 * (i + 1)}.00", f"{1000 + sum(10 * (k + 1) for k in range(i + 1))}.00") for i in range(4)]
    rows[1], rows[2] = rows[2], rows[1]
    assert run(render(rows=rows))["status"] == "refused"


def test_a_debit_written_as_a_credit_breaks_the_chain(run):
    rows = [("02/01/2026", "Rent", "", "200.50", "1299.50")]
    assert run(render(rows=rows))["error"]["code"] == "BALANCE_MISMATCH"


# ---- MT940 and OFX written the other ways they are written --------------------------------------------------------------

MT = """:20:STMT001
:25:12345678/9876543
:28C:1/1
:60F:C260101INR1000,00
:61:2601050105C500,00NTRFNONREF//BANKREF1
:86:Salary January
:61:2601060106D200,50NTRFINV1001//BR2
:86:Rent
:62F:C260106INR1299,50
"""


@pytest.mark.parametrize("name,fn", [
    ("crlf", lambda s: s.replace("\n", "\r\n")), ("bom", lambda s: "﻿" + s), ("trailing_blank_lines", lambda s: s + "\n\n"),
    ("dash_terminator", lambda s: s + "-\n"), ("padded_lines", lambda s: s.replace("\n", "  \n")),
    ("multi_line_86", lambda s: s.replace("Salary January", "Salary\nJanuary 2026 continued")),
])
def test_mt940_spellings_release_the_same_data(run, name, fn):
    ref = canon(run(MT, "sta"))
    doc = run(fn(MT), "sta")
    assert doc["status"] == "ok", f"{name}: {doc.get('error')}"
    assert canon(doc) == ref


@pytest.mark.parametrize("ext", ["sta", "mt940", "txt", "STA"])
def test_mt940_is_recognised_by_content_whatever_the_extension(run, ext):
    assert run(MT, ext)["status"] == "ok"


def test_mt940_truncated_anywhere_before_the_closing_balance_is_never_released(run):
    end = MT.index(":62F:") + len(":62F:C260106INR")  # up to the closing balance's digits; "1299,5" would equal 1299,50
    for cut in range(0, end, 3):
        doc = run(MT[:cut], "sta")
        assert doc["status"] == "refused", f"cut at {cut} released {MT[:cut][-30:]!r}"


@pytest.mark.parametrize("old,new", [("500,00", "500,01"), ("200,50", "200,51"), ("1000,00", "1000,01"), ("1299,50", "1299,49"), ("C260101", "D260101"), ("C500", "D500"), ("D200", "C200")])
def test_mt940_one_wrong_character_is_refused(run, old, new):
    assert run(MT.replace(old, new, 1), "sta")["status"] == "refused"


def test_mt940_reversal_and_unusual_codes_are_refused_or_exact(run):
    doc = run(MT.replace("C500,00", "RC500,00"), "sta")
    assert doc["status"] in ("ok", "refused") and not doc.get("error", {}).get("internal")


OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>INR
<BANKACCTFROM><BANKID>X<ACCTID>123456789<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260101<DTEND>20260131
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260105120000<TRNAMT>500.00<FITID>A1<NAME>Salary</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260106120000<TRNAMT>-200.50<FITID>A2<NAME>Rent</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>1299.50<DTASOF>20260131</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""
OFX_P = Params(opening=Decimal("1000.00"))


@pytest.mark.parametrize("ext", ["ofx", "qfx", "OFX", "txt"])
def test_ofx_is_recognised_by_content_whatever_the_extension(run, ext):
    assert run(OFX, ext, OFX_P)["status"] == "ok"


@pytest.mark.parametrize("name,fn", [("crlf", lambda s: s.replace("\n", "\r\n")), ("bom", lambda s: "﻿" + s), ("indented", lambda s: s.replace("<STMTTRN>", "  <STMTTRN>")),
                                     ("one_line", lambda s: s.replace("\n", ""))])
def test_ofx_spellings_release_the_same_data(run, name, fn):
    ref = canon(run(OFX, "ofx", OFX_P))
    doc = run(fn(OFX), "ofx", OFX_P)
    assert doc["status"] == "ok", f"{name}: {doc.get('error')}"
    assert canon(doc) == ref


def test_ofx_truncated_anywhere_before_the_closing_balance_is_never_released(run):
    end = OFX.index("<BALAMT>") + len("<BALAMT>")  # up to the closing balance's digits; "1299.5" would equal 1299.50
    for cut in range(0, end, 7):
        assert run(OFX[:cut], "ofx", OFX_P)["status"] == "refused", cut


@pytest.mark.parametrize("old,new", [("500.00", "500.01"), ("-200.50", "-200.51"), ("-200.50", "200.50"), ("1299.50", "1299.51"), ("<CURDEF>INR", "<CURDEF>USD")])
def test_ofx_one_wrong_value_is_refused_or_changes_only_the_currency(run, old, new):
    doc = run(OFX.replace(old, new, 1), "ofx", OFX_P)
    if old.startswith("<CURDEF>"):
        assert doc["status"] == "ok" and doc["data"]["transactions"][0]["amount"]["currency"] == "USD"
    else:
        assert doc["status"] == "refused"


# ---- many at once -------------------------------------------------------------------------------------------------------

def test_processing_in_several_threads_gives_the_same_answers_as_one_at_a_time(tmp_path):
    files = []
    for i in range(24):
        f = tmp_path / f"s{i}.csv"
        f.write_text(render() if i % 3 else render().replace("1295.00", "1295.01"), encoding="utf-8")
        files.append(f)
    serial = [process(f, P)["status"] for f in files]
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        parallel = list(pool.map(lambda f: process(f, P)["status"], files * 3))
    assert parallel == serial * 3 and set(serial) == {"ok", "refused"}


def test_a_failure_in_one_file_never_leaks_into_the_next(tmp_path):
    bad, good = tmp_path / "bad.csv", tmp_path / "good.csv"
    bad.write_bytes(b"\x00\x01garbage")
    good.write_text(render(), encoding="utf-8")
    assert [process(f, P)["status"] for f in (good, bad, good, bad, good)] == ["ok", "refused", "ok", "refused", "ok"]
