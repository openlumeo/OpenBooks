import http.client
import json
import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from ui import server as ui_server

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
FAKE_SECRET = "fake-mistral-secret-7f3a9c"
SECRET_ENV_NAME = "MISTRAL_API_KEY"
VERIFY_FIELDS = {"currency": "INR", "date_order": "dmy", "opening": "1000.00"}
OVERSIZE_BYTES = ui_server.MAX_UPLOAD_BYTES + 1
OB_UI_HEADERS = {"X-OB-UI": "1"}
ESCAPE_SECRET = 'fake"quote\\slash\nnewline-é-</script>'


class Reply(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> object:
        return json.loads(self.body)


def send(
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    host: str | None = None,
) -> Reply:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    try:
        request_headers = dict(headers or {})
        if host is not None:
            request_headers["Host"] = host
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        lowered = {name.lower(): value for name, value in response.getheaders()}
        return Reply(response.status, lowered, response.read())
    finally:
        connection.close()


def multipart_body(filename: str, payload: bytes, fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "openbooks-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode()
        + payload
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def post_verify(port: int, filename: str, payload: bytes, fields: dict[str, str] | None = None) -> Reply:
    body, content_type = multipart_body(filename, payload, VERIFY_FIELDS if fields is None else fields)
    return send(port, "POST", "/api/verify", body=body, headers={"Content-Type": content_type, **OB_UI_HEADERS})


def assert_json_error(reply: Reply) -> None:
    assert reply.headers["content-type"].startswith("application/json")
    payload = reply.json()
    assert isinstance(payload, dict)
    assert isinstance(payload.get("error"), str)
    assert "Traceback" not in reply.body.decode("utf-8", "replace")


def assert_security_headers(reply: Reply) -> None:
    csp = reply.headers["content-security-policy"]
    for directive in ("frame-ancestors 'none'", "base-uri 'none'", "form-action 'self'"):
        assert directive in csp
    assert reply.headers["x-frame-options"] == "DENY"
    assert reply.headers["referrer-policy"] == "no-referrer"
    assert reply.headers["x-content-type-options"] == "nosniff"


@pytest.fixture(scope="module")
def module_monkeypatch() -> Iterator[pytest.MonkeyPatch]:
    patcher = pytest.MonkeyPatch()
    yield patcher
    patcher.undo()


@pytest.fixture(scope="module")
def ui_server_instance(module_monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    module_monkeypatch.setenv(SECRET_ENV_NAME, FAKE_SECRET)
    httpd = ui_server.create_server(port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def port(ui_server_instance: object) -> int:
    return ui_server_instance.server_address[1]  # type: ignore[attr-defined]


@pytest.fixture
def results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "bench-out"
    (root / "nested").mkdir(parents=True)
    (root / "ocr-compare.v1.json").write_text(json.dumps({"kind": "ocr"}), encoding="utf-8")
    (root / "nested" / "token-cost.v1.json").write_text(json.dumps({"kind": "tokens"}), encoding="utf-8")
    monkeypatch.setattr(ui_server, "RESULTS_DIR", root)
    return root


def test_server_binds_to_loopback_only(ui_server_instance: object) -> None:
    assert ui_server_instance.server_address[0] == "127.0.0.1"  # type: ignore[attr-defined]


def test_providers_lists_cloud_env_names_as_set_flags(port: int) -> None:
    reply = send(port, "GET", "/api/providers", host=f"127.0.0.1:{port}")

    assert reply.status == 200
    payload = reply.json()
    assert set(payload) >= {"default", "fallback", "remote_enabled", "providers"}
    mistral = next(item for item in payload["providers"] if item["id"] == "mistral")
    assert {"id", "engine", "remote", "available", "issue", "env"} <= set(mistral)
    assert {"name": SECRET_ENV_NAME, "set": True} in mistral["env"]


def test_providers_body_never_contains_secret_value(port: int) -> None:
    reply = send(port, "GET", "/api/providers", host=f"127.0.0.1:{port}")

    assert reply.status == 200
    assert FAKE_SECRET.encode() not in reply.body


def test_skills_returns_name_and_description_pairs(port: int) -> None:
    reply = send(port, "GET", "/api/skills", host=f"127.0.0.1:{port}")

    assert reply.status == 200
    skills = reply.json()
    assert isinstance(skills, list)
    for skill in skills:
        assert set(skill) == {"name", "description"}


def test_results_listing_reports_json_files_under_results_folder(port: int, results_dir: Path) -> None:
    reply = send(port, "GET", "/api/results", host=f"127.0.0.1:{port}")

    assert reply.status == 200
    files = {item["name"]: item for item in reply.json()["files"]}
    assert set(files) == {"ocr-compare.v1.json", "nested/token-cost.v1.json"}
    assert files["ocr-compare.v1.json"]["kind"] == "ocr-compare"


def test_result_file_returns_stored_json(port: int, results_dir: Path) -> None:
    reply = send(port, "GET", "/api/results/nested/token-cost.v1.json", host=f"127.0.0.1:{port}")

    assert reply.status == 200
    assert reply.json() == {"kind": "tokens"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/results/../outside.json",
        "/api/results/nested/../../outside.json",
        "/api/results/%2Fetc%2Fpasswd",
        "/api/results/..%5Coutside.json",
        "/api/results/nested%5C..%5Coutside.json",
    ],
)
def test_result_path_escapes_are_rejected_with_400(port: int, results_dir: Path, path: str) -> None:
    reply = send(port, "GET", path, host=f"127.0.0.1:{port}")

    assert reply.status == 400
    assert_json_error(reply)


def test_missing_result_file_returns_404_json(port: int, results_dir: Path) -> None:
    reply = send(port, "GET", "/api/results/missing.v1.json", host=f"127.0.0.1:{port}")

    assert reply.status == 404
    assert_json_error(reply)


def test_symlink_inside_results_pointing_outside_is_rejected(
    port: int, results_dir: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"secret": True}), encoding="utf-8")
    link = results_dir / "escape.json"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlinks are not permitted on this platform")

    listing = send(port, "GET", "/api/results", host=f"127.0.0.1:{port}").json()
    reply = send(port, "GET", "/api/results/escape.json", host=f"127.0.0.1:{port}")

    assert "escape.json" not in {item["name"] for item in listing["files"]}
    assert reply.status == 400
    assert b'"secret"' not in reply.body


def test_verify_released_for_balanced_sample_csv(port: int) -> None:
    payload = (SAMPLES_DIR / "statement_balanced.csv").read_bytes()

    reply = post_verify(port, "statement_balanced.csv", payload)

    assert reply.status == 200
    body = reply.json()
    assert body["status"] == "released"
    assert body["doc"]["status"] == "ok"
    assert "ocr" in body


def test_verify_refused_with_code_for_tampered_sample_csv(port: int) -> None:
    payload = (SAMPLES_DIR / "statement_tampered.csv").read_bytes()

    reply = post_verify(port, "statement_tampered.csv", payload)

    assert reply.status == 200
    body = reply.json()
    assert body["status"] == "refused"
    assert body["doc"]["error"]["code"] == "BALANCE_MISMATCH"


def test_verify_rejects_disallowed_extension_with_415(port: int) -> None:
    reply = post_verify(port, "payload.exe", b"MZ")

    assert reply.status == 415
    assert_json_error(reply)


def test_verify_rejects_declared_length_over_limit_with_413(port: int) -> None:
    headers = {
        "Content-Type": "multipart/form-data; boundary=x",
        "Content-Length": str(OVERSIZE_BYTES + ui_server.MULTIPART_OVERHEAD_BYTES),
        **OB_UI_HEADERS,
    }

    reply = send(port, "POST", "/api/verify", headers=headers)

    assert reply.status == 413
    assert_json_error(reply)


def test_verify_rejects_file_payload_over_20mb_with_413(port: int) -> None:
    reply = post_verify(port, "huge.csv", b"a" * OVERSIZE_BYTES)

    assert reply.status == 413
    assert_json_error(reply)


def test_verify_rejects_non_multipart_body_with_415(port: int) -> None:
    reply = send(
        port,
        "POST",
        "/api/verify",
        body=b'{"file": "x"}',
        headers={"Content-Type": "application/json", **OB_UI_HEADERS},
    )

    assert reply.status == 415
    assert_json_error(reply)


def test_verify_without_ui_header_is_forbidden(port: int) -> None:
    body, content_type = multipart_body("statement_balanced.csv", b"x", VERIFY_FIELDS)

    reply = send(port, "POST", "/api/verify", body=body, headers={"Content-Type": content_type})

    assert reply.status == 403
    assert_json_error(reply)


@pytest.mark.parametrize("value", ["0", ""])
def test_verify_with_wrong_ui_header_is_forbidden(port: int, value: str) -> None:
    body, content_type = multipart_body("statement_balanced.csv", b"x", VERIFY_FIELDS)

    reply = send(port, "POST", "/api/verify", body=body, headers={"Content-Type": content_type, "X-OB-UI": value})

    assert reply.status == 403
    assert_json_error(reply)


def test_ui_header_is_checked_before_body_is_read(port: int) -> None:
    headers = {
        "Content-Type": "multipart/form-data; boundary=x",
        "Content-Length": str(OVERSIZE_BYTES),
    }

    reply = send(port, "POST", "/api/verify", headers=headers)

    assert reply.status == 403
    assert_json_error(reply)


def test_root_serves_index_html_with_security_headers(port: int) -> None:
    reply = send(port, "GET", "/", host=f"localhost:{port}")

    assert reply.status == 200
    assert reply.headers["content-type"].startswith("text/html")
    assert reply.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in reply.headers["content-security-policy"]


def test_static_file_is_served_from_static_folder(port: int) -> None:
    reply = send(port, "GET", "/static/index.html", host=f"localhost:{port}")

    assert reply.status == 200
    assert reply.body == (Path(ui_server.STATIC_DIR) / "index.html").read_bytes()


@pytest.mark.parametrize(
    "path",
    [
        "/static/../server.py",
        "/static/..%2Fserver.py",
        "/static/..%5Cserver.py",
        "/static/%2Fetc%2Fpasswd",
    ],
)
def test_static_traversal_is_rejected(port: int, path: str) -> None:
    reply = send(port, "GET", path, host=f"localhost:{port}")

    assert reply.status == 400
    assert_json_error(reply)


def test_api_responses_carry_security_headers(port: int) -> None:
    reply = send(port, "GET", "/api/skills", host=f"127.0.0.1:{port}")

    assert_security_headers(reply)


def test_every_response_kind_carries_security_headers(port: int) -> None:
    replies = [
        send(port, "GET", "/", host=f"localhost:{port}"),
        send(port, "GET", "/api/skills", host=f"127.0.0.1:{port}"),
        send(port, "GET", "/no-such-route", host=f"127.0.0.1:{port}"),
        send(port, "GET", "/api/skills", host="attacker.example"),
        send(port, "POST", "/api/verify", headers={"Content-Type": "application/json"}),
    ]

    for reply in replies:
        assert_security_headers(reply)


def test_non_json_result_file_is_refused_with_415(port: int, results_dir: Path) -> None:
    (results_dir / "notes.txt").write_text("plain", encoding="utf-8")
    (results_dir / "nested" / "notes.csv").write_text("a,b", encoding="utf-8")

    for path in ("/api/results/notes.txt", "/api/results/nested/notes.csv"):
        reply = send(port, "GET", path, host=f"127.0.0.1:{port}")

        assert reply.status == 415
        assert_json_error(reply)


def test_providers_body_never_contains_escaped_secret_value(port: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV_NAME, ESCAPE_SECRET)

    reply = send(port, "GET", "/api/providers", host=f"127.0.0.1:{port}")

    assert reply.status == 200
    for encoded in (
        ESCAPE_SECRET,
        json.dumps(ESCAPE_SECRET)[1:-1],
        json.dumps(ESCAPE_SECRET, ensure_ascii=True)[1:-1],
    ):
        assert encoded.encode("utf-8") not in reply.body


def test_unknown_route_returns_json_404_without_traceback(port: int) -> None:
    reply = send(port, "GET", "/no-such-route", host=f"127.0.0.1:{port}")

    assert reply.status == 404
    assert_json_error(reply)


@pytest.mark.parametrize(
    "host",
    [
        "evil.example.com",
        "evil.example.com:8777",
        "localhost.evil.example",
        "evil.com@localhost",
        "localhost:123456",
    ],
)
def test_rebinding_host_header_is_forbidden(port: int, host: str) -> None:
    reply = send(port, "GET", "/api/providers", host=host)

    assert reply.status == 403
    assert_json_error(reply)


def test_rebinding_host_header_is_forbidden_on_verify(port: int) -> None:
    body, content_type = multipart_body("statement_balanced.csv", b"x", VERIFY_FIELDS)

    reply = send(
        port,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": content_type, **OB_UI_HEADERS},
        host="evil.com@localhost",
    )

    assert reply.status == 403
    assert_json_error(reply)


def test_rebinding_host_header_is_forbidden_on_root(port: int) -> None:
    reply = send(port, "GET", "/", host="attacker.example")

    assert reply.status == 403


@pytest.mark.parametrize("host_template", ["127.0.0.1:{port}", "localhost:{port}", "[::1]:{port}"])
def test_loopback_host_headers_are_accepted(port: int, host_template: str) -> None:
    reply = send(port, "GET", "/api/skills", host=host_template.format(port=port))

    assert reply.status == 200
