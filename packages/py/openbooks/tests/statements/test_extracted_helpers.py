"""Edge cases for the helpers extracted from pdf_front, pdf_backend, parsers and cli. Each test documents what the helper does today."""
import math
from decimal import Decimal

import pytest

from openbooks.core import Params
from openbooks.core.errors import Refusal
from openbooks.statements import parsers, pdf_backend, pdf_front, scan_decimals, table_header
from openbooks.statements.pdf_words import Word, _date_spans, _lines

P = Params(currency="INR")


def w(text, x0, y, x1=None, h=10, page=1):
    return Word(text, x0, y, x0 + 40 if x1 is None else x1, y + h, page)


def header_line(y=0):
    """Date | Description | Debit | Credit | Balance, the split-column layout the OCR repair reads."""
    return [w("Date", 0, y), w("Description", 100, y, 160), w("Debit", 300, y, 340), w("Credit", 400, y, 440),
            w("Balance", 500, y, 550)]


def txn_line(y, debit=None, balance="100.00", date="01/01/2024", credit=None):
    line = [w(date, 0, y, 70), w("Coffee", 100, y, 160)]
    if debit is not None:
        line.append(w(debit, 300, y, 340))
    if credit is not None:
        line.append(w(credit, 400, y, 440))
    line.append(w(balance, 500, y, 550))
    return line


def test_lines_of_nothing_is_nothing():
    assert _lines([]) == []


def test_words_on_one_baseline_share_a_line_and_are_sorted_left_to_right():
    line = _lines([w("b", 100, 0), w("a", 0, 1), w("c", 0, 50)])
    assert [[x.text for x in ln] for ln in line] == [["a", "b"], ["c"]]


def test_date_spans_find_numeric_hyphen_and_spelled_dates_and_ignore_plain_text():
    words = [w("01-Jan-2024", 0, 0, 80), w("Coffee", 100, 0), w("5", 200, 0), w("March", 210, 0), w("2024", 260, 0)]
    assert _date_spans(words) == [(0, 1, "01-Jan-2024"), (2, 3, "5 March 2024")]


def test_date_spans_of_an_empty_line_is_empty():
    assert _date_spans([]) == []


def test_word_is_immutable_and_its_centre_is_the_midpoint():
    word = w("x", 10, 0, 30, h=20)
    assert (word.cx, word.cy, word.h) == (20, 10, 20)
    with pytest.raises(Exception):
        word.text = "y"


def test_word_height_is_never_below_one_point():
    assert Word("x", 0, 5, 1, 5, 1).h == 1.0


def test_a_split_debit_credit_header_is_recognised_with_its_columns():
    mode, cols = table_header._header_cols(header_line())
    assert mode == "split" and cols["debit"].text == "Debit" and cols["balance"].text == "Balance"


def test_a_single_amount_header_with_a_balance_is_recognised_as_single():
    mode, cols = table_header._header_cols([w("Date", 0, 0), w("Amount", 300, 0), w("Balance", 500, 0)])
    assert mode == "single" and "amount" in cols


def test_a_header_missing_a_balance_is_not_a_header():
    assert table_header._header_cols([w("Date", 0, 0), w("Debit", 300, 0), w("Credit", 400, 0)]) is None


def test_a_money_amount_on_the_line_disqualifies_it_as_a_header():
    assert table_header._header_cols(header_line() + [w("4.25", 320, 0)]) is None


def test_header_match_ignores_case_and_punctuation():
    mode, _ = table_header._header_cols([w("DATE:", 0, 0), w("DEBIT.", 300, 0), w("Credit", 400, 0), w("BALANCE", 500, 0)])
    assert mode == "split"


def test_find_header_returns_the_line_index_and_none_when_absent():
    assert table_header.find_header([txn_line(0), header_line(20)])[0] == 1
    assert table_header.find_header([txn_line(0)]) is None
    assert table_header.find_header([]) is None


def test_near_picks_the_closest_role_by_centre_or_right_edge():
    _, cols = table_header._header_cols(header_line())
    roles = ("debit", "credit", "balance")
    assert table_header._near(w("1.00", 300, 0, 340), cols, roles) == "debit"
    assert table_header._near(w("1.00", 480, 0, 552), cols, roles) == "balance"


def repaired_texts(words):
    return [x.text for x in scan_decimals._repair_scan_decimal_commas(words)]


def statement(*debits, ocr=None):
    """Header, then one row per (debit) amount with a dotted balance; `ocr` is an extra row with a comma amount."""
    rows = [txn_line(20 * (i + 1), debit=d, balance=f"{100 + i}.00") for i, d in enumerate(debits)]
    if ocr is not None:
        rows.append(txn_line(20 * (len(debits) + 1), debit=ocr, balance="999.00"))
    return [*header_line(), *[x for r in rows for x in r]]


def test_a_comma_amount_is_repaired_once_two_dotted_debits_prove_the_convention():
    words = statement("4.25", "7.50", ocr="4,25")
    assert repaired_texts(words)[-2] == "4.25"


