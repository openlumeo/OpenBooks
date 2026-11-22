"""Request-id validation and echo, route labels, early refusal of guarded routes and the per-request counter and log."""
import logging

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from openbooks_server import admission as adm
from openbooks_server.admission import Admission
from openbooks_server.app import app
from openbooks_server.metrics import registry
from openbooks_server.middleware import (
    OpsMiddleware,
    declared_length,
    early_refusal,
    route_label,
    valid_request_id,
)


@pytest.fixture(autouse=True)
def forget_middleware_stack_after_each_test():
    yield
    app.middleware_stack = None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(adm, "current", Admission())
    monkeypatch.delenv("OPENBOOKS_ENGINE_KEY", raising=False)
    app.middleware_stack = None
    return TestClient(app)


@pytest.mark.parametrize("raw", ["abc-123", "x", "a.b_c-9", "a" * 128])
def test_well_formed_request_id_is_echoed(raw):
    assert valid_request_id(raw) == raw


@pytest.mark.parametrize("raw", ["", "a" * 129, "bad id!", "../escape", "ridé", "日本", "x\r\nSet-Cookie: a=b",
                                 "x\nInjected: 1", "x\ty", "x;y", "<script>"])
def test_malformed_request_id_is_replaced_by_a_fresh_32_char_hex_id(raw):
    generated = valid_request_id(raw)

    assert generated != raw and len(generated) == 32 and int(generated, 16) >= 0


def test_crlf_in_a_request_id_can_never_reach_the_response_header(client):
    r = client.get("/healthz", headers={"X-Request-ID": "ok-1"})

    assert r.headers["x-request-id"] == "ok-1" and "\n" not in r.headers["x-request-id"]


def test_missing_request_id_is_generated_on_every_response(client):
    first = client.get("/healthz").headers["x-request-id"]
    second = client.get("/healthz").headers["x-request-id"]

    assert len(first) == 32 and first != second


@pytest.mark.parametrize("path, label", [
    ("/v1/samples/abc", "/v1/samples/{id}"),
    ("/v1/samples", "/v1/samples"),
    ("/v1/runs", "/v1/runs"),
    ("/metrics", "/metrics"),
    ("/no/such/path?x=1", "other"),
    ("/v1/runs/extra", "other"),
])
def test_route_label_is_bounded_to_known_routes(path, label):
    assert route_label(path.split("?")[0]) == label


@pytest.mark.parametrize("headers, expected", [
    ({}, 0),
    ({b"content-length": b""}, 0),
    ({b"content-length": b"abc"}, 0),
    ({b"content-length": b"12"}, 12),
])
def test_declared_length_treats_missing_or_malformed_values_as_zero(headers, expected):
    assert declared_length(headers) == expected


def test_early_refusal_ignores_unguarded_routes(monkeypatch):
    monkeypatch.setattr(adm, "current", Admission(max_inflight=0, max_queue=0))

    assert early_refusal("GET", "/v1/health", {}) is None


def test_early_refusal_returns_the_429_for_a_full_guarded_route(monkeypatch):
    monkeypatch.setattr(adm, "current", Admission(max_inflight=0, max_queue=0))

    refusal = early_refusal("POST", "/v1/roles", {})

    assert isinstance(refusal, JSONResponse) and refusal.status_code == 429


def test_early_refusal_is_none_for_a_guarded_route_with_room(monkeypatch):
    monkeypatch.setattr(adm, "current", Admission())

    assert early_refusal("POST", "/v1/runs", {b"content-length": b"10"}) is None


def test_draining_refuses_guarded_routes_before_body_validation(client):
    adm.current.start_drain()

    r = client.post("/v1/runs")

    assert r.status_code == 503 and r.json()["error"] == "draining"


def test_each_response_is_counted_by_route_and_status(client):
    client.get("/healthz")

    assert 'openbooks_requests_total{route="/healthz",status="200"}' in registry.render({})


def test_access_log_records_request_id_route_and_status(client, caplog):
    with caplog.at_level(logging.INFO, logger="openbooks_server"):
        client.get("/healthz", headers={"X-Request-ID": "trace-42"})

    assert "request_id=trace-42 GET /healthz status=200" in caplog.text


def test_a_crashing_app_is_counted_as_status_500():
    async def boom(scope, receive, send):
        raise RuntimeError("boom")

    crashing = TestClient(OpsMiddleware(boom))
    with pytest.raises(RuntimeError):
        crashing.get("/v1/health")

    assert 'openbooks_requests_total{route="/v1/health",status="500"}' in registry.render({})
