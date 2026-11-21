"""Refusal bodies and Retry-After headers, plus the HTTP path that produces them."""
import json

import pytest
from fastapi.testclient import TestClient

from openbooks_server import admission as adm
from openbooks_server.admission import Admission
from openbooks_server.app import app
from openbooks_server.metrics import registry
from openbooks_server.responses import reject_response, unauthorised_response

CSV = ("bank.csv", b"Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n")


@pytest.fixture
def gate(monkeypatch):
    fresh = Admission(max_inflight=1, max_queue=0, retry_after=7)
    monkeypatch.setattr(adm, "current", fresh)
    return fresh


@pytest.mark.parametrize("retry_after", [0, 1, 7, 300])
def test_retry_after_header_mirrors_the_configured_value(gate, retry_after):
    gate.retry_after = retry_after

    response = reject_response("queue_full")

    assert response.headers["retry-after"] == str(retry_after)
    assert json.loads(response.body)["retry_after"] == retry_after


def test_capacity_refusal_is_429_overloaded(gate):
    response = reject_response("queue_full")

    assert response.status_code == 429
    assert json.loads(response.body)["error"] == "overloaded"


def test_draining_refusal_is_503_draining(gate):
    response = reject_response("draining")

    assert response.status_code == 503
    assert json.loads(response.body)["error"] == "draining"


def test_refusal_is_counted_by_reason(gate):
    reject_response("bytes")

    assert 'openbooks_rejections_total{reason="bytes"}' in registry.render({})


def test_unauthorised_response_is_401_without_retry_after():
    response = unauthorised_response()

    assert response.status_code == 401
    assert "retry-after" not in response.headers
    assert json.loads(response.body)["error"] == "unauthorized"


def test_excess_work_gets_429_with_retry_after(gate):
    held = gate.admit(10, 0)  # engine is full
    client = TestClient(app)
    try:
        r = client.post("/v1/runs", files=[("files", CSV)])
    finally:
        held.release()

    assert r.status_code == 429
    assert r.headers["retry-after"] == "7"
    assert r.json()["reason"] == "queue_full" and r.json()["retry_after"] == 7


def test_queue_timeout_over_http_is_429_queue_timeout(monkeypatch):
    gate = Admission(max_inflight=1, max_queue=2, queue_timeout=0.05, retry_after=3)
    monkeypatch.setattr(adm, "current", gate)
    gate.try_start(gate.admit(0, 0))  # a job holds the only slot
    client = TestClient(app)

    r = client.post("/v1/runs", files=[("files", CSV)])

    assert r.status_code == 429
    assert r.headers["retry-after"] == "3"
    assert r.json()["reason"] == "queue_timeout"
    assert gate.queued == 0  # the timed-out ticket gave back its place
