"""Build the explicitly public wheel and JSON schemas used by the docs deployment."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/py/openbooks-mcp"
SCHEMAS = ROOT / "packages/py/openbooks/src/openbooks/core/schema"
PUBLIC = ROOT / "web/public"


def main() -> None:
    version = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    downloads = PUBLIC / "downloads"
    schemas = PUBLIC / "schema"
    downloads.mkdir(exist_ok=True)
    schemas.mkdir(exist_ok=True)

    subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(downloads), str(PACKAGE)], check=True)
    name = f"openbooks_mcp-{version}-py3-none-any.whl"
    wheel = downloads / name
    with wheel.open("rb") as artifact:
        checksum = hashlib.file_digest(artifact, "sha256").hexdigest()
    (downloads / f"{name}.sha256").write_text(f"{checksum}  {name}\n", encoding="ascii")

    for schema in ("openbooks.v1.schema.json", "openbooks.v1.refusal.schema.json"):
        shutil.copyfile(SCHEMAS / schema, schemas / schema)
    print(f"Public assets ready: {name}, its checksum, and two JSON schemas")


if __name__ == "__main__":
    main()
