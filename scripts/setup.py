#!/usr/bin/env python
"""One command to install every OpenBooks package from a source checkout.

    python scripts/setup.py              # all Python packages + engine service + JS workspace + web app
    python scripts/setup.py --scan       # also OCR for scans and the typed heads (EasyOCR, PyTorch, Pillow)
    python scripts/setup.py --no-js      # Python only
    python scripts/setup.py --dry-run    # print the commands, run nothing

Python packages are installed editable in ONE pip call, so the private lab and the server resolve
`openbooks` to the local copy instead of fetching it from PyPI.
Installing (not PYTHONPATH) is required: layouts register through entry points.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "packages" / "py"

# Order is cosmetic; pip resolves them together.
PY_PACKAGES = [
    PY / "openbooks-lab",
    PY / "openbooks",
    ROOT / "server",
]
JS_DIRS = [ROOT / "packages" / "js", ROOT / "web"]


def run(cmd: list[str], cwd: Path, dry: bool) -> None:
    print(f"\n$ ({cwd.relative_to(ROOT) or '.'}) {' '.join(cmd)}", flush=True)
    if not dry:
        subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan", action="store_true", help="include OCR and typed heads (large: PyTorch)")
    ap.add_argument("--no-py", action="store_true", help="skip the Python packages")
    ap.add_argument("--no-js", action="store_true", help="skip packages/js and web (no Node/pnpm needed)")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = ap.parse_args()

    if sys.version_info < (3, 11):
        print("OpenBooks needs Python 3.11 or newer.", file=sys.stderr)
        return 2

    if not args.no_py:
        pip = [sys.executable, "-m", "pip", "install"]
        for p in PY_PACKAGES:
            name = p.name
            extra = "[scan]" if name == "openbooks" and args.scan else ""
            pip += ["-e", f"{p}{extra}"]
        run(pip, ROOT, args.dry_run)

    if not args.no_js:
        pnpm = shutil.which("pnpm")
        if not pnpm and not args.dry_run:
            print("pnpm not found. Install it (`npm i -g pnpm` or `corepack enable`) or pass --no-js.",
                  file=sys.stderr)
            return 2
        for d in JS_DIRS:
            run([pnpm or "pnpm", "install"], d, args.dry_run)

    print("\nDone." if not args.dry_run else "\nDry run only; nothing was installed.")
    if not args.no_py and not args.dry_run:
        print("Check it:  openbooks doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
