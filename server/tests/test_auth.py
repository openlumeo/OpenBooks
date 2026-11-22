"""Engine-key auth: the shared secret guards everything except the liveness and readiness probes."""
import logging

import pytest
from fastapi.testclient import TestClient

from openbooks_server.app import app
from openbooks_server.auth import KEY_EXEMPT, engine_key_from_env, is_authorised

KEY = "s3cret"


@pytest.fixture(autouse=True)
def forget_middleware_stack_after_each_test():
    yield
    app.middleware_stack = None


def guarded_client(monkeypatch, key: str | None) -> TestClient:
    if key is None:
        monkeypatch.delenv("OPENBOOKS_ENGINE_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENBOOKS_ENGINE_KEY", key)
    app.middleware_stack = None
    return TestClient(app)


def test_missing_key_header_is_refused_with_401(monkeypatch):
    client = guarded_client(monkeypatch, KEY)

    assert client.get("/metrics").status_code == 401


@pytest.mark.parametrize("value", ["wrong", "", "s3cret-extra", "s3"])
def test_wrong_empty_or_different_length_keys_are_refused(monkeypatch, value):
    client = guarded_client(monkeypatch, KEY)

    r = client.get("/metrics", headers={"x-openbooks-key": value})

    assert r.status_code == 401 and r.json()["error"] == "unauthorized"


def test_correct_key_is_accepted(monkeypatch):
    client = guarded_client(monkeypatch, KEY)

    assert client.get("/metrics", headers={"x-openbooks-key": KEY}).status_code == 200


def test_header_name_is_matched_case_insensitively(monkeypatch):
    client = guarded_client(monkeypatch, KEY)

    assert client.get("/metrics", headers={"X-OpenBooks-Key": KEY}).status_code == 200


def test_probes_are_exempt_and_need_no_key(monkeypatch):
    client = guarded_client(monkeypatch, KEY)

    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code in (200, 503)


def test_probe_exemption_is_exact_and_does_not_cover_lookalike_paths(monkeypatch):
    client = guarded_client(monkeypatch, KEY)

    assert client.get("/healthz/").status_code == 401


def test_guarded_post_is_refused_before_the_body_is_read(monkeypatch):
    client = guarded_client(monkeypatch, KEY)

    assert client.post("/v1/runs").status_code == 401


def test_key_unset_accepts_any_caller(monkeypatch):
    client = guarded_client(monkeypatch, None)

    assert client.get("/metrics").status_code == 200


def test_empty_env_value_counts_as_unset_and_warns(monkeypatch, caplog):
    monkeypatch.setenv("OPENBOOKS_ENGINE_KEY", "")

    with caplog.at_level(logging.WARNING, logger="openbooks_server"):
        key = engine_key_from_env()

    assert key == b"" and "OPENBOOKS_ENGINE_KEY is not set" in caplog.text


def test_set_key_logs_no_warning(monkeypatch, caplog):
    monkeypatch.setenv("OPENBOOKS_ENGINE_KEY", KEY)

    with caplog.at_level(logging.WARNING, logger="openbooks_server"):
        assert engine_key_from_env() == KEY.encode()

    assert caplog.text == ""


def test_is_authorised_passes_probes_and_unset_keys_without_headers():
    assert is_authorised(b"", "/metrics", {})
    assert all(is_authorised(b"k", path, {}) for path in KEY_EXEMPT)


def test_is_authorised_compares_the_header_value_exactly():
    assert is_authorised(b"k", "/metrics", {b"x-openbooks-key": b"k"})
    assert not is_authorised(b"k", "/metrics", {b"x-openbooks-key": b"K"})
