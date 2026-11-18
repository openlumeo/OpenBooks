"""Build the public Open Books tree from this (private) repository into an empty directory.

    python scripts/export_public.py OUT_DIR --licence-file PATH_TO_LICENCE_TEXT [--dry-run]

What it does: copies an explicit allow-list of paths (nothing is public by default), overlays the public README, CI, security and
contribution files from tools/public/, writes the licence file you give it, then scans the result for private material and exits
1 if it finds any. It runs no git commands and publishes nothing. The new repository should start with a single fresh commit:
never push this repository's history (it holds the training recipe, evidence, weights lineage and the hosted product).

--dry-run lists what would be copied and scans in memory; it needs no licence file. A real export refuses to run without one,
because a public tree without a licence grants nobody any rights.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Nothing is public unless it is listed here.
INCLUDE = [
    "packages/py/openbooks-core/**", "packages/py/openbooks-gateways/**", "packages/py/openbooks-tax/**",
    "packages/py/openbooks-statements/**", "packages/py/openbooks-doctor/**", "packages/py/openbooks/**",
    "packages/js/**",
    "models/roles_head.pt", "models/roles_calibration.json", "models/roles_model_card.json",  # the statements wheel ships these
    "tests/packaging/**", "tests/test_cli_machine.py", "tests/test_model_card.py",
]
# Never copied even when an include matches.
EXCLUDE = ["**/node_modules/**", "**/dist/**", "**/__pycache__/**", "**/*.egg-info/**", "**/.pytest_cache/**", "**/.venv/**",
           "**/*.tsbuildinfo", "**/*.pyc", "**/build/**"]
# tools/public/<src> -> <dest> in the export
OVERLAY = {"README.md": "README.md", "CONTRIBUTING.md": "CONTRIBUTING.md", "SECURITY.md": "SECURITY.md", "THIRD_PARTY.md": "THIRD_PARTY.md",
           "ci.yml": ".github/workflows/ci.yml", "gitignore": ".gitignore", "pytest.toml": "pyproject.toml"}

# Text that must not appear in the public tree. A hit fails the export.
FORBIDDEN = {
    "private package or module": [r"openbooks_lab", r"lumeo-openbooks-lab", r"lumeo_private"],
    "training recipe or internal weights": [r"jepa_encoder", r"train_roles", r"score_family_candidate", r"promote\.py", r"roles_manifest"],
    "third-party training data": [r"\bCORD\b", r"\bFUNSD\b", r"\bSROIE\b", r"invoice-ner"],
    "internal documents": [r"HANDOFF", r"format_catalog", r"docs/evidence", r"PRODUCT\.md", r"docs/research"],
    "hosted product": [r"ANTHROPIC_API_KEY", r"openbooks_server", r"OPENBOOKS_ENGINE_URL"],
    "personal or machine details": [r"Rohit", r"Victus", r"gmail\.com", r"C:\\{1,2}Users", r"/Users/"],
}
# Files allowed to mention forbidden strings because their job is to forbid them.
SCAN_ALLOW = {"tests/packaging/test_wheels.py": {"private package or module", "training recipe or internal weights"},
              "scripts/export_public.py": set(FORBIDDEN)}
TEXT_SUFFIXES = {".py", ".ts", ".mjs", ".json", ".toml", ".md", ".yml", ".yaml", ".txt", ".cfg", ".lock", ".gitignore", ""}
BINARY_ALLOWED = {"models/roles_head.pt"}
EMPTY_MARKERS = {"py.typed"}  # empty PEP 561 marker files


def matches(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p.replace("/**", "/*")) for p in patterns)


def selected() -> list[str]:
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if matches(rel, INCLUDE) and not matches(rel, EXCLUDE):
            out.append(rel)
    return out


def scan_text(rel: str, text: str) -> list[str]:
    allowed = SCAN_ALLOW.get(rel, set())
    hits = []
    for kind, pats in FORBIDDEN.items():
        if kind in allowed:
            continue
        for pat in pats:
            for m in re.finditer(pat, text):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{rel}:{line}: {kind}: {m.group(0)!r}")
    return hits


def scan_tree(files: dict[str, bytes]) -> list[str]:
    hits = []
    for rel, data in sorted(files.items()):
        suffix = Path(rel).suffix.lower()
        if suffix in TEXT_SUFFIXES or Path(rel).name in {".gitignore"}:
            try:
                hits += scan_text(rel, data.decode("utf-8"))
            except UnicodeDecodeError:
                hits.append(f"{rel}: not valid UTF-8 text")
        elif rel not in BINARY_ALLOWED and Path(rel).name not in EMPTY_MARKERS:
            hits.append(f"{rel}: unexpected binary or unknown file type")
    return hits


def build(licence: bytes | None) -> dict[str, bytes]:
    files = {rel: (ROOT / rel).read_bytes() for rel in selected()}
    for src, dest in OVERLAY.items():
        p = ROOT / "tools" / "public" / src
        if p.exists():
            files[dest] = p.read_bytes()
    if licence is not None:
        files["LICENSE"] = licence
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--licence-file", type=Path, help="the licence text to ship as LICENSE (required unless --dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run and not a.licence_file:
        ap.error("a real export needs --licence-file: a public repository without a licence grants nobody any rights")
    if a.licence_file and not a.licence_file.read_text(encoding="utf-8").strip():
        ap.error("the licence file is empty")
    if not a.dry_run and a.out.exists() and any(a.out.iterdir()):
        ap.error(f"{a.out} is not empty; export into a new directory")
    files = build(a.licence_file.read_bytes() if a.licence_file else None)
    problems = scan_tree(files)
    for line in problems:
        print(f"PRIVATE MATERIAL {line}")
    print(f"{len(files)} files, {sum(len(v) for v in files.values()) / 1e6:.1f} MB, {len(problems)} problems")
    if a.dry_run or problems:
        if problems:
            print("nothing written" if not a.dry_run else "")
        return 1 if problems else 0
    for rel, data in files.items():
        dest = a.out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    print(f"wrote {a.out}. Start a NEW repository from it with a single commit; do not reuse this repository's history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
