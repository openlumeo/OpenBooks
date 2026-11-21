"""End-to-end OCR safety check on synthetic scans, and the date-confidence threshold sweep.

For random layouts: render -> scan -> process() with the date-confidence rule switched off. Each result is
accepted-and-correct, accepted-and-WRONG (the dangerous case), or refused (by code). The sweep then shows, for
each threshold, how many would abstain and how many wrong dates would still get through.
Writes docs/evidence/ocr_calibration.json. Synthetic scans only: real scans will be worse.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from openbooks.statements import pdf_front  # noqa: E402
from openbooks_lab.golden_docs import _pdf_rows  # noqa: E402
from openbooks.pipeline import Params, process  # noqa: E402
from openbooks_lab.synth import random_layout, render, to_scan  # noqa: E402

THRESHOLDS = (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9)


def truth_matches(doc: dict, rows: list[list[str]]) -> tuple[bool, list[float]]:
    """(all fields right, confidences of the dates that were read wrong)."""
    tx = doc["data"]["transactions"]
    if len(tx) != len(rows):
        return False, [0.0]
    ok, bad_date_conf = True, []
    for t, r in zip(tx, rows):
        d, m, y = r[0].split("/")
        if t["date"] != f"{y}-{m}-{d}":
            ok = False
            bad_date_conf.append(doc["evidence"][f"{t['id']}.date"].get("confidence", 1.0))
        amt = Decimal(r[3] or r[2])
        if Decimal(t["amount"]["amount"]) != amt or Decimal(t["balance_after"]["amount"]) != Decimal(r[4]):
            ok = False
    return ok, bad_date_conf


def main(n: int) -> dict:
    pdf_front.OCR_MIN_DATE_CONF = 0.0
    rng, results, path = random.Random(2024), [], Path(tempfile.mkdtemp()) / "cal.pdf"
    for k in range(n):
        lay = random_layout(rng)
        lay.has_header = True
        rows = _pdf_rows(random.Random(2024 + k), rng.randint(8, 30))
        pdf, _ = render(rows, "1000.00", lay, rng, closing=rows[-1][4])
        path.write_bytes(to_scan(pdf, rng))
        doc = process(path, Params(currency="INR"))
        if doc["status"] == "ok":
            right, bad = truth_matches(doc, rows)
            confs = [e.get("confidence", 1.0) for key, e in doc["evidence"].items() if key.endswith(".date")]
            results.append({"outcome": "correct" if right else "WRONG", "min_date_conf": min(confs), "wrong_date_conf": bad,
                            "font": lay.font})
        else:
            results.append({"outcome": "refused:" + doc["error"]["code"], "font": lay.font, "why": doc["error"]["message"][:90]})
        print(f"scan {k + 1}/{n}: {results[-1]['outcome']}", file=sys.stderr)
    sweep = {}
    for t in THRESHOLDS:
        acc = [r for r in results if r["outcome"] in ("correct", "WRONG") and r["min_date_conf"] >= t]
        sweep[str(t)] = {"accepted": len(acc), "accepted_wrong": sum(r["outcome"] == "WRONG" for r in acc),
                         "abstained_by_confidence": sum(r["outcome"] in ("correct", "WRONG") and r["min_date_conf"] < t for r in results)}
    return {"scans": n, "outcomes": dict(Counter(r["outcome"] for r in results)),
            "outcomes_by_font": {f: dict(Counter(r["outcome"] for r in results if r["font"] == f)) for f in ("helv", "tiro", "cour")},
            "date_conf_sweep": sweep, "refusal_reasons": dict(Counter(r["why"] for r in results if "why" in r).most_common(12)),
            "note": "synthetic scans, EasyOCR, GPU. WRONG = accepted with a field that differs from the rendered truth."}


if __name__ == "__main__":
    res = main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
    (ROOT / "docs" / "evidence" / "ocr_calibration.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("outcomes", "outcomes_by_font", "date_conf_sweep")}, indent=1))
