"""Stream multipart uploads directly into the run's only copy of each input."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from anyio import to_thread
from fastapi import HTTPException, Request
from openbooks.core.guard import MAX_BYTES, MAX_TEXT_BYTES, TEXT_EXT
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.requests import ClientDisconnect

from .runs import MAX_FILES, Run, Staged

FORM_BYTES = 1 << 20
HEADER_BYTES = 8 << 10
SPACE_CHECK_BYTES = 16 << 20
FREE_SPACE_RESERVE = 256 << 20


class Upload:
    def __init__(self, run: Run, file_field: bytes, fields: set[bytes], max_files: int) -> None:
        self.run = run
        self.file_field = file_field
        self.fields = fields
        self.max_files = max_files
        self.values: dict[bytes, str] = {}
        self.output: BinaryIO | None = None
        self.path: Path | None = None
        self.ended = False
        self.total = 0
        self.next_space_check = 0

    def begin(self) -> None:
        self.header = bytearray()
        self.header_name = bytearray()
        self.headers_size = 0
        self.disposition = b""
        self.value = bytearray()
        self.size = 0

    def header_fragment(self, target: bytearray, data: bytes, start: int, end: int) -> None:
        self.headers_size += end - start
        if self.headers_size > HEADER_BYTES:
            raise HTTPException(400, "multipart headers are too large")
        target.extend(data[start:end])

    def header_end(self) -> None:
        if self.header_name.lower() == b"content-disposition":
            self.disposition = bytes(self.header)
        self.header.clear()
        self.header_name.clear()

    def headers_finished(self) -> None:
        disposition, options = parse_options_header(self.disposition)
        self.field = options.get(b"name", b"")
        if disposition != b"form-data":
            raise HTTPException(400, "invalid multipart disposition")
        if b"filename" not in options:
            if self.field not in self.fields or self.field in self.values:
                raise HTTPException(422, "unexpected or repeated multipart field")
            return
        if self.field != self.file_field or len(self.run.files) >= self.max_files:
            raise HTTPException(422, f"attach at most {self.max_files} files in the {self.file_field.decode()} field")
        self.name = options[b"filename"].decode("utf-8", errors="replace")
        self.path = self.run.upload_path(self.name)
        self.limit = MAX_TEXT_BYTES if self.path.suffix.lower() in TEXT_EXT else MAX_BYTES
        self.output = self.path.open("wb")

    def data(self, data: bytes, start: int, end: int) -> None:
        count = end - start
        self.size += count
        if self.output is None:
            if self.size > FORM_BYTES // 4:
                raise HTTPException(413, "multipart field is too large")
            self.value.extend(data[start:end])
            return
        self.total += count
        if self.size > self.limit or self.total > MAX_BYTES:
            raise HTTPException(413, f"upload exceeds the file limit of {self.limit} bytes or the run limit of {MAX_BYTES} bytes")
        if self.total > self.next_space_check:
            if shutil.disk_usage(self.run.root).free < FREE_SPACE_RESERVE + max(count, SPACE_CHECK_BYTES):
                raise HTTPException(507, "insufficient temporary storage for the upload")
            self.next_space_check = self.total + SPACE_CHECK_BYTES
        self.output.write(memoryview(data)[start:end])

    def part_end(self) -> None:
        if self.output is None:
            self.values[self.field] = self.value.decode("utf-8", errors="replace")
            return
        self.output.close()
        self.output = None
        assert self.path is not None
        self.run.files.append(Staged(self.name or self.path.name, self.path, self.size))

    def end(self) -> None:
        self.ended = True


async def stage_multipart(request: Request, run: Run, *, roles: bool = False) -> dict[bytes, str]:
    content_type = request.headers.get("content-type", "")
    if not content_type:
        return {}
    media, params = parse_options_header(content_type)
    boundary = params.get(b"boundary", b"")
    if media != b"multipart/form-data" or not 0 < len(boundary) <= 70:
        raise HTTPException(400, "expected multipart/form-data with a valid boundary")
    upload = Upload(run, b"file" if roles else b"files", {b"params"} if roles else {b"params", b"file_params"},
                    1 if roles else MAX_FILES)
    parser = MultipartParser(boundary, {
        "on_part_begin": upload.begin, "on_part_data": upload.data, "on_part_end": upload.part_end,
        "on_header_field": lambda *args: upload.header_fragment(upload.header_name, *args),
        "on_header_value": lambda *args: upload.header_fragment(upload.header, *args),
        "on_header_end": upload.header_end, "on_headers_finished": upload.headers_finished, "on_end": upload.end,
    })
    received = 0
    try:
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_BYTES + FORM_BYTES:
                raise HTTPException(413, "multipart request exceeds the upload limit")
            await to_thread.run_sync(parser.write, chunk)
        parser.finalize()
        if not upload.ended:
            raise HTTPException(400, "incomplete multipart upload")
        return upload.values
    except MultipartParseError:
        raise HTTPException(400, "invalid multipart upload") from None
    except ClientDisconnect:
        raise HTTPException(499, "client disconnected during upload") from None
    finally:
        if upload.output is not None:
            upload.output.close()
