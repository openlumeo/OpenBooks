from __future__ import annotations

from pathlib import Path

from .errors import Refusal

MAX_BYTES = 20 * 1024 * 1024
TEXT_EXT = {".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt"}
DOC_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_EXT = TEXT_EXT | DOC_EXT | {".xlsx"}


def check_input(path: Path) -> None:
    if path.suffix.lower() not in ALLOWED_EXT:
        raise Refusal("UNSUPPORTED_INPUT", f"file type {path.suffix!r} is not supported")
    if path.stat().st_size > MAX_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", "file is over the 20 MB limit")


def read_text_input(path: Path) -> bytes:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise Refusal("UNSUPPORTED_INPUT", "binary content")
    return raw


def guard(path: Path) -> bytes:
    check_input(path)
    return read_text_input(path) if path.suffix.lower() in TEXT_EXT else path.read_bytes()


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        return text.replace("\r\n", "\n").replace("\r", "\n")
    raise Refusal("UNSUPPORTED_INPUT", "text is neither UTF-8 nor cp1252")
