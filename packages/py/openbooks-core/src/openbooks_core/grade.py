"""The grader: run a golden set (one directory per case with expected.json) and report mismatches and false accepts."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from .params import Params
from .process import process


def run_eval(root: Path) -> int:
    bad = false_accepts = 0
    cases = sorted(d for d in root.iterdir() if d.is_dir())
    for d in cases:
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        src = next(f for f in d.iterdir() if f.name != "expected.json")
        pr = exp.get("params", {})
        doc = process(src, Params(pr.get("currency"), Decimal(pr["opening"]) if "opening" in pr else None,
                                  pr.get("account"), pr.get("allow_derived_opening", False)))
        got = (doc["status"], doc.get("error", {}).get("code"))
        want = (exp["status"], exp.get("code"))
        codes = exp.get("code") if isinstance(exp.get("code"), list) else None
        if (got[0] != want[0] or got[1] not in codes) if codes else got != want:
            bad += 1
            false_accepts += exp["status"] == "refused" and doc["status"] == "ok"
            print(f"MISMATCH {d.name}: want {want} got {got}")
    print(f"cases={len(cases)} mismatches={bad} false_accepts={false_accepts}")
    return 1 if bad else 0
