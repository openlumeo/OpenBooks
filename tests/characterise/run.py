"""Run the characterisation corpus through `process` and record or verify the results.

  python tests/characterise/run.py record [--section main|pdf]   write baseline_<section>.json (do this on the baseline commit)
  python tests/characterise/run.py verify [--section ...]        compare to the stored baseline; exit 1 on any difference

Each result is (status, code, sha256 of the exact JSON the CLI would write). The hash covers every field, so any change
to a released document, to evidence, to an assertion or to a refusal message shows up.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
pass

from corpus import PARAM_VARIANTS, Case, build_corpus, have_fitz  # noqa: E402


def _params(base: dict, extra: dict):
    from openbooks.pipeline import Params

    merged = {**extra, **{k: v for k, v in base.items()}}
    opening = merged.get("opening")
    return Params(currency=merged.get("currency"), opening=Decimal(opening) if opening else None,
                  account=merged.get("account"), allow_derived_opening=merged.get("allow_derived_opening", False),
                  date_order=merged.get("date_order"))


def run_case(case: Case, variant: str) -> dict:
    from openbooks.pipeline import dumps, process

    doc = process(case.path, _params(case.params, PARAM_VARIANTS[variant]))
    if case.path.suffix.lower() == ".pdf":  # two PDF libraries report slightly different box coordinates for the same text
        for ev in doc.get("evidence", {}).values():
            ev.pop("bbox", None)
            ev.pop("confidence", None)
        # A wrapped description line sits midway between two rows; which row it joins was float noise in the old reader. Compare the
        # words each document holds, not their split between neighbouring rows (compare_pdf_backends.py checks the same thing).
        txs = (doc.get("data") or {}).get("transactions") or []
        if txs:
            doc["data"]["description_words"] = sorted(w for t in txs for w in str(t.get("description") or "").split())
            for t in txs:
                t["description"] = ""
    if case.path.suffix.lower() in (".xlsx", ".pdf"):  # generators stamp times/ids, so the file's own hash differs per build
        if "file" in doc:
            doc["file"]["sha256"] = "-"
        if "error" in doc:
            doc["error"]["file_sha256"] = "-"
    return {"status": doc["status"], "code": doc.get("error", {}).get("code"),
            "sha256": hashlib.sha256(dumps(doc).encode("utf-8")).hexdigest()}


def collect(section: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for case in build_corpus(section):
        for variant in PARAM_VARIANTS:
            out[f"{case.id}|{variant}"] = run_case(case, variant)
    return out


def baseline_path(section: str) -> Path:
    return HERE / f"baseline_{section}.json"


def diff(old: dict, new: dict) -> list[str]:
    msgs = [f"missing now: {k}" for k in old.keys() - new.keys()]
    msgs += [f"new case not in baseline: {k}" for k in new.keys() - old.keys()]
    msgs += [f"CHANGED {k}: {old[k]['status']}/{old[k]['code']} -> {new[k]['status']}/{new[k]['code']}"
             for k in old.keys() & new.keys() if old[k] != new[k]]
    return sorted(msgs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("record", "verify"))
    ap.add_argument("--section", choices=("main", "pdf"), default="main")
    a = ap.parse_args(argv)
    if a.section == "pdf" and not have_fitz():
        print("PyMuPDF is not importable here; the pdf section runs in CI")
        return 0
    results = collect(a.section)
    path = baseline_path(a.section)
    if a.mode == "record":
        path.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"recorded {len(results)} results -> {path.name}")
        return 0
    problems = diff(json.loads(path.read_text(encoding="utf-8")), results)
    for m in problems:
        print(m)
    print(f"{len(results)} results, {len(problems)} differences")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
