"""Write the golden set (text PDFs, scans, images and every other case) to a directory, for use as test material elsewhere.

    python tests/characterise/export_fixtures.py OUT_DIR

Generating the PDFs needs PyMuPDF (private lab code), which some machines cannot load. CI runs this once and uploads the result,
so the permissive PDF backend can be developed and checked against the very files the engine is graded on.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from openbooks_lab.golden import build
except ModuleNotFoundError:
    from openbooks.golden import build


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    build(out, seed=7, n_random=4, scans=True)
    n = sum(1 for d in out.iterdir() if d.is_dir())
    print(f"wrote {n} cases to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
