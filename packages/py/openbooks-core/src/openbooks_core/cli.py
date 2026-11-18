"""Command line: openbooks run | report | link | eval | engine-info.

Exit codes:  0 every file released | 1 at least one file refused (a valid financial outcome) | 2 usage error or
nothing to do | 3 engine fault (broken install, unreadable input, out of memory). Code 3 never comes with a refusal
document, so a wrapper can tell "this document cannot be proven" from "the engine could not run".

`run --machine` prints one JSON object per line on stdout (one per file, then an `engine` line) and nothing else.
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import __version__
from .errors import EngineFault
from .evidence import sha256_file
from .grade import run_eval
from .output import write_atomic
from .params import Params
from .process import dumps, process
from .registry import LAYOUT_API_VERSION, _entry_points, default_registry
from .report import run_report
from .schema import SCHEMA_VERSION

EXIT_OK, EXIT_REFUSED, EXIT_USAGE, EXIT_ENGINE = 0, 1, 2, 3


def _add_params(p: argparse.ArgumentParser) -> None:
    p.add_argument("--currency")
    p.add_argument("--opening", help="opening balance, if the file does not state one")
    p.add_argument("--account")
    p.add_argument("--allow-derived-opening", action="store_true")
    p.add_argument("--date-order", choices=("dmy", "mdy"), help="day/month order of numeric dates; inferred from the file when omitted")
    p.add_argument("--no-ocr", action="store_true", help="refuse scans instead of running OCR")
    p.add_argument("--model", action="store_true", help="typed-head cross-check on PDFs/scans (needs the model assets)")


def _params(ap: argparse.ArgumentParser, a: argparse.Namespace) -> Params:
    try:
        opening = Decimal(a.opening) if a.opening else None
    except InvalidOperation:
        ap.error(f"--opening must be a plain number like 1000.00, got {a.opening!r}")
    return Params(a.currency, opening, a.account, a.allow_derived_opening, not a.no_ocr, a.model, a.date_order)


def engine_info() -> dict:
    reg = default_registry()
    return {"name": "openbooks-core", "version": __version__, "schema_version": SCHEMA_VERSION, "layout_api": LAYOUT_API_VERSION,
            "python": sys.version.split()[0], "layouts": sorted(reg.installed_layouts()),
            "frontends": sorted(n for n in ("document",) if _has_frontend(reg, n)), "linker": reg.linker() is not None}


def _has_frontend(reg, name: str) -> bool:
    try:
        reg.frontend(name)
    except Exception:  # noqa: BLE001 - a missing or broken frontend is reported as absent here; doctor explains why
        return False
    return True


def _run(ap: argparse.ArgumentParser, a: argparse.Namespace) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    p = _params(ap, a)
    rc = EXIT_OK
    for f in a.files:
        sha = sha256_file(Path(f))
        target = out / f"{sha}.json"
        # No reuse of an earlier <sha>.json: the same bytes give a different result under another --currency,
        # --opening or --model, and a stale refusal or release must never be returned silently.
        doc = process(f, p, strict=True)
        write_atomic(target, dumps(doc))
        err = doc.get("error", {})
        if a.machine:
            line = {"file": Path(f).name, "status": doc["status"], "code": err.get("code"), "output": str(target)}
            if err.get("internal"):
                line["internal"] = True
            sys.stdout.write(json.dumps(line, sort_keys=True) + "\n")
        else:
            sys.stdout.write(f"{Path(f).name}: {doc['status']} {err.get('code', '')} -> {target.name}\n")
        if doc["status"] != "ok":
            rc = EXIT_REFUSED
    if a.machine:
        sys.stdout.write(json.dumps({"engine": engine_info()}, sort_keys=True) + "\n")
    return rc


def _plugin_commands(sub) -> dict:
    """Subcommands contributed by installed packages (entry-point group openbooks.commands, name = the subcommand).
    A command object has `help`, `add_arguments(parser)` and `run(args) -> int`. A command that fails to load is reported
    on stderr and skipped; it must not take the rest of the CLI down."""
    out: dict = {}
    for ep in _entry_points("commands"):
        try:
            cmd = ep.load()
            cmd.add_arguments(sub.add_parser(ep.name, help=cmd.help))
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"openbooks: the {ep.name!r} command could not be loaded ({type(e).__name__}: {e})\n")
            continue
        out[ep.name] = cmd
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="openbooks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="write one openbooks.v1 JSON per input file")
    r.add_argument("files", nargs="+")
    r.add_argument("--out", default="out")
    r.add_argument("--machine", action="store_true", help="print one JSON object per line on stdout (for wrappers)")
    _add_params(r)
    e = sub.add_parser("eval", help="run the golden set")
    e.add_argument("root")
    lk = sub.add_parser("link", help="link settlement payouts and FIRA credits to bank credits (needs a linker)")
    lk.add_argument("files", nargs="+")
    lk.add_argument("--out", default="links.json")
    rp = sub.add_parser("report", help="run every file in a folder, link the released ones, write report.json")
    rp.add_argument("folder", help="a params.json in the folder gives per-file currency/opening/account")
    rp.add_argument("--out", default="out")
    _add_params(rp)
    sub.add_parser("engine-info", help="print the engine version, contract version and installed layouts as JSON")
    plugins = _plugin_commands(sub)
    a = ap.parse_args(argv)
    try:
        if a.cmd in plugins:
            return plugins[a.cmd].run(a)
        if a.cmd == "engine-info":
            sys.stdout.write(json.dumps(engine_info(), indent=2, sort_keys=True) + "\n")
            return EXIT_OK
        if a.cmd == "eval":
            return run_eval(Path(a.root))
        if a.cmd == "report":
            return run_report(Path(a.folder), Path(a.out), _params(ap, a))
        if a.cmd == "link":
            linker = default_registry().linker()
            if linker is None:
                sys.stderr.write("openbooks link: no linker is installed (matching is not part of the open packages)\n")
                return EXIT_USAGE
            return linker.run_link(a.files, a.out)
        return _run(ap, a)
    except (EngineFault, OSError, MemoryError) as e:
        sys.stderr.write(f"openbooks: engine error: {type(e).__name__}: {e}\n")
        return EXIT_ENGINE


if __name__ == "__main__":
    sys.exit(main())
