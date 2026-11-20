"""One run: many uploaded files, each through openbooks.pipeline.process, reported as events.

Events (name, payload), in order per file:
  file.started {index, name, size}
  file.stage   {index, stage}            once per stage the engine completes
  file.done    {index, doc}              doc is exactly what process() returned
and finally
  run.done     {released, refused}

Uploaded files only exist inside a per-run temp dir, removed when the run ends. Size limits are the
engine's: an oversized file reaches process() and comes back as its own UNSUPPORTED_INPUT refusal.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO

from openbooks.pipeline import MAX_BYTES, Params, process

MAX_FILES = 20
_CURRENCY = re.compile(r"^[A-Za-z]{3}$")
_AMOUNT = re.compile(r"^-?\d+(\.\d+)?$")
_UNSAFE = re.compile(r"[^\w.\- ()\[\]]+")

Emit = Callable[[str, dict], None]


def parse_params(raw: dict | None, base: Params | None = None) -> Params:
    """Validate caller params on top of base. Raises ValueError with a message fit for the user."""
    if raw is not None and not isinstance(raw, dict):
        raise ValueError("params must be an object")
    raw = raw or {}
    b = base or Params()
    cur = raw.get("currency", b.currency)
    if cur in ("", None):
        cur = None
    elif not isinstance(cur, str) or not _CURRENCY.fullmatch(cur):
        raise ValueError(f"currency must be a 3-letter code, got {cur!r}")
    opening = b.opening
    if "opening" in raw:
        o = raw["opening"]
        if o in ("", None):
            opening = None
        else:
            o = str(o).strip().replace(",", "")
            if not _AMOUNT.fullmatch(o):
                raise ValueError(f"opening balance must be a plain number like 1000.00, got {raw['opening']!r}")
            try:
                opening = Decimal(o)
            except InvalidOperation:
                raise ValueError(f"opening balance is not a number: {raw['opening']!r}") from None
    account = raw.get("account", b.account) or None
    if account is not None and not isinstance(account, str):
        raise ValueError("account must be text")
    order = raw.get("date_order", b.date_order) or None
    if order not in (None, "dmy", "mdy"):
        raise ValueError(f"date_order must be dmy or mdy, got {order!r}")

    def flag(name: str, default: bool) -> bool:
        v = raw.get(name, default)
        if not isinstance(v, bool):
            raise ValueError(f"{name} must be true or false")
        return v

    return Params(
        currency=cur.upper() if cur else None,
        opening=opening,
        account=account,
        allow_derived_opening=flag("allow_derived_opening", b.allow_derived_opening),
        ocr=flag("ocr", b.ocr),
        model=flag("model", b.model),
        date_order=order,
    )


def safe_name(name: str, index: int) -> str:
    base = Path((name or "").replace("\\", "/")).name.strip()
    base = _UNSAFE.sub("_", base)[:180]
    return base if base not in ("", ".", "..") else f"file-{index}"


@dataclass
class Staged:
    name: str
    path: Path
    size: int


class Run:
    """Owns the temp dir for one request. stage() copies uploads in; execute() processes and cleans up."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="openbooks-run-"))
        self.files: list[Staged] = []
        self.cancelled = threading.Event()

    def stage(self, name: str, stream: BinaryIO) -> None:
        i = len(self.files)
        d = self.root / str(i)
        d.mkdir()
        path = d / safe_name(name, i)
        # Never write more than the engine limit + 1 byte to disk: the extra byte still makes process()
        # refuse the file as oversize, but a hostile upload cannot fill the disk.
        with open(path, "wb") as out:
            out.write(stream.read(MAX_BYTES + 1))
        self.files.append(Staged(name or path.name, path, path.stat().st_size))

    def execute(self, params: Params, per_file: dict[int, Params], emit: Emit) -> None:
        released = refused = 0
        try:
            for i, f in enumerate(self.files):
                if self.cancelled.is_set():
                    return
                emit("file.started", {"index": i, "name": f.name, "size": f.size})
                doc = process(f.path, per_file.get(i, params),
                              on_stage=lambda s, i=i: emit("file.stage", {"index": i, "stage": s}))
                if doc["status"] == "ok":
                    released += 1
                else:
                    refused += 1
                emit("file.done", {"index": i, "doc": doc})
                f.path.unlink(missing_ok=True)
            emit("run.done", {"released": released, "refused": refused})
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
