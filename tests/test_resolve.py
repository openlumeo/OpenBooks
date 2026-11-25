"""S2b: a wide role set is resolved only when exactly one reading ties the running balance."""
from decimal import Decimal

import pytest

from openbooks.statements.pdf_front import Word
from openbooks.pipeline import Refusal
from openbooks.statements.roles import Pred, Predictions

AMT, BAL = Word("100.00", 0, 0, 1, 1, 1), Word("1,100.00", 2, 0, 3, 1, 1)
value = lambda w: Decimal(w.text.replace(",", ""))  # noqa: E731


def preds(amt_set, bal_set):
    mk = lambda s: Pred(s[0], tuple(s), "money", ("money",))  # noqa: E731
    return Predictions({AMT: mk(amt_set), BAL: mk(bal_set)})


def test_singletons_pass_through_unchanged():
    got = preds(("credit",), ("balance",)).resolve([AMT, BAL], None, value)
    assert got == {AMT: "credit", BAL: "balance"}


def test_wide_set_resolved_by_balance_chain():
    got = preds(("debit", "credit"), ("balance",)).resolve([AMT, BAL], Decimal("1000.00"), value)
    assert got == {AMT: "credit", BAL: "balance"}


def test_both_amounts_wide_still_resolved_by_chain():
    got = preds(("balance", "debit", "credit"), ("balance", "credit")).resolve([AMT, BAL], Decimal("1000.00"), value)
    assert got == {AMT: "credit", BAL: "balance"}


def test_no_opening_and_ambiguous_abstains():
    with pytest.raises(Refusal) as e:
        preds(("debit", "credit"), ("balance",)).resolve([AMT, BAL], None, value)
    assert e.value.code == "LOW_CONFIDENCE"


def test_no_reading_ties_abstains():
    with pytest.raises(Refusal) as e:
        preds(("debit", "credit"), ("balance",)).resolve([AMT, BAL], Decimal("5.00"), value)
    assert e.value.code == "LOW_CONFIDENCE"


def test_merged_amount_uses_the_numeric_token_inside_its_box():
    num, cr = Word("1,100.00", 2, 0, 3, 1, 1), Word("Cr", 3.1, 0, 4, 1, 1)
    merged = Word("1,100.00Cr", 2, 0, 4, 1, 1)
    pr = Predictions({num: Pred("balance", ("balance",), "money", ("money",)), cr: Pred("other", ("other",), "text", ("text",))})
    assert pr.get(merged).role_set == ("balance",)
    assert Predictions({}).get(merged) is None


def test_unpredicted_token_abstains():
    with pytest.raises(Refusal):
        Predictions({}).resolve([AMT, BAL], Decimal("1000.00"), value)


@pytest.mark.parametrize("closing,expected", [(None, None), (Decimal("80"), "debit")])
def test_printed_closing_can_select_a_unique_path(closing, expected):
    left, right = Word("20.00", 0, 0, 1, 1, 1), Word("80.00", 2, 0, 3, 1, 1)
    wide = Pred("debit", ("debit", "balance"), "money", ("money",))
    predictions = Predictions(dict.fromkeys((left, right), wide))
    if expected is None:
        with pytest.raises(Refusal, match="unique balance chain"):
            predictions.resolve_chain([[left, right]], Decimal("100"), closing, value)
    else:
        assert predictions.resolve_chain([[left, right]], Decimal("100"), closing, value) == [
            {left: expected, right: "balance"},
        ]


def test_paths_that_converge_are_still_ambiguous():
    left, right = Word("20.00", 0, 0, 1, 1, 1), Word("80.00", 2, 0, 3, 1, 1)
    amount, balance = Word("30.00", 0, 2, 1, 3, 1), Word("50.00", 2, 2, 3, 3, 1)
    predictions = Predictions({
        left: Pred("debit", ("debit", "balance"), "money", ("money",)),
        right: Pred("balance", ("debit", "balance"), "money", ("money",)),
        amount: Pred("debit", ("debit", "credit"), "money", ("money",)),
        balance: Pred("balance", ("balance",), "money", ("money",)),
    })
    with pytest.raises(Refusal, match="unique balance chain"):
        predictions.resolve_chain([[left, right], [amount, balance]], Decimal("100"), Decimal("50"), value)


@pytest.mark.parametrize("second_balance", ["70.00", "70.01"])
def test_headerless_statement_uses_later_rows_to_verify_an_ambiguous_read(tmp_path, monkeypatch, second_balance):
    from types import SimpleNamespace

    import pymupdf

    from openbooks.pipeline import Params, process
    from openbooks.statements.roles import RoleModel

    pdf = tmp_path / "headerless.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((40, 48), "Opening Balance: INR 100.00")
        for y, date, amount, balance in (
            (85, "13-01-2026", "20.00", "80.00"),
            (105, "14-01-2026", "10.00", second_balance),
        ):
            for x, text in ((40, date), (140, "TRANSFER"), (310, amount), (420, balance)):
                page.insert_text((x, y), text)
        document.save(pdf)

    def predict(pages):
        possible = {"20.00": ("debit", "balance"), "80.00": ("debit", "balance"),
                    "10.00": ("debit",), second_balance: ("balance",)}
        table = {}
        for words in pages:
            for word in words:
                if word.text in possible:
                    roles = possible[word.text]
                    table[word] = Pred(roles[0], roles, "money", ("money",))
                elif word.text in ("13-01-2026", "14-01-2026"):
                    table[word] = Pred("date", ("date",), "date", ("date",))
        return Predictions(table)

    identity = {"weights_sha256": "0" * 64, "calibration_sha256": "1" * 64}
    monkeypatch.setattr(RoleModel, "load", lambda: SimpleNamespace(identity=identity, predict=predict))
    result = process(pdf, Params(ocr=False, model=True), strict=True)
    if second_balance == "70.01":
        assert result["status"] == "refused", result
        assert result["error"]["code"] == "LOW_CONFIDENCE"
    else:
        assert result["status"] == "ok", result
        assert result["file"]["model"] == identity
        assert result["file"]["method"] == "pdf_text+model"
        assert [(row["direction"], row["amount"]["amount"]) for row in result["data"]["transactions"]] == [
            ("debit", "20.00"), ("debit", "10.00"),
        ]
        assert all(check["passed"] for check in result["assertions"])
        assert any(check["independent"] for check in result["assertions"])
