"""REAL-data score for the OCR front end: SROIE 2019 test receipts (real scanned/photographed receipts, not statements).

Question: when a receipt is OCR'd with the same reader the scan path uses, is the labelled TOTAL read exactly as one amount
token, and the labelled DATE as a date? Reported with OCR confidence so the abstain threshold can be judged on real scans.
Internal evaluation only (dataset licence is 'other'); nothing from SROIE is used for training or shipped.
Usage: python scripts/eval_real_ocr.py [n_images]  -> docs/evidence/real_ocr_eval.json
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from openbooks_statements.pdf_front import read_words  # noqa: E402
from openbooks.pipeline import Params  # noqa: E402

TEST = ROOT / "data" / "raw" / "kaggle_urbikn__sroie-datasetv2" / "SROIE2019" / "test"
AMOUNT = re.compile(r"(\d[\d,]*\.\d{2})$")
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d", "%d %b %Y", "%d-%b-%Y", "%d.%m.%Y", "%d.%m.%y")


def amount_tokens(words) -> list[tuple[str, float]]:
    out = []
    for pg in words:
        for w in pg:
            t = re.sub(r"^(RM|MYR|\$)", "", w.text.upper().replace(",", ""))
            m = AMOUNT.search(t)
            if m:
                out.append((m.group(1), w.conf or 1.0))
    return out


def date_found(words, truth: str) -> tuple[bool, float]:
    want = None
    for f in DATE_FORMATS:
        try:
            want = datetime.strptime(truth.strip(), f).date()
            break
        except ValueError:
            continue
    if want is None:
        return False, 0.0
    toks = [w for pg in words for w in pg]
    for i in range(len(toks)):
        for n in (1, 2, 3):
            raw = " ".join(w.text for w in toks[i:i + n])
            for f in DATE_FORMATS:
                try:
                    if datetime.strptime(raw, f).date() == want:
                        return True, min(w.conf or 1.0 for w in toks[i:i + n])
                except ValueError:
                    continue
    return False, 0.0


def main(n: int) -> dict:
    imgs = sorted((TEST / "img").glob("*.jpg"))[:n]
    tot_hit = date_hit = 0
    tot_confs, date_confs = [], []
    for k, img in enumerate(imgs, 1):
        gt = json.loads((TEST / "entities" / f"{img.stem}.txt").read_text(encoding="utf-8"))
        try:
            pages, _ = read_words(img, Params())
        except Exception as e:
            print(img.name, "unreadable", e, file=sys.stderr)
            continue
        total = re.sub(r"[^\d.]", "", gt.get("total", ""))
        hits = [c for t, c in amount_tokens(pages) if t == total]
        if hits:
            tot_hit += 1
            tot_confs.append(max(hits))
        ok, c = date_found(pages, gt.get("date", ""))
        date_hit += ok
        if ok:
            date_confs.append(c)
        if k % 10 == 0:
            print(f"{k}/{len(imgs)} total_found={tot_hit} date_found={date_hit}", file=sys.stderr, flush=True)
            save(summary(k, tot_hit, date_hit, tot_confs, date_confs, partial=k < len(imgs)))
    return summary(len(imgs), tot_hit, date_hit, tot_confs, date_confs, partial=False)


def share(xs, lo):
    return round(sum(1 for x in xs if x >= lo) / max(len(xs), 1), 4)


def summary(n, tot_hit, date_hit, tot_confs, date_confs, partial: bool) -> dict:
    d = max(n, 1)
    return {"origin": "REAL receipts (SROIE 2019 test, photographed/scanned). Not bank statements. Internal evaluation only.",
            "partial": partial, "images": n, "total_read_exactly": round(tot_hit / d, 4), "date_read_exactly": round(date_hit / d, 4),
            "of_totals_read_share_with_conf_at_least": {str(t): share(tot_confs, t) for t in (0.5, 0.7, 0.9)},
            "of_dates_read_share_with_conf_at_least": {str(t): share(date_confs, t) for t in (0.5, 0.7, 0.9)},
            "note": "recall of one labelled field per receipt; receipts are noisier than the synthetic scans, so use this as the real-scan reference"}


def save(res: dict) -> None:
    (ROOT / "docs" / "evidence" / "real_ocr_eval.json").write_text(json.dumps(res, indent=2), encoding="utf-8")


if __name__ == "__main__":
    res = main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
    save(res)
    print(json.dumps(res, indent=1))
