"""S2b: a wide role set is resolved only when exactly one reading ties the running balance."""
from decimal import Decimal

import pytest

from openbooks_statements.pdf_front import Word
from openbooks.pipeline import Refusal
from openbooks_statements.roles import Pred, Predictions

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
