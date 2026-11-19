"""Score the PDF/scan path on AgamiAI/Indian-Bank-Statements (third-party SYNTHETIC Indian statements, Apache-2.0).

Two separate questions, reported separately:
  extraction  - do the rows we read equal the ground-truth JSON (date, direction, amount, balance)? Measured before the gate.
  decision    - does the pipeline accept only statements whose printed balances actually tie? Truth = arithmetic on the JSON.
Many files in this dataset do NOT tie (the generator's balances break the running-total arithmetic), so refusing them is the
correct answer and an accept of one would be a false accept.
Usage: python scripts/eval_agami.py [files_per_kind] [kinds comma-separated]   -> docs/evidence/agami_eval.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from openbooks.statements import pdf_front as pf  # noqa: E402
from openbooks.pipeline import Params, Refusal, process  # noqa: E402

BASE = ROOT / "data" / "raw" / "agami_indian_bank_statements" / "train"
Q = Decimal("0.01")


def truth_rows(gt: dict) -> list[tuple[str, str, Decimal, Decimal]]:
    """(date, direction, amount, balance) of every non-failed transaction, whichever of the two schemas the file uses."""
    out = []
    for t in gt["transactions"]:
        if t.get("failed"):
            continue
        if "transaction_amount" in t:
            d = datetime.strptime(t["date"], "%d/%m/%Y").date().isoformat()
            out.append((d, "credit" if t["cr_dr"] == "CR" else "debit", Decimal(str(t["transaction_amount"])).quantize(Q),
                        Decimal(str(t["available_balance"])).quantize(Q)))
        else:
            cr = t.get("credit") is not None
            out.append((t["date"][:10], "credit" if cr else "debit", Decimal(str(t["credit"] if cr else t["debit"])).quantize(Q),
                        Decimal(str(t["balance"])).quantize(Q)))
    return out


def ties(gt: dict, rows) -> bool:
    bal = Decimal(str(gt["opening_balance"])).quantize(Q)
    for _, direction, amt, after in rows:
        bal += amt if direction == "credit" else -amt
        if bal != after:
            return False
    return True


def score_kind(kind: str, n: int) -> dict:
    d = BASE / f"India_Bank_Statement_{kind}"
    files = sorted(d.glob("*.pdf"))[:n]
    ext, dec, why = Counter(), Counter(), Counter()
    fields = Counter()
    secs = 0.0
    for pdf in files:
        gt = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
        rows = truth_rows(gt)
        t0 = time.time()
        extracted = False
        try:
            pages, method = pf.read_words(pdf, Params())
            data, _, _, _ = pf.extract_statement(pages, Params(currency="INR"), method)
            got = [(t["date"], t["direction"], Decimal(t["amount"]["amount"]), Decimal(t["balance_after"]["amount"]))
                   for t in data["transactions"]]
            extracted = True
            ext["extracted"] += 1
            ext["row_count_matches"] += len(got) == len(rows)
            for g, w in zip(got, rows):
                fields["rows"] += 1
                fields["date"] += g[0] == w[0]
                fields["direction"] += g[1] == w[1]
                fields["amount"] += g[2] == w[2]
                fields["balance"] += g[3] == w[3]
                fields["all_four"] += g == w
            ext["rows_missing_or_extra"] += abs(len(got) - len(rows))
        except Refusal as r:
            ext["extraction_refused:" + r.code] += 1
            why[r.message[:90]] += 1
        doc = process(pdf, Params(currency="INR"))
        consistent = ties(gt, rows)
        outcome = "accepted" if doc["status"] == "ok" else "refused:" + doc["error"]["code"]
        if consistent and doc["status"] == "ok":
            dec["consistent_accepted"] += 1
        elif consistent:
            dec["consistent_REFUSED"] += 1
        elif doc["status"] == "ok":
            dec["inconsistent_ACCEPTED(false accept)"] += 1
        else:
            dec["inconsistent_refused_correctly"] += 1
        dec["outcome:" + outcome] += 1
        secs += time.time() - t0
        print(f"{kind} {pdf.name}: extraction {'ok' if extracted else 'refused'} | truth {'ties' if consistent else 'does not tie'} | {outcome}",
              file=sys.stderr, flush=True)
    n_rows = fields["rows"] or 1
    return {"files": len(files), "seconds_per_file": round(secs / max(len(files), 1), 2), "extraction": dict(ext),
            "field_accuracy_over_rows": {k: round(fields[k] / n_rows, 5) for k in ("date", "direction", "amount", "balance", "all_four")},
            "rows_scored": fields["rows"], "decision": dict(dec), "extraction_refusal_reasons": dict(why.most_common(6))}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    kinds = (sys.argv[2] if len(sys.argv) > 2 else "Digital_Type1,Digital_Type2,Scanned_Type1,Scanned_Type2").split(",")
    res = {"origin": "third-party SYNTHETIC Indian statements (AgamiAI/Indian-Bank-Statements, Apache-2.0); not real customer data",
           "files_per_kind": n, "kinds": {k: score_kind(k, n) for k in kinds}}
    (ROOT / "docs" / "evidence" / "agami_eval.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: {"extraction": v["extraction"], "field_accuracy": v["field_accuracy_over_rows"], "decision": v["decision"]}
                      for k, v in res["kinds"].items()}, indent=1))
