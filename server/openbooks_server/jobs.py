"""Short-lived, capability-keyed results for requests that outlast an HTTP gateway."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

JOB_HEADER = "x-openbooks-job"
JOB_KEY = re.compile(r"[a-f0-9]{32}")
RESULT_TTL = 120
MAX_JOBS = 24
MAX_RESULT_BYTES = 32 << 20
POLL_BYTES = 4 << 20
HEADERS = {"Cache-Control": "no-store"}
log = logging.getLogger("openbooks_server")


def job_key(request: Request, *, required: bool = False) -> str | None:
    key = request.headers.get(JOB_HEADER)
    if (key is not None or required) and not JOB_KEY.fullmatch(key or ""):
        raise HTTPException(400, f"{JOB_HEADER} must be a 32-character lowercase hex key")
    return key


@dataclass
class Job:
    remaining: Callable[[], int]
    frames: list[bytes] = field(default_factory=list)
    size: int = 0
    done: bool = False
    delivered: bool = False

    def push(self, event: str, data: Any) -> None:
        frame = json.dumps({"event": event, "data": data}, ensure_ascii=False, separators=(",", ":")).encode()
        if len(frame) > POLL_BYTES - 1024 or len(frame) > self.remaining():
            raise ResultLimit
        self.frames.append(frame)
        self.size += len(frame)

    def poll(self, cursor: int) -> tuple[Response, bool]:
        if not 0 <= cursor <= len(self.frames):
            return JSONResponse({"message": "Invalid job cursor."}, status_code=400, headers=HEADERS), False
        end, size = cursor, 0
        while end < len(self.frames):
            n = len(self.frames[end])
            if size + n > POLL_BYTES:
                break
            end += 1
            size += n
        done = self.done and end == len(self.frames)
        body = b'{"events":[' + b",".join(self.frames[cursor:end]) + b'],"cursor":' + str(end).encode()
        body += b',"done":' + (b"true" if done else b"false") + b"}"
        return Response(body, media_type="application/json", headers=HEADERS), done


class ResultLimit(Exception):
    pass


class Jobs:
    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], Job] = {}
        self.tasks: set[asyncio.Task] = set()

    def get(self, kind: str, key: str) -> Job | None:
        return self.entries.get((kind, key))

    def start(self, kind: str, key: str, work: Callable[[Job], Awaitable[None]], request_id: str) -> Response:
        index = (kind, key)
        if index in self.entries:
            return JSONResponse({"message": "This job key has already been used."}, status_code=409, headers=HEADERS)
        if len(self.entries) >= MAX_JOBS:
            return JSONResponse({"message": "The engine is busy. Try again shortly."}, status_code=429,
                                headers={**HEADERS, "Retry-After": "5"})
        job = self.entries[index] = Job(self.remaining)

        def error(message: str) -> None:
            job.frames.append(json.dumps({"event": "error", "data": {"message": message}}).encode())

        async def run() -> None:
            try:
                await work(job)
            except ResultLimit:
                error("Too much result data to return. Split the input into smaller files and try again.")
            except Exception:
                log.exception("background job failed request_id=%s", request_id)
                error("The engine could not complete the job. Try again.")
            finally:
                job.done = True
                asyncio.get_running_loop().call_later(RESULT_TTL, self.expire, index, job)

        task = asyncio.create_task(run())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return JSONResponse({"accepted": True}, status_code=202, headers=HEADERS)

    def remaining(self) -> int:
        return MAX_RESULT_BYTES - sum(job.size for job in self.entries.values())

    def expire(self, index: tuple[str, str], job: Job) -> None:
        if self.entries.get(index) is job:
            del self.entries[index]
            job.frames.clear()

    def poll(self, kind: str, key: str, cursor: int) -> Response:
        job = self.get(kind, key)
        if job is None:
            return JSONResponse({"message": "This job has expired or the engine restarted. Submit the file again."},
                                status_code=404, headers=HEADERS)
        response, done = job.poll(cursor)
        if done and not job.delivered:
            job.delivered = True
            asyncio.get_running_loop().call_later(15, self.expire, (kind, key), job)
        return response
