"""openbooks doctor: is this installation able to do what it claims?

Exit codes: 0 no check failed (warnings allowed, unless --strict) | 1 a check failed | 2 usage error | 3 doctor itself crashed.
--json prints one document {schema: "openbooks.doctor.v1", ok, summary, checks: [...]}. Doctor reads no user documents and
prints no document content.
"""
from __future__ import annotations

import argparse
import json
import sys

from .checks import FAIL, PASS, SKIP, WARN, run_checks

SCHEMA = "openbooks.doctor.v1"
SYMBOL = {PASS: "ok  ", WARN: "warn", FAIL: "FAIL", SKIP: "skip"}


def report(checks, *, strict: bool = False) -> dict:
    summary = {s: sum(c.status == s for c in checks) for s in (PASS, WARN, FAIL, SKIP)}
    ok = summary[FAIL] == 0 and not (strict and summary[WARN])
    return {"schema": SCHEMA, "ok": ok, "summary": summary, "checks": [c.as_dict() for c in checks]}


def render(rep: dict) -> str:
    lines = []
    for c in rep["checks"]:
        lines.append(f"[{SYMBOL[c['status']]}] {c['id']}: {c['detail']}")
        if c.get("fix") and c["status"] in (WARN, FAIL):
            lines.append(f"       fix: {c['fix']}")
    s = rep["summary"]
    lines.append(f"{s[PASS]} passed, {s[WARN]} warnings, {s[FAIL]} failed, {s[SKIP]} skipped -> " + ("OK" if rep["ok"] else "NOT OK"))
    return "\n".join(lines) + "\n"


def exit_code(rep: dict) -> int:
    return 0 if rep["ok"] else 1


class DoctorCommand:
    help = "check this installation: dependencies, providers, model integrity and a built-in proven-or-refused self-test"

    def add_arguments(self, p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true", help="machine-readable output")
        p.add_argument("--strict", action="store_true", help="treat warnings as failures")
        p.add_argument("--deep", action="store_true", help="also import PyTorch and load the model (slower)")

    def run(self, a: argparse.Namespace) -> int:
        try:
            rep = report(run_checks(deep=a.deep), strict=a.strict)
        except Exception as e:  # noqa: BLE001 - doctor must say so, not pretend the installation is fine
            sys.stderr.write(f"openbooks doctor crashed: {type(e).__name__}: {e}\n")
            return 3
        sys.stdout.write(json.dumps(rep, indent=2) + "\n" if a.json else render(rep))
        return exit_code(rep)


COMMAND = DoctorCommand()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="openbooks-doctor", description=COMMAND.help)
    COMMAND.add_arguments(ap)
    return COMMAND.run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
