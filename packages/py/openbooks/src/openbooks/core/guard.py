from __future__ import annotations

from pathlib import Path

from .errors import Refusal

MAX_BYTES = 2 * 1024 * 1024 * 1024
MAX_LOCAL_BYTES = 2 * MAX_BYTES
MAX_TEXT_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
TEXT_EXT = {".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt", ".xml"}
DOC_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_EXT = TEXT_EXT | DOC_EXT | {".xlsx"}


def check_input(path: Path, *, max_bytes: int = MAX_BYTES) -> None:
    if path.suffix.lower() not in ALLOWED_EXT:
        raise Refusal("UNSUPPORTED_INPUT", f"file type {path.suffix!r} is not supported")
    size = path.stat().st_size
    if size > max_bytes:
        raise Refusal("UNSUPPORTED_INPUT", f"file is over the {max_bytes >> 30} GB limit")
    if path.suffix.lower() in TEXT_EXT and size > MAX_TEXT_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", "text file is over the 64 MB limit")


def read_text_input(path: Path) -> bytes:
    with path.open("rb") as handle:
        raw = handle.read(MAX_TEXT_BYTES + 1)
    if len(raw) > MAX_TEXT_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", "text file is over the 64 MB limit")
    if b"\x00" in raw:
        raise Refusal("UNSUPPORTED_INPUT", "binary content")
    return raw


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
