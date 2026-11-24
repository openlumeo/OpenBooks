from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "harness"
ENGINE = REPO / "packages" / "py" / "openbooks"
OUTPUT_DIR = REPO / "web" / "public" / "downloads"
ARCHIVE = OUTPUT_DIR / "openbooks-harness.zip"
CHECKSUM = OUTPUT_DIR / "openbooks-harness.zip.sha256"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
EXCLUDED_FILES = {Path("harness/eval/report.json")}
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", "bench-out"}
FILE_MODE = 0o644 << 16


def kit_files() -> list[Path]:
    files = []
    for path in HARNESS.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(REPO)
        if relative in EXCLUDED_FILES or EXCLUDED_DIRS & set(relative.parts) or path.name == ".env" or path.name.startswith(".env."):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(REPO).as_posix())


def build_engine_wheel(directory: Path) -> Path:
    env = {**os.environ, "SOURCE_DATE_EPOCH": "315532800"}
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(directory), str(ENGINE)],
                   check=True, env=env)
    wheels = list(directory.glob("openbooks-*.whl"))
    if len(wheels) != 1:
        raise OSError("expected one Open Books engine wheel")
    return wheels[0]


def write_archive(files: list[Path], wheel: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        entries = [(path.relative_to(REPO).as_posix(), path) for path in files]
        entries.append((f"harness/wheels/{wheel.name}", wheel))
        for name, path in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = FILE_MODE
            archive.writestr(info, path.read_bytes())


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if not HARNESS.is_dir():
        print(f"harness directory not found: {HARNESS}", file=sys.stderr)
        return 2
    files = kit_files()
    if not files:
        print("no files to package in harness/", file=sys.stderr)
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="openbooks-kit-") as workdir:
            write_archive(files, build_engine_wheel(Path(workdir)))
        digest = sha256_of(ARCHIVE)
        CHECKSUM.write_text(f"{digest}  {ARCHIVE.name}\n", encoding="utf-8")
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"could not write kit: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    size = ARCHIVE.stat().st_size
    print(f"files={len(files) + 1}")
    print(f"sha256={digest}")
    print(f"size={size}")
    print(f"archive={ARCHIVE.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
