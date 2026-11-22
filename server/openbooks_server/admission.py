"""Admission control: bounds jobs in flight, queued jobs, staged bytes and estimated OCR pages.

A request is admitted onto an idle engine regardless of size, so one large upload cannot be refused forever.
Tickets wait for a run slot by polling; a waiter is dropped when its client disconnects or its queue timeout passes.
"""
from __future__ import annotations

import asyncio
import re
import threading
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from .settings import env_number

DEFAULT_MAX_INFLIGHT = 2
DEFAULT_MAX_QUEUE = 8
DEFAULT_MAX_BYTES = 256 << 20
DEFAULT_MAX_OCR_PAGES = 60
DEFAULT_RETRY_AFTER_S = 5
DEFAULT_QUEUE_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.02
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
_PDF_PAGE_OBJECT = re.compile(rb"/Type\s*/Page\b")
_PDF_FONT_MARKER = b"/Font"


class Rejected(Exception):
    """Raised by Admission.admit when a limit is hit; reason is the public rejection code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Ticket:
    """One admitted job. The Admission object owns its state; the ticket only asks it to start or release."""

    def __init__(self, adm: Admission, nbytes: int, pages: int) -> None:
        self.adm = adm
        self.nbytes = nbytes
        self.pages = pages
        self.state = "queued"
        self.waited = 0.0

    async def wait_turn(self, is_disconnected: Callable[[], Awaitable[bool]]) -> str:
        """Wait for a run slot. Returns ok | disconnected | timeout; the caller releases the ticket unless ok."""
        t0 = time.perf_counter()
        outcome = await self._poll_for_slot(t0, is_disconnected)
        self.waited = time.perf_counter() - t0
        return outcome

    async def _poll_for_slot(self, t0: float, is_disconnected: Callable[[], Awaitable[bool]]) -> str:
        while True:
            if self.adm.try_start(self):
                return "ok"
            if await is_disconnected():
                return "disconnected"
            if time.perf_counter() - t0 > self.adm.queue_timeout:
                return "timeout"
            await asyncio.sleep(POLL_INTERVAL_S)

    def release(self) -> None:
        """Give back this ticket's share of the engine. Safe to call more than once."""
        self.adm.release(self)


class Admission:
    """The single process-wide gate. All counters are changed only under its lock, through its methods."""

    def __init__(self, max_inflight: int = DEFAULT_MAX_INFLIGHT, max_queue: int = DEFAULT_MAX_QUEUE,
                 max_bytes: int = DEFAULT_MAX_BYTES, max_pages: int = DEFAULT_MAX_OCR_PAGES,
                 retry_after: int = DEFAULT_RETRY_AFTER_S, queue_timeout: float = DEFAULT_QUEUE_TIMEOUT_S) -> None:
        self.max_inflight = max_inflight
        self.max_queue = max_queue
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.retry_after = retry_after
        self.queue_timeout = queue_timeout
        self.running = 0
        self.queued = 0
        self.bytes = 0
        self.pages = 0
        self.draining = False
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> Admission:
        """Build the gate from the OPENBOOKS_* limits, using the defaults for anything unset."""
        return cls(
            max_inflight=int(env_number("OPENBOOKS_MAX_INFLIGHT", DEFAULT_MAX_INFLIGHT)),
            max_queue=int(env_number("OPENBOOKS_MAX_QUEUE", DEFAULT_MAX_QUEUE)),
            max_bytes=int(env_number("OPENBOOKS_MAX_INFLIGHT_BYTES", DEFAULT_MAX_BYTES)),
            max_pages=int(env_number("OPENBOOKS_MAX_OCR_PAGES", DEFAULT_MAX_OCR_PAGES)),
            retry_after=int(env_number("OPENBOOKS_RETRY_AFTER_S", DEFAULT_RETRY_AFTER_S)),
            queue_timeout=env_number("OPENBOOKS_QUEUE_TIMEOUT_S", DEFAULT_QUEUE_TIMEOUT_S),
        )

    def start_drain(self) -> bool:
        """Refuse all new work from now on. Returns True only for the call that started the drain."""
        with self._lock:
            if self.draining:
                return False
            self.draining = True
            return True

    def _reason(self, nbytes: int, pages: int) -> str | None:
        """Caller holds the lock. Returns the first limit the extra work would break, or None."""
        if self.draining:
            return "draining"
        if self.running + self.queued >= self.max_inflight + self.max_queue:
            return "queue_full"
        if self.bytes and self.bytes + nbytes > self.max_bytes:
            return "bytes"
        if self.pages and self.pages + pages > self.max_pages:
            return "ocr_pages"
        return None

    def precheck(self, nbytes: int = 0) -> str | None:
        """Cheap refusal before the upload body is read. Returns a rejection reason or None."""
        with self._lock:
            return self._reason(nbytes, 0)

    def admit(self, nbytes: int, pages: int) -> Ticket:
        """Reserve queue space and bytes for one job, or raise Rejected with the reason."""
        with self._lock:
            reason = self._reason(nbytes, pages)
            if reason:
                raise Rejected(reason)
            self.queued += 1
            self.bytes += nbytes
            self.pages += pages
            return Ticket(self, nbytes, pages)

    def try_start(self, ticket: Ticket) -> bool:
        """Move a queued ticket to running if a slot is free. Returns whether it started."""
        with self._lock:
            if self.running >= self.max_inflight:
                return False
            self.queued -= 1
            self.running += 1
            ticket.state = "running"
            return True

    def release(self, ticket: Ticket) -> None:
        """Return a ticket's slot, bytes and pages. Releasing an already released ticket does nothing."""
        with self._lock:
            if ticket.state == "done":
                return
            if ticket.state == "running":
                self.running -= 1
            else:
                self.queued -= 1
            self.bytes -= ticket.nbytes
            self.pages -= ticket.pages
            ticket.state = "done"

    def busy(self) -> int:
        """Jobs running or waiting for a slot."""
        with self._lock:
            return self.running + self.queued


current = Admission.from_env()


def estimate_ocr_pages(path: Path) -> int:
    """Pages of OCR work for one file: images count as one page; a PDF with no font objects counts its page objects."""
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return 1
    if suffix != ".pdf":
        return 0
    data = path.read_bytes()
    if _PDF_FONT_MARKER in data:
        return 0
    return max(1, len(_PDF_PAGE_OBJECT.findall(data)))
