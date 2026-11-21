"""Drain: idempotent start, readiness failing while draining, in-flight work finishing, and the timeout cap."""
import asyncio
import signal

import pytest
from fastapi.testclient import TestClient

from openbooks_server import admission as adm
from openbooks_server.admission import Admission
from openbooks_server.app import app
from openbooks_server.drain import begin_drain, drain_then_exit


class RecordingLoop:
    """Stands in for the event loop: records what would have been scheduled."""

    def __init__(self) -> None:
        self.scheduled: list = []

    def call_soon_threadsafe(self, callback) -> None:
        self.scheduled.append(callback)


@pytest.fixture
def gate(monkeypatch):
    fresh = Admission()
    monkeypatch.setattr(adm, "current", fresh)
    monkeypatch.setenv("OPENBOOKS_DRAIN_GRACE_S", "0")
    return fresh


def test_begin_drain_schedules_the_exit_only_once(gate):
    loop = RecordingLoop()

    begin_drain(loop)
    begin_drain(loop)

    assert gate.draining is True and len(loop.scheduled) == 1


def test_readyz_is_503_while_draining_even_with_the_model_loaded(gate, monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(app.state, "model_ready", True, raising=False)
    assert client.get("/readyz").status_code == 200

    begin_drain(RecordingLoop())

    ready = client.get("/readyz")
    assert ready.status_code == 503 and ready.json()["draining"] is True
    assert ready.headers["retry-after"] == "5"
    assert client.get("/healthz").status_code == 200  # still alive


def test_drain_waits_for_in_flight_work_before_handing_over_the_signal(gate):
    handed_over: list[int] = []
    running = gate.admit(0, 0)
    gate.try_start(running)

    async def scenario() -> None:
        task = asyncio.ensure_future(drain_then_exit(lambda n, _f: handed_over.append(n), signal.SIGTERM))
        await asyncio.sleep(0.3)
        assert handed_over == []  # the job is still running
        running.release()
        await task

    asyncio.run(scenario())

    assert handed_over == [signal.SIGTERM]


def test_drain_gives_up_after_the_timeout_even_if_work_remains(gate, monkeypatch):
    monkeypatch.setenv("OPENBOOKS_DRAIN_TIMEOUT_S", "0.1")
    handed_over: list[int] = []
    gate.try_start(gate.admit(0, 0))

    asyncio.run(drain_then_exit(lambda n, _f: handed_over.append(n), signal.SIGTERM))

    assert handed_over == [signal.SIGTERM] and gate.busy() == 1


def test_drain_waits_out_the_grace_period_even_when_idle(gate, monkeypatch):
    monkeypatch.setenv("OPENBOOKS_DRAIN_GRACE_S", "0.2")
    handed_over: list[int] = []

    asyncio.run(drain_then_exit(lambda n, _f: handed_over.append(n), signal.SIGTERM))

    assert handed_over == [signal.SIGTERM]


def test_drain_without_a_callable_previous_handler_just_finishes(gate):
    asyncio.run(drain_then_exit(signal.SIG_DFL, signal.SIGTERM))

    assert gate.busy() == 0
