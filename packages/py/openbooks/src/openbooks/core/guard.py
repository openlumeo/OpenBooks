from __future__ import annotations

from pathlib import Path

from .errors import Refusal

MAX_BYTES = 2 * 1024 * 1024 * 1024
MAX_TEXT_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
TEXT_EXT = {".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt", ".xml"}
DOC_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_EXT = TEXT_EXT | DOC_EXT | {".xlsx"}


def check_input(path: Path) -> None:
    if path.suffix.lower() not in ALLOWED_EXT:
        raise Refusal("UNSUPPORTED_INPUT", f"file type {path.suffix!r} is not supported")
    if path.stat().st_size > MAX_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", "file is over the 2 GB limit")
    if path.suffix.lower() in TEXT_EXT and path.stat().st_size > MAX_TEXT_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", "text file is over the 64 MB limit")


def read_text_input(path: Path) -> bytes:
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            if b"\x00" in chunk:
                raise Refusal("UNSUPPORTED_INPUT", "binary content")
        handle.seek(0)
        return handle.read()


def guard(path: Path) -> bytes | Path:
    check_input(path)
    return read_text_input(path) if path.suffix.lower() in TEXT_EXT else path


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        return text.replace("\r\n", "\n").replace("\r", "\n")
    raise Refusal("UNSUPPORTED_INPUT", "text is neither UTF-8 nor cp1252")
