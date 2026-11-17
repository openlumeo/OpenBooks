import os

import numpy as np
import pytest

from openbooks.calibration import Calibrator, conformal_threshold, ece, fit_temperature, prediction_set, softmax
from openbooks.link import link
from openbooks.pdf_front import _ocr_fix


def _src(sha, amount, day, cur="INR"):
    return {"status": "ok", "file": {"sha256": sha * 64},
            "data": {"batches": [{"id": "batch-1", "kind": "settlement", "payout": {"amount": amount, "currency": cur},
                                  "period_end": day}], "transactions": []}}


def _bank(sha, credits):
    tx = [{"id": f"txn-{k}", "batch_id": "batch-1", "direction": "credit", "amount": {"amount": a, "currency": "INR"},
           "date": d, "description": desc} for k, (a, d, desc) in enumerate(credits, 1)]
    return {"status": "ok", "file": {"sha256": sha * 64}, "data": {"batches": [{"id": "batch-1", "kind": "statement"}], "transactions": tx}}


def test_link_one_to_one_requires_equal_amount_and_window():
    res = link([_src("a", "100.00", "2026-01-05"), _bank("b", [("100.00", "2026-01-07", "STRIPE"), ("100.01", "2026-01-07", "X")])])
    assert [x["credit"] for x in res["links"]] == ["bbbbbbbbbbbb:txn-1"]
    assert res["links"][0]["assertion"]["passed"] and res["unlinked_credits"] == ["bbbbbbbbbbbb:txn-2"]


def test_link_refuses_outside_window():
    res = link([_src("a", "100.00", "2026-01-05"), _bank("b", [("100.00", "2026-03-01", "late")])])
    assert res["links"] == [] and res["unlinked_sources"]


def test_link_ambiguous_identical_candidates_are_not_linked():
    res = link([_src("a", "100.00", "2026-01-05"), _src("c", "100.00", "2026-01-05"),
                _bank("b", [("100.00", "2026-01-06", "p1"), ("100.00", "2026-01-06", "p2")])])
    assert res["links"] == [] and len(res["ambiguous"]) == 2


def test_link_many_to_one_by_exact_sum():
    res = link([_src("a", "40.00", "2026-01-05"), _src("c", "60.00", "2026-01-05"), _bank("b", [("100.00", "2026-01-06", "batch")])])
    assert len(res["links"]) == 1 and res["links"][0]["kind"] == "many_to_one" and len(res["links"][0]["sources"]) == 2


def test_link_end_to_end_razorpay_payout_to_bank_credit(tmp_path):
    from decimal import Decimal

    from openbooks.golden import RZP_HEAD, RZP_OK
    from openbooks.pipeline import Params, process

    rz, bank = tmp_path / "rz.csv", tmp_path / "bank.csv"
    rz.write_text("\n".join([RZP_HEAD] + RZP_OK) + "\n")
    bank.write_text("Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n08/01/2026,RAZORPAY SETL,,77.64,1077.64\n")
    docs = [process(rz), process(bank, Params("INR", Decimal("1000.00")))]
    assert [d["status"] for d in docs] == ["ok", "ok"]
    res = link(docs)
    assert len(res["links"]) == 1 and res["links"][0]["amount"]["amount"] == "77.64" and not res["unlinked_credits"]


@pytest.mark.parametrize("raw,want", [("2.133.64", "2133.64"), ("5.,217.37", "5217.37"), ("1,234.50", "1,234.50"),
                                      ("1.000,50", "1.000,50"), ("12.50", "12.50")])
def test_ocr_separator_repair_is_narrow(raw, want):
    assert _ocr_fix(raw) == want


def test_temperature_reduces_ece_for_overconfident_logits():
    rng = np.random.default_rng(0)
    n, k = 4000, 5
    y = rng.integers(0, k, n)
    logits = rng.normal(0, 1, (n, k))
    flip = rng.random(n) < 0.3
    logits[np.arange(n), np.where(flip, rng.integers(0, k, n), y)] += 4.0
    logits *= 3.0
    t = fit_temperature(logits, y)
    assert t > 1.5
    assert ece(softmax(logits / t), y) < ece(softmax(logits), y)


def test_conformal_sets_cover_at_least_one_minus_alpha_on_exchangeable_data():
    rng = np.random.default_rng(1)
    n, k = 6000, 4
    y = rng.integers(0, k, n)
    logits = rng.normal(0, 1, (n, k))
    logits[np.arange(n), y] += 2.0
    cal = Calibrator.fit(logits[:3000], y[:3000], alpha=0.1)
    sets = cal.sets(logits[3000:])
    cover = np.mean([y[3000 + i] in s for i, s in enumerate(sets)])
    assert cover >= 0.88


def test_conformal_threshold_is_infinite_when_too_few_samples():
    p = softmax(np.zeros((3, 4)))
    assert conformal_threshold(p, np.array([0, 1, 2]), 0.05) == float("inf")
    assert prediction_set(p[0], float("inf")) == [0, 1, 2, 3]


@pytest.mark.skipif(not os.environ.get("OB_SLOW"), reason="OCR cases are slow; set OB_SLOW=1")
def test_scan_golden_cases_zero_false_accepts(tmp_path, capsys):
    from openbooks.golden import build
    from openbooks.pipeline import run_eval

    build(tmp_path, n_random=0, scans=True)
    assert run_eval(tmp_path) == 0
    assert "false_accepts=0" in capsys.readouterr().out


def test_pdf_fuzz_one_cent_tamper_is_never_accepted(tmp_path):
    import random
    from decimal import Decimal

    from openbooks.golden_docs import _pdf_rows
    from openbooks.pipeline import Params, process
    from openbooks.synth import random_layout, render

    rng, path, accepted_clean = random.Random(77), tmp_path / "f.pdf", 0
    for k in range(60):
        lay = random_layout(rng)
        lay.has_header = True
        rows = _pdf_rows(random.Random(k), rng.randint(5, 45))
        path.write_bytes(render(rows, "1000.00", lay, rng, closing=rows[-1][4])[0])
        accepted_clean += process(path, Params(currency="INR"))["status"] == "ok"
        t = [r[:] for r in rows]
        i, col = rng.randrange(len(t)), rng.choice([2, 3, 4])
        col = 5 - col if col in (2, 3) and not t[i][col] else col
        t[i][col] = f"{Decimal(t[i][col]) + Decimal('0.01'):.2f}"
        path.write_bytes(render(t, "1000.00", lay, rng, closing=rows[-1][4])[0])
        assert process(path, Params(currency="INR"))["status"] == "refused", f"false accept on layout {k}"
    assert accepted_clean >= 50
