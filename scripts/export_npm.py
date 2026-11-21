"""Build the minimal public tree that publishes the six @lumeo_hq npm packages with provenance.

    python scripts/export_npm.py OUT_DIR [--dry-run]

npm only issues provenance for a public source repository. This private repository stays private, so the six TypeScript
packages are mirrored to a small public repository (Sagexd08/openbooks-js) whose only job is to build and publish them.
The mirror holds the package sources and nothing else: no engine, model, server, web app, tests, docs or history.
Start the public repository from one fresh commit; never push this repository's history to it.

Layout: packages/js/<pkg>/... becomes <pkg>/... at the mirror root. The tree is scanned with the same forbidden-text rules as
scripts/export_public.py and the export exits 1 on any hit. It runs no git commands and publishes nothing.
"""
from __future__ import annotations

import argparse
import fnmatch
import shutil
import sys
from pathlib import Path

import export_public as ex

ROOT = ex.ROOT
SOURCE = ROOT / "packages" / "js"
PACKAGES = ("core", "statements", "gateways", "tax", "doctor", "cli")
ROOT_FILES = ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "tsconfig.base.json", "tsconfig.json")
# Left out of the mirror: build output, tests (they need the private engine), and the schema-sync tooling that reads private paths.
EXCLUDE = ["**/node_modules/**", "**/dist/**", "**/*.tsbuildinfo", "**/test/**", "**/tests/**", "core/scripts/**", "**/vitest.config.ts"]
# tools/public-npm/<src> -> <dest> in the mirror
OVERLAY = {"README.md": "README.md", "publish.yml": ".github/workflows/publish.yml", "gitignore": ".gitignore"}


def selected() -> list[str]:
    """Mirror-relative paths of the files copied from packages/js."""
    wanted = [*ROOT_FILES, *(f"{pkg}/**" for pkg in PACKAGES)]
    out = []
    for p in sorted(SOURCE.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(SOURCE).as_posix()
        if any(fnmatch.fnmatch(rel, w) for w in wanted) and not any(fnmatch.fnmatch(rel, e) for e in EXCLUDE):
            out.append(rel)
    return out


def build(licence: bytes | None) -> dict[str, bytes]:
    files = {rel: (SOURCE / rel).read_bytes() for rel in selected()}
    for src, dest in OVERLAY.items():
        path = ROOT / "tools" / "public-npm" / src
        if path.exists():
            files[dest] = path.read_bytes()
    files["NOTICE"] = (ROOT / "tools" / "public" / "NOTICE").read_bytes()
    if licence is not None:
        files["LICENSE"] = licence
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="list and scan without writing")
    args = ap.parse_args(argv)

    licence = None if args.dry_run else (ROOT / "tools" / "public" / "LICENSE").read_bytes()
    files = build(licence)
    hits = ex.scan_tree(files)
    if hits:
        print("private material found; nothing written:", *hits, sep="\n  ", file=sys.stderr)
        return 1
    if args.dry_run:
        print(*sorted(files), sep="\n")
        return 0
    if args.out.exists() and any(args.out.iterdir()):
        print(f"{args.out} is not empty", file=sys.stderr)
        return 2
    for rel, data in files.items():
        target = args.out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
