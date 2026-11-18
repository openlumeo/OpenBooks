"""Command line: openbooks run | report | link | eval. Arguments, exit codes and output paths are unchanged from 0.1."""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from .evidence import sha256_file
from .grade import run_eval
from .params import Params
from .process import dumps, process
from .registry import default_registry
from .report import run_report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="openbooks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="write one openbooks.v1 JSON per input file")
    r.add_argument("files", nargs="+")
    r.add_argument("--out", default="out")
    r.add_argument("--currency")
    r.add_argument("--opening", help="opening balance, if the file does not state one")
    r.add_argument("--account")
    r.add_argument("--allow-derived-opening", action="store_true")
    r.add_argument("--date-order", choices=("dmy", "mdy"), help="day/month order of numeric dates; inferred from the file when omitted")
    r.add_argument("--no-ocr", action="store_true", help="refuse scans instead of running OCR")
    r.add_argument("--model", action="store_true", help="typed-head cross-check on PDFs/scans (needs models/roles_head.pt)")
    e = sub.add_parser("eval", help="run the golden set")
    e.add_argument("root")
    lk = sub.add_parser("link", help="link settlement payouts and FIRA credits to bank credits")
    lk.add_argument("files", nargs="+")
    lk.add_argument("--out", default="links.json")
    rp = sub.add_parser("report", help="run every file in a folder, link the released ones, write report.json")
    rp.add_argument("folder", help="a params.json in the folder gives per-file currency/opening/account")
    rp.add_argument("--out", default="out")
    rp.add_argument("--currency")
    rp.add_argument("--opening", help="opening balance, if the files do not state one")
    rp.add_argument("--account")
    rp.add_argument("--allow-derived-opening", action="store_true")
    rp.add_argument("--date-order", choices=("dmy", "mdy"))
    rp.add_argument("--no-ocr", action="store_true")
    rp.add_argument("--model", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "eval":
        return run_eval(Path(a.root))
    if a.cmd == "report":
        return run_report(Path(a.folder), Path(a.out),
                          Params(a.currency, Decimal(a.opening) if a.opening else None, a.account,
                                 a.allow_derived_opening, not a.no_ocr, a.model, a.date_order))
    if a.cmd == "link":
        linker = default_registry().linker()
        if linker is None:
            sys.stderr.write("openbooks link: no linker is installed (matching is not part of the open packages)\n")
            return 2
        return linker.run_link(a.files, a.out)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    p = Params(a.currency, Decimal(a.opening) if a.opening else None, a.account, a.allow_derived_opening,
               not a.no_ocr, a.model, a.date_order)
    rc = 0
    for f in a.files:
        sha = sha256_file(Path(f))
        target = out / f"{sha}.json"
        # No reuse of an earlier <sha>.json: the same bytes give a different result under another --currency,
        # --opening or --model, and a stale refusal or release must never be returned silently.
        doc = process(f, p)
        target.write_text(dumps(doc), encoding="utf-8")
        err = doc.get("error", {})
        sys.stdout.write(f"{Path(f).name}: {doc['status']} {err.get('code', '')} -> {target.name}\n")
        rc |= doc["status"] != "ok"
    return rc


if __name__ == "__main__":
    sys.exit(main())
