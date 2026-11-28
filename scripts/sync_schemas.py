import argparse
import ast
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "packages" / "py" / "openbooks" / "src" / "openbooks" / "core" / "schema"
REGISTRY_SOURCE = ROOT / "packages" / "py" / "openbooks" / "src" / "openbooks" / "core" / "refusal_codes.py"
JS_REGISTRY = ROOT / "packages" / "js" / "cli" / "src" / "core" / "generated" / "refusal-codes.ts"
REFUSAL_DOC = ROOT / "docs" / "refusal-codes.md"
WEB_TARGET = ROOT / "web" / "public" / "schema"
TARGETS = (ROOT / "packages" / "js" / "cli" / "schema", WEB_TARGET)
PATTERN = "openbooks.v*.json"
FIX = "run `python scripts/sync_schemas.py` and commit the result"


def canonical_files() -> list[Path]:
    return sorted(CANONICAL.glob(PATTERN))


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def registry_codes() -> dict[str, str]:
    for node in ast.parse(REGISTRY_SOURCE.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "REFUSAL_CODES":
            return ast.literal_eval(node.value)
    raise SystemExit(f"REFUSAL_CODES not found in {relative(REGISTRY_SOURCE)}")


def generated_texts() -> dict[Path, str]:
    codes = registry_codes()
    table = "\n".join(f"| `{code}` | {meaning} |" for code, meaning in codes.items())
    js = (
        f"// GENERATED from {relative(REGISTRY_SOURCE)} by scripts/sync_schemas.py. Do not edit.\n"
        "export const REFUSAL_CODES: Readonly<Record<string, string>> = "
        + json.dumps(codes, indent=2)
        + ";\n"
    )
    doc = (
        "# Refusal codes\n\n"
        f"Generated from `{relative(REGISTRY_SOURCE)}` by `scripts/sync_schemas.py`. Do not edit.\n\n"
        "| Code | Meaning |\n|---|---|\n"
        f"{table}\n"
    )
    return {JS_REGISTRY: js, REFUSAL_DOC: doc}


def generated_divergences() -> list[str]:
    report = []
    for path, text in generated_texts().items():
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            report.append(f"stale {relative(path)}")
    return report


def divergences() -> list[str]:
    report = []
    canonical_names = {src.name for src in canonical_files()}
    for target in TARGETS:
        if target == WEB_TARGET and not target.is_dir():
            continue
        for src in canonical_files():
            dst = target / src.name
            if not dst.is_file():
                report.append(f"missing {relative(dst)}")
            elif dst.read_bytes() != src.read_bytes():
                report.append(f"differs {relative(dst)}")
        if target.is_dir():
            for stray in sorted(target.glob(PATTERN)):
                if stray.name not in canonical_names:
                    report.append(f"stray {relative(stray)}")
    return report


def sync() -> list[str]:
    written = []
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for src in canonical_files():
            dst = target / src.name
            shutil.copyfile(src, dst)
            written.append(relative(dst))
    for path, text in generated_texts().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        written.append(relative(path))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy the canonical openbooks.v* JSON Schemas and generate the refusal-code registry copies.")
    parser.add_argument("--check", action="store_true", help="exit 1 if any copy diverges instead of writing")
    args = parser.parse_args(argv)
    if args.check:
        problems = divergences() + generated_divergences()
        for line in problems:
            print(line, file=sys.stderr)
        if problems:
            print(f"generated copies diverge from {relative(CANONICAL)} or {relative(REGISTRY_SOURCE)}: {FIX}", file=sys.stderr)
            return 1
        print(f"schema copies and refusal-code registry copies match {relative(CANONICAL)}")
        return 0
    for path in sync():
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
