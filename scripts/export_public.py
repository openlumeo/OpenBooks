"""Export the Apache-licensed source tree into an empty directory.

    python scripts/export_public.py OUT_DIR [--licence-file PATH] [--dry-run]

Git supplies the list of tracked source files. The exporter adds the public
README, policies and CI, then scans the result before writing anything.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INCLUDE = [
    "packages/py/openbooks/**",
    "packages/js/**",
    "models/roles_head.pt",
    "models/roles_calibration.json",
    "models/roles_model_card.json",
    "tests/packaging/**",
    "tests/test_cli_machine.py",
    "tests/test_model_card.py",
]
EXCLUDE = [
    "**/node_modules/**",
    "**/dist/**",
    "**/__pycache__/**",
    "**/*.egg-info/**",
    "**/.pytest_cache/**",
    "**/.venv/**",
    "**/*.tsbuildinfo",
    "**/*.pyc",
    "**/build/**",
]
OVERLAY = {
    "README.md": "README.md",
    "CONTRIBUTING.md": "CONTRIBUTING.md",
    "SECURITY.md": "SECURITY.md",
    "THIRD_PARTY.md": "THIRD_PARTY.md",
    "NOTICE": "NOTICE",
    "ci.yml": ".github/workflows/ci.yml",
    "gitignore": ".gitignore",
    "pytest.toml": "pyproject.toml",
}

FORBIDDEN = {
    "private package or module": [r"openbooks_lab", r"lumeo-openbooks-lab", r"lumeo_private"],
    "training recipe or internal weights": [
        r"jepa_encoder",
        r"train_roles",
        r"score_family_candidate",
        r"promote\.py",
        r"roles_manifest",
    ],
    "third-party training data": [r"\bCORD\b", r"\bFUNSD\b", r"\bSROIE\b", r"invoice-ner"],
    "internal documents": [r"HANDOFF", r"format_catalog", r"docs/evidence", r"PRODUCT\.md", r"docs/research"],
    "hosted product": [r"OPENBOOKS_LLM_API_KEY", r"openbooks_server", r"OPENBOOKS_ENGINE_URL"],
    "personal or machine details": [r"Rohit", r"Victus", r"gmail\.com", r"C:\\{1,2}Users", r"/Users/"],
}
SCAN_ALLOW = {
    "tests/packaging/test_wheels.py": {"private package or module", "training recipe or internal weights"},
    "scripts/export_public.py": set(FORBIDDEN),
}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".mjs",
    ".json",
    ".toml",
    ".md",
    ".yml",
    ".yaml",
    ".txt",
    ".cfg",
    ".lock",
    ".gitignore",
    "",
}
BINARY_ALLOWED = {"models/roles_head.pt"}
EMPTY_MARKERS = {"py.typed"}
SHARED_FIXTURES = "packages/py/openbooks/tests/fixtures/shared/"


def matches(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p.replace("/**", "/*")) for p in patterns)


def tracked_files(*pathspecs: str) -> list[str]:
    """List candidate source files without discovering local or ignored files."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--deduplicate", "-z", "--", *pathspecs],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        check=True,
    )
    return sorted(result.stdout.decode("utf-8").rstrip("\0").split("\0")) if result.stdout else []


def read_source(rel: str) -> bytes:
    path = ROOT / rel
    if path.is_symlink() or path.resolve() != path or not path.is_file():
        raise ValueError(f"expected a regular source file: {rel}")
    return path.read_bytes()


def selected() -> list[str]:
    return [rel for rel in tracked_files() if matches(rel, INCLUDE) and not matches(rel, EXCLUDE)]


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
        fixture_text = rel.startswith(SHARED_FIXTURES) and suffix in {".csv", ".sta"}
        if suffix in TEXT_SUFFIXES or Path(rel).name in {".gitignore"} or fixture_text:
            try:
                hits += scan_text(rel, data.decode("utf-8"))
            except UnicodeDecodeError:
                hits.append(f"{rel}: not valid UTF-8 text")
        elif rel not in BINARY_ALLOWED and Path(rel).name not in EMPTY_MARKERS:
            hits.append(f"{rel}: unexpected binary or unknown file type")
    return hits


def build(licence: bytes | None) -> dict[str, bytes]:
    files = {rel: read_source(rel) for rel in selected()}
    for src, dest in OVERLAY.items():
        files[dest] = read_source(f"tools/public/{src}")
    if licence is not None:
        files["LICENSE"] = licence
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument(
        "--licence-file",
        type=Path,
        default=ROOT / "tools" / "public" / "LICENSE",
        help="the licence text to ship as LICENSE (default: the Apache-2.0 text in tools/public/LICENSE)",
    )
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run and not a.licence_file.is_file():
        ap.error(
            f"licence file {a.licence_file} not found: a public repository without a licence grants nobody any rights"
        )
    if a.licence_file.is_file() and not a.licence_file.read_text(encoding="utf-8").strip():
        ap.error("the licence file is empty")
    if not a.dry_run and a.out.exists() and (not a.out.is_dir() or any(a.out.iterdir())):
        ap.error(f"{a.out} is not empty; export into a new directory")
    try:
        files = build(a.licence_file.read_bytes() if a.licence_file.is_file() else None)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        ap.error(f"could not read public export sources: {exc}")
    problems = scan_tree(files)
    for line in problems:
        print(f"PRIVATE MATERIAL {line}")
    print(f"{len(files)} files, {sum(len(v) for v in files.values()) / 1e6:.1f} MB, {len(problems)} problems")
    if problems:
        return 1
    if a.dry_run:
        return 0
    for rel, data in files.items():
        dest = a.out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    print(
        f"wrote {a.out}. Start a NEW repository from it with a single commit; do not reuse this repository's history."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