def test_the_repair_keeps_the_original_text_on_the_repaired_word():
    words = scan_decimals._repair_scan_decimal_commas(statement("4.25", "7.50", ocr="4,25"))
    fixed = next(x for x in words if x.orig == "4,25")
    assert fixed.text == "4.25"


def test_one_dotted_example_is_not_enough_to_repair_anything():
    words = statement("4.25", ocr="4,25")
    assert repaired_texts(words)[-2] == "4,25"


def test_a_thousands_comma_shape_is_not_repaired_because_it_is_not_a_decimal():
    words = statement("4.25", "7.50", ocr="1,234")
    assert repaired_texts(words)[-2] == "1,234"


def test_a_zero_comma_amount_is_repaired_like_any_other():
    assert repaired_texts(statement("4.25", "7.50", ocr="0,00"))[-2] == "0.00"


def test_a_negative_comma_amount_is_never_repaired():
    assert repaired_texts(statement("4.25", "7.50", ocr="-4,25"))[-2] == "-4,25"


def test_a_european_thousands_amount_anywhere_disables_the_repair_entirely():
    words = statement("4.25", "7.50", ocr="4,25") + txn_line(900, debit="1.234,56")
    assert repaired_texts(words) == [x.text for x in words]


def test_no_header_means_the_words_come_back_unchanged():
    words = [txn_line(0, debit="4,25")][0]
    assert scan_decimals._repair_scan_decimal_commas(words) == words


def test_empty_input_comes_back_empty():
    assert scan_decimals._repair_scan_decimal_commas([]) == []


def test_repair_is_done_by_the_same_objects_the_pdf_front_module_exposes():
    assert pdf_front._repair_scan_decimal_commas is scan_decimals._repair_scan_decimal_commas
    assert pdf_front._OCR_COMMA_DECIMAL is scan_decimals._OCR_COMMA_DECIMAL
    assert pdf_front.Word is Word and pdf_front.HEADER is table_header.HEADER


def test_description_words_and_fragments_join_in_reading_order():
    row = {"desc_words": [w("Card", 100, 20), w("payment", 160, 20)], "frags": [(5.0, "Ref 1")]}
    pdf_front._join_descriptions([row])
    assert row == {"desc": "Ref 1 Card payment"}


def test_a_row_with_no_words_gets_an_empty_description():
    row = {"desc_words": [], "frags": []}
    pdf_front._join_descriptions([row])
    assert row["desc"] == ""


def test_joining_nothing_is_a_no_op():
    rows: list = []
    pdf_front._join_descriptions(rows)
    assert rows == []


def test_rows_over_no_pages_yields_no_rows_and_no_model_use():
    assert pdf_front._rows([], None) == ([], [], [], False)


def test_rows_with_no_header_and_no_model_are_skipped_silently():
    assert pdf_front._rows([[txn_line(0, debit="4.25")]], None) == ([], [], [], False)


@pytest.mark.parametrize("angle,upright", [
    (0.0, True), (-0.0, True), (1e-9, True), (math.radians(2.0), True),
    (math.pi / 2, False), (math.pi, False), (-math.pi / 2, False), (math.radians(10), False),
])
def test_only_near_horizontal_characters_are_kept(angle, upright):
    assert pdf_backend._upright(angle) is upright


class FakeTextPage:
    def __init__(self, boxes):
        self.boxes = boxes

    def get_charbox(self, i, loose):
        assert loose is True
        return self.boxes[i]


def test_a_char_box_is_moved_to_the_page_origin_and_flipped_to_top_left():
    tp = FakeTextPage([(110.0, 40.0, 120.0, 50.0)])
    assert pdf_backend._char_extent(tp, 0, 100.0, 200.0) == (10.0, 150.0, 20.0, 160.0)


def test_a_char_box_can_sit_left_of_the_page_origin_and_stays_a_tuple_of_four():
    tp = FakeTextPage([(90.0, 0.0, 95.0, 10.0)])
    box = pdf_backend._char_extent(tp, 0, 100.0, 10.0)
    assert box == (-10.0, 0.0, -5.0, 10.0) and len(box) == 4


def test_mt_fields_of_empty_text_is_empty():
    assert parsers._mt_fields("") == []


def test_mt_fields_join_continuation_lines_and_drop_blank_and_dash_lines():
    text = ":86:first\n\n-\nsecond\n-}\n"
    assert parsers._mt_fields(text) == [["86", "first\nsecond"]]


def test_mt_fields_treat_cr_and_crlf_line_endings_alike():
    assert parsers._mt_fields(":20:A\r\n:25:X\r:62F:C") == [["20", "A"], ["25", "X"], ["62F", "C"]]


def test_text_before_the_first_tag_is_ignored():
    assert parsers._mt_fields("{1:F01BANK}\nno tag here\n:20:A") == [["20", "A"]]


