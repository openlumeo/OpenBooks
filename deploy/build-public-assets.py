"""Publish the JSON schemas used by the docs deployment."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "packages/py/openbooks/src/openbooks/core/schema"
PUBLIC = ROOT / "web/public"


def main() -> None:
    schemas = PUBLIC / "schema"
    schemas.mkdir(exist_ok=True)

    for schema in ("openbooks.v1.schema.json", "openbooks.v1.refusal.schema.json"):
        shutil.copyfile(SCHEMAS / schema, schemas / schema)
    print("Public assets ready: two JSON schemas")


if __name__ == "__main__":
    main()
