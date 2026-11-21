"""Graceful drain on SIGTERM: fail readiness, refuse new work, let in-flight jobs finish, then hand the signal on."""
from __future__ import annotations

import asyncio
import logging
import signal
import time
from collections.abc import Callable

from . import admission as adm
from .settings import env_number

log = logging.getLogger("openbooks_server")
DEFAULT_GRACE_S = 5.0  # keep answering /readyz=503 this long even when idle, so load balancers notice
DEFAULT_TIMEOUT_S = 120.0  # hard cap on waiting for in-flight jobs
POLL_INTERVAL_S = 0.25
SignalHandler = Callable[[int, object], object] | int | None


def begin_drain(loop: asyncio.AbstractEventLoop, prev_handler: SignalHandler = None,
                signum: int = signal.SIGTERM) -> None:
    """Start draining once; repeat calls are no-ops. The exit is scheduled on the given loop."""
    gate = adm.current
    if not gate.start_drain():
        return
    log.info("draining: readiness now fails, %d jobs in flight", gate.busy())
    loop.call_soon_threadsafe(lambda: asyncio.ensure_future(drain_then_exit(prev_handler, signum)))


async def drain_then_exit(prev_handler: SignalHandler, signum: int) -> None:
    """Wait out the grace period and then for in-flight jobs (up to the timeout), then call the previous handler."""
    gate = adm.current
    grace = env_number("OPENBOOKS_DRAIN_GRACE_S", DEFAULT_GRACE_S)
    limit = env_number("OPENBOOKS_DRAIN_TIMEOUT_S", DEFAULT_TIMEOUT_S)
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit and (time.monotonic() - t0 < grace or gate.busy()):
        await asyncio.sleep(POLL_INTERVAL_S)
    if callable(prev_handler):
        prev_handler(signum, None)
