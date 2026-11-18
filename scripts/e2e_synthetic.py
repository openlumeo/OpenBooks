"""End to end on a SYNTHETIC Indian pack: files in -> release/refuse -> cross-file links -> scored report.

Pack = every case of the golden generator, plus a bank CSV whose credit matches the Razorpay settlement.
Truth is known by construction, so this scores the whole chain (decision + link), not just parsing.
Labelled synthetic (own generator); real-data scores live in docs/evidence/real_ocr_eval.json.
Usage: python scripts/e2e_synthetic.py [--scans] [--model]  -> docs/evidence/e2e_synthetic[_model][_scans].json
Also checks accuracy (decisions, false accepts) and that every output matches the pipeline schema (released) or typed-refusal shape.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from openbooks_lab.golden import RZP_HEAD, RZP_OK, build  # noqa: E402
from openbooks.pipeline import Params, process, run_report, validate_output  # noqa: E402


def shape_problem(doc: dict) -> str:
    """Independent output-contract check: released docs re-validated against the pipeline SCHEMA; refusals must be typed, with no data."""
    if doc["status"] == "ok":
        try:
            validate_output(doc)
        except Exception as e:  # noqa: BLE001
            return f"released doc fails schema: {e}"
        return ""
    err = doc.get("error") or {}
    if doc.get("data") is not None or not {"code", "message", "file_sha256"} <= set(err) or doc["status"] != "refused":
        return "refusal is not {status:refused, data:null, error:{code,message,file_sha256}}"
    return ""


def main(scans: bool, model: bool = False) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="ob_e2e_"))
    gold, pack, out = tmp / "golden", tmp / "pack", tmp / "out"
    pack.mkdir()
    build(gold, 7, 0, scans)
    want: dict[str, tuple] = {}
    for d in sorted(p for p in gold.iterdir() if p.is_dir()):
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        src = next(f for f in d.iterdir() if f.name != "expected.json")
        name = f"{d.name}{src.suffix}"
        shutil.copy(src, pack / name)
        want[name] = (exp["status"], exp.get("code"), exp.get("params"))
    (pack / "zz_rzp.csv").write_text("\n".join([RZP_HEAD] + RZP_OK) + "\n", encoding="utf-8")
    (pack / "zz_bank.csv").write_text(
        "Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n08/01/2026,RAZORPAY SETL,,77.64,1077.64\n", encoding="utf-8")

    per_file = {n: w[2] for n, w in want.items() if w[2]}
    per_file["zz_bank.csv"] = {"currency": "INR", "opening": "1000.00"}
    (pack / "params.json").write_text(json.dumps(per_file), encoding="utf-8")
    wrong, false_accepts, bad_shape, expected_ok, released_ok = [], 0, [], 0, 0
    for name, (status, code, params) in want.items():
        pr = params or {}
        got = process(pack / name, Params(pr.get("currency"), Decimal(pr["opening"]) if "opening" in pr else None,
                                          pr.get("account"), pr.get("allow_derived_opening", False), ocr=scans, model=model))
        codes = code if isinstance(code, list) else [code]
        ok = got["status"] == status and (status == "ok" or got["error"]["code"] in codes)
        if not ok:
            wrong.append(name)
            false_accepts += status == "refused" and got["status"] == "ok"
        expected_ok += status == "ok"
        released_ok += ok and status == "ok"
        problem = shape_problem(got)
        if problem:
            bad_shape.append(f"{name}: {problem}")
    run_report(pack, out, Params(ocr=scans, model=model))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    pair = tmp / "pair"
    pair.mkdir()
    shutil.copy(pack / "ok_razorpay.csv", pair / "ok_razorpay.csv")
    shutil.copy(pack / "zz_bank.csv", pair / "zz_bank.csv")
    (pair / "params.json").write_text(json.dumps({"zz_bank.csv": per_file["zz_bank.csv"]}), encoding="utf-8")
    run_report(pair, tmp / "pair_out", Params(ocr=False))
    pair_report = json.loads((tmp / "pair_out" / "report.json").read_text(encoding="utf-8"))
    res = {"origin": "SYNTHETIC (own generator), Indian formats; not real exports", "model": model, "scans": scans, "cases": len(want),
           "decision_accuracy": round(1 - len(wrong) / len(want), 4), "released_of_expected_ok": f"{released_ok}/{expected_ok}",
           "schema_violations": bad_shape, "decision_mismatches": wrong, "false_accepts": false_accepts, "released_in_report": report["released"], "refused_by_code": report["refused"],
           "crowded_pack": {"links": len(report["links"]), "ambiguous_not_linked": len(report["ambiguous"]),
                            "all_links_proven": all(x["assertion"]["passed"] for x in report["links"])},
           "isolated_pair": {"links": len(pair_report["links"]), "expected": 1,
                             "amounts": [x["amount"]["amount"] for x in pair_report["links"]]}}
    tag = ("_model" if model else "") + ("_scans" if scans else "")
    (ROOT / "docs" / "evidence" / f"e2e_synthetic{tag}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return res


if __name__ == "__main__":
    r = main("--scans" in sys.argv, "--model" in sys.argv)
    print(json.dumps(r, indent=1))
    bad = r["schema_violations"] or r["decision_mismatches"] or r["false_accepts"] or r["isolated_pair"]["links"] != 1 or not r["crowded_pack"]["all_links_proven"]
    sys.exit(1 if bad else 0)
