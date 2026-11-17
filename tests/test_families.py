"""S2: opt-in synthetic layout families (sign, branch, skew). Default layouts must not move; family PDFs must label cleanly
and the pipeline must never release a wrong ledger from them (a typed refusal is acceptable)."""
import hashlib
import random
from datetime import datetime, timedelta
from decimal import Decimal

import fitz
import pytest

from openbooks.golden_docs import _pdf_rows
from openbooks.pipeline import Params, process
from openbooks.synth import FAMILIES, NOISY_SCAN, SHIFT_HEAD, SKEW_MERCHANTS, merchant_rows, random_layout, render, to_scan

SEEDS = range(12)


def _build(family: str, seed: int):
    rng = random.Random(500 + seed)
    lay = random_layout(rng, family=family)
    lay.has_header = True
    rows = _pdf_rows(random.Random(seed), rng.randint(8, 30))
    if family == "skew":
        rows = merchant_rows(rows, rng, SKEW_MERCHANTS)
    pdf, cells = render(rows, "1000.00", lay, rng, closing=rows[-1][4])
    return lay, rows, pdf, cells


def test_default_layouts_are_unchanged():
    """Fingerprint taken before families existed; family=None must draw exactly the same layouts."""
    s = "".join(repr(random_layout(random.Random(k), shifted=k % 2 == 1, rich=k % 3 == 0, wide=k % 5 == 0)) for k in range(40))
    assert hashlib.sha256(s.encode()).hexdigest()[:16] == "f2d2f79f9dc99c7e"


def test_unknown_family_is_rejected():
    with pytest.raises(ValueError):
        random_layout(random.Random(1), family="distractors")  # F4 is held out on purpose


def test_family_headers_stay_out_of_the_shifted_vocabulary():
    shifted = {w for v in SHIFT_HEAD.values() for w in v}
    for fam in FAMILIES:
        for s in SEEDS:
            assert not shifted & set(_build(fam, s)[0].head.values()), (fam, s)


@pytest.mark.parametrize("family", FAMILIES)
def test_cells_do_not_overprint_and_sit_in_the_text_layer(family):
    for s in SEEDS:
        _, _, pdf, cells = _build(family, s)
        doc = fitz.open(stream=pdf, filetype="pdf")
        text = {i + 1: " ".join(p.get_text().split()) for i, p in enumerate(doc)}
        for i, (no, a, _, t) in enumerate(cells):
            assert " ".join(t.split()) in text[no], (family, s, t)
            for no2, b, _, t2 in cells[i + 1:]:
                if no2 == no:
                    assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (family, s, t, t2)


def test_sign_family_has_indicator_and_balance_drcr_column():
    seen = set()
    for s in SEEDS:
        lay, _, _, cells = _build("sign", s)
        assert lay.single and "bind" in lay.order and not lay.drcr_balance
        assert lay.order.index("bind") == lay.order.index("balance") + 1
        ind = {t for _, _, r, t in cells if r == "other" and t in ("+", "-", "DR", "CR")}
        assert ind and ind <= ({"+", "-"} if lay.extra["sign"] == "pm" else {"DR", "CR"})
        seen.add(lay.extra["sign"])
        assert {t for _, _, r, t in cells if t in ("Cr", "Dr")} == {"Cr"}
    assert seen == {"pm", "drcr"}


def test_branch_family_truncates_and_puts_the_cheque_in_the_narration():
    for s in SEEDS:
        lay, _, _, cells = _build("branch", s)
        desc = [t for _, _, r, t in cells if r == "desc"]
        assert lay.font == "cour" and lay.head["date"] == "Date" and "ref" not in lay.order
        assert desc and all(len(t) <= lay.extra["trunc"] for t in desc)
        assert all(t.startswith("CHQ ") for t in desc)


def test_skew_family_value_date_differs_by_a_day_and_uses_new_words():
    for s in SEEDS:
        lay, _, _, cells = _build("skew", s)
        assert lay.date_fmt.endswith("%y") and {"vdate", "tid"} <= set(lay.order)
        assert lay.head["debit"] in ("With. Amt.", "Dr") and lay.drcr_balance == lay.head["balance"].startswith("Balance (")
        sep = lay.date_fmt[2]
        dates = [datetime.strptime(t, lay.date_fmt) for _, _, r, t in cells if r == "date"]
        vals = [datetime.strptime(t, lay.date_fmt) for _, _, r, t in cells if r == "other" and t.count(sep) == 2]
        assert dates and len(dates) == len(vals) and all(v - d == timedelta(days=1) for d, v in zip(dates, vals))


def test_noisy_scan_differs_from_the_default_scan():
    _, _, pdf, _ = _build("branch", 0)
    assert to_scan(pdf, random.Random(1), **NOISY_SCAN) != to_scan(pdf, random.Random(1))


@pytest.mark.parametrize("family", FAMILIES)
def test_pipeline_never_releases_a_wrong_ledger_from_a_family_pdf(family, tmp_path):
    path, released = tmp_path / "f.pdf", 0
    for s in SEEDS:
        _, rows, pdf, _ = _build(family, s)
        path.write_bytes(pdf)
        doc = process(path, Params(currency="INR"))
        if doc["status"] != "ok":
            assert doc["error"]["code"], (family, s)
            continue
        want = [(("debit", r[2]) if r[2] else ("credit", r[3])) for r in rows if r[2] or r[3]]
        got = [(t["direction"], t["amount"]["amount"]) for t in doc["data"]["transactions"]]
        assert got == [(d, f"{Decimal(a):.2f}") for d, a in want], (family, s)
        released += 1
    print(f"{family}: released {released}/{len(SEEDS)}")
