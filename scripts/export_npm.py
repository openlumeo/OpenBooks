"""Export the source mirror for provenance builds of @lumeo_hq/openbooks.

python scripts/export_npm.py OUT_DIR [--dry-run]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import export_public as ex

SOURCE = "packages/js"
PACKAGE = "cli"
ROOT_FILES = ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "tsconfig.base.json", "tsconfig.json")
EXCLUDE = ["**/node_modules/**", "**/dist/**", "**/*.tsbuildinfo", "**/test/**", "**/tests/**", "**/vitest.config.ts"]
OVERLAY = {"README.md": "README.md", "publish.yml": ".github/workflows/publish.yml", "gitignore": ".gitignore"}


def selected() -> list[str]:
    """Mirror-relative paths of the files copied from packages/js."""
    wanted = [*ROOT_FILES, f"{PACKAGE}/**"]
    files = (path.removeprefix(f"{SOURCE}/") for path in ex.tracked_files(SOURCE))
    return [rel for rel in files if ex.matches(rel, wanted) and not ex.matches(rel, EXCLUDE)]


def build(licence: bytes | None) -> dict[str, bytes]:
    files = {rel: ex.read_source(f"{SOURCE}/{rel}") for rel in selected()}
    for src, dest in OVERLAY.items():
        files[dest] = ex.read_source(f"tools/public-npm/{src}")
    files["NOTICE"] = ex.read_source("tools/public/NOTICE")
    if licence is not None:
        files["LICENSE"] = licence
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="list and scan without writing")
    args = ap.parse_args(argv)

    try:
        files = build(ex.read_source("tools/public/LICENSE"))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        ap.error(f"could not read npm mirror sources: {exc}")
    hits = ex.scan_tree(files)
    if hits:
        print("private material found; nothing written:", *hits, sep="\n  ", file=sys.stderr)
        return 1
    if args.dry_run:
        print(*sorted(files), sep="\n")
        return 0
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        print(f"{args.out} is not empty", file=sys.stderr)
        return 2
    for rel, data in files.items():
        target = args.out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
