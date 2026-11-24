"""Hostile-input tests for the engine service: injection, traversal, malformed params, upload limits, CORS."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from openbooks.pipeline import MAX_BYTES

from openbooks_server.app import app
from openbooks_server.execution import _sse
from openbooks_server.runs import Run, parse_params, safe_name

XSS = '<script>alert(1)</script>"\'><img src=x onerror=alert(1)>'
SQLI = ["' OR 1=1 --", "1; DROP TABLE users;--", "' UNION SELECT NULL--", "admin'/*"]
CSV = "Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n01/01/24,=HYPERLINK(\"http://x\"),0,100,100\n"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("name", ["../../etc/passwd", "..\\..\\win.ini", "/abs/path.csv", "a/b/../../c.csv",
                                  "", ".", "..", "x\x00.csv", "con<>|?*.csv", "a" * 500 + ".csv"])
def test_safe_name_never_escapes_or_overflows(name):
    out = safe_name(name, 0)
    assert "/" not in out and "\\" not in out and "\x00" not in out
    assert out not in ("", ".", "..") and len(out) <= 180


def test_stage_stays_inside_run_dir_for_traversal_names():
    run = Run()
    try:
        run.stage("../../../evil.csv", io.BytesIO(b"x"))
        assert run.root in run.files[0].path.resolve().parents
    finally:
        run.cleanup()


def test_stage_never_writes_more_than_engine_limit(monkeypatch):
    limit = 1024 * 1024
    monkeypatch.setattr("openbooks_server.runs.MAX_BYTES", limit)
    run = Run()
    try:
        run.stage("big.pdf", io.BytesIO(b"0" * (limit + 5_000)))
        assert run.files[0].size == limit + 1
    finally:
        run.cleanup()


@pytest.mark.parametrize("raw", [
    {"currency": SQLI[0]}, {"currency": XSS}, {"currency": "USDX"}, {"currency": 5}, {"currency": ["USD"]},
    {"opening": "1e999"}, {"opening": "NaN"}, {"opening": "1; DROP"}, {"opening": {"a": 1}},
    {"date_order": "ymd"}, {"date_order": SQLI[1]}, {"ocr": "true"}, {"model": 1}, {"account": 7}, [], "str", 5,
])
def test_parse_params_rejects_hostile_values(raw):
    with pytest.raises(ValueError):
        parse_params(raw)


def test_parse_params_keeps_account_as_inert_text():
    assert parse_params({"account": XSS}).account == XSS


@pytest.mark.parametrize("payload", SQLI + [XSS, "../../etc/passwd", "%2e%2e%2fsecret", "a" * 5000])
def test_sample_lookup_rejects_injection_and_traversal(client, payload):
    r = client.get("/v1/samples/" + payload.replace("/", "%2F"))
    assert r.status_code in (404, 405, 422)


@pytest.mark.parametrize("params", ["{not json", "[1]", '"s"', json.dumps({"currency": SQLI[0]})])
def test_runs_bad_params_are_422(client, params):
    r = client.post("/v1/runs", files={"files": ("a.csv", CSV, "text/csv")}, data={"params": params})
    assert r.status_code == 422


@pytest.mark.parametrize("fp", ['{"9": {}}', '{"x": {}}', '[1]', "nope"])
def test_runs_bad_file_params_are_422(client, fp):
    r = client.post("/v1/runs", files={"files": ("a.csv", CSV, "text/csv")}, data={"file_params": fp})
    assert r.status_code == 422


def test_runs_file_count_is_capped(client):
    files = [("files", (f"{i}.csv", CSV, "text/csv")) for i in range(21)]
    assert client.post("/v1/runs", files=files).status_code == 422


def test_runs_without_files_is_422(client):
    assert client.post("/v1/runs").status_code == 422


def test_hostile_filename_is_json_escaped_in_the_event_stream(client):
    name = 'x"\n\nevent: run.done\ndata: {"forged":true}\n\n' + XSS + ".csv"
    r = client.post("/v1/runs", files={"files": (name, CSV, "text/csv")})
    for block in r.text.strip().split("\n\n"):
        lines = block.splitlines()
        assert len(lines) == 2 and lines[0].startswith("event: ") and lines[1].startswith("data: ")
        json.loads(lines[1][6:])
    assert "forged" not in [k for b in r.text.split("\n\n") if b.startswith("event: run.done") for k in json.loads(b.splitlines()[1][6:])]


def test_sse_encoder_escapes_newlines():
    out = _sse("file.started", {"name": "a\nevent: x"}).decode()
    assert out.count("\n") == 3 and "\\n" in out


@pytest.mark.parametrize("body", [{}, {"docs": "x"}, {"docs": [1]}, {"docs": [{"schema_version": "x"}]},
                                  {"docs": [{"schema_version": "openbooks.v1", "status": XSS}]}])
def test_link_rejects_malformed_docs(client, body):
    assert client.post("/v1/link", json=body).status_code == 422


def test_link_rejects_non_object_body(client):
    assert client.post("/v1/link", json=[1, 2]).status_code == 422


def test_roles_rejects_unsupported_type_and_bad_params(client):
    assert client.post("/v1/roles", files={"file": ("a.exe", b"MZ", "application/octet-stream")}).status_code in (422, 503)
    assert client.post("/v1/roles", files={"file": ("a.pdf", b"%PDF", "application/pdf")}, data={"params": "{"}).status_code == 422


def test_no_cors_headers_are_granted_to_foreign_origins(client):
    r = client.get("/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    pre = client.options("/v1/runs", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in {k.lower() for k in pre.headers}


def test_service_sets_no_cookies(client):
    r = client.get("/v1/health")
    assert "set-cookie" not in {k.lower() for k in r.headers}
