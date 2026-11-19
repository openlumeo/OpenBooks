from __future__ import annotations

from pathlib import Path

from .errors import Refusal

MAX_BYTES = 20 * 1024 * 1024
TEXT_EXT = {".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt"}
DOC_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_EXT = TEXT_EXT | DOC_EXT | {".xlsx"}


def guard(path: Path) -> bytes:
    if path.suffix.lower() not in ALLOWED_EXT:
        raise Refusal("UNSUPPORTED_INPUT", f"file type {path.suffix!r} is not supported")
    if path.stat().st_size > MAX_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", "file is over the 20 MB limit")
    raw = path.read_bytes()
    if path.suffix.lower() in TEXT_EXT and b"\x00" in raw:
        raise Refusal("UNSUPPORTED_INPUT", "binary content")
    return raw


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        # One line ending for every parser: CRLF (Windows) and a bare CR (old Mac exports) both become LF. The csv module refuses
        # a bare CR inside a row, which would turn a harmless export quirk into a refusal.
        return text.replace("\r\n", "\n").replace("\r", "\n")
    raise Refusal("UNSUPPORTED_INPUT", "text is neither UTF-8 nor cp1252")
