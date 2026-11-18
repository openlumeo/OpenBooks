from __future__ import annotations

import hashlib
from pathlib import Path


def evidence(ev: dict, rid: str, field: str, row: int | None, raw: str, *, page: int | None = None,
             bbox: list[float] | None = None, method: str = "parser", conf: float | None = None) -> None:
    ev[f"{rid}.{field}"] = {"page": page, "bbox": bbox, "row": row, "raw_text": raw, "method": method}
    if conf is not None:
        ev[f"{rid}.{field}"]["confidence"] = round(conf, 4)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