def test_statements_need_a_20_tag_before_anything_else_counts():
    assert parsers._mt_statements(":61:xx\n:86:y") == []
    assert parsers._mt_statements("") == []


def test_a_balance_with_a_comma_decimal_and_iso_date_is_read_with_its_sign():
    value, date, currency = parsers._mt_bal("C240101INR1234,56", "x")
    assert (value, date, currency) == (Decimal("1234.56"), "2024-01-01", "INR")


def test_a_debit_balance_is_negative():
    assert parsers._mt_bal("D240101INR10,00", "x")[0] == Decimal("-10.00")


def test_a_dot_decimal_balance_is_refused_as_unreadable():
    with pytest.raises(Refusal, match="unreadable balance"):
        parsers._mt_bal("C240101INR1234.56", "x")


def test_a_thousands_separated_balance_is_refused_rather_than_guessed():
    with pytest.raises(Refusal, match="unreadable balance"):
        parsers._mt_bal("C240101INR1.234,56", "x")


def test_an_impossible_date_is_refused_with_its_location():
    with pytest.raises(Refusal, match="where: unreadable date '230229'"):
        parsers._mt_date("230229", "where")


def test_a_leap_day_in_a_leap_year_is_accepted():
    assert parsers._mt_date("240229", "x") == "2024-02-29"


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


def test_the_sample_statement_releases_two_transactions_with_their_references():
    data, ev = parsers.parse_mt940(MT, P)
    refs = [t["reference"] for t in data["transactions"]]
    assert refs == [None, "INV1001"] and [t["description"] for t in data["transactions"]] == ["Salary January", "Rent"]
    assert data["batches"][0]["closing"]["amount"] == "1299.50"


def test_an_empty_file_is_refused_for_having_no_transactions():
    with pytest.raises(Refusal, match="no :61: transactions"):
        parsers.parse_mt940("", P)


def test_a_statement_without_its_closing_balance_is_refused_with_its_number():
    text = MT.replace(":62F:C260106INR1299,50\n", "")
    with pytest.raises(Refusal, match="statement 1: missing :25:, :60F: or :62F:"):
        parsers.parse_mt940(text, P)


def test_a_currency_change_inside_a_statement_is_refused():
    text = MT.replace(":62F:C260106INR1299,50", ":62F:C260106USD1299,50")
    with pytest.raises(Refusal, match="currency changes inside statement"):
        parsers.parse_mt940(text, P)


def test_a_malformed_61_line_is_refused_and_quotes_the_line():
    text = MT.replace(":61:2601060106D200,50NTRFINV1001//BR2", ":61:not a transaction")
    with pytest.raises(Refusal, match=r"unreadable 'not a transaction'"):
        parsers.parse_mt940(text, P)


def test_a_86_line_before_any_61_is_ignored_rather_than_attached():
    text = MT.replace(":61:2601050105", ":86:orphan\n:61:2601050105")
    data, _ = parsers.parse_mt940(text, P)
    assert data["transactions"][0]["description"] == "Salary January"


def test_multi_line_86_text_is_joined_with_single_spaces():
    text = MT.replace(":86:Salary January", ":86:Salary\n  January 2026")
    data, _ = parsers.parse_mt940(text, P)
    assert data["transactions"][0]["description"] == "Salary January 2026"


def test_a_large_statement_is_read_in_full_with_padded_transaction_ids():
    lines = [":20:BIG", ":25:1", ":60F:C260101INR0,00"]
    lines += [f":61:2601050105C1,00NTRFR{i}//X" for i in range(5000)]
    lines.append(":62F:C260102INR5000,00")
    data, _ = parsers.parse_mt940("\n".join(lines), P)
    assert len(data["transactions"]) == 5000
    assert data["transactions"][0]["id"] == "txn-1-00001" and data["transactions"][-1]["id"] == "txn-1-05000"


def test_a_negative_zero_debit_balance_is_formatted_the_same_as_zero():
    from openbooks.core.normalise import fmt

    value, _, _ = parsers._mt_bal("D240101INR0,00", "x")
    assert fmt(value, "INR") == fmt(Decimal("0"), "INR")


def test_the_parser_has_every_builtin_command_and_returns_plugins_by_name(monkeypatch):
    from openbooks.core import cli

    monkeypatch.setattr(cli, "_entry_points", lambda group: [])
    ap, plugins = cli._build_parser()
    assert plugins == {}
    for name in ("run", "eval", "link", "report", "engine-info"):
        assert ap.parse_args([name, *(["x"] if name in ("run", "eval", "link", "report") else [])]).cmd == name


def test_link_without_a_linker_is_a_usage_message_not_a_crash(monkeypatch, capsys):
    from openbooks.core import cli
    import argparse

    class NoLinker:
        def linker(self):
            return None

    monkeypatch.setattr(cli, "default_registry", lambda: NoLinker())
    rc = cli._link(argparse.Namespace(files=[], out="links.json"))
    assert rc != 0 and "no linker is installed" in capsys.readouterr().err
