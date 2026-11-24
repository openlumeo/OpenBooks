from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
from collections import deque
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from email.message import Message
from email.parser import BytesParser
from email.policy import HTTP
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from openbooks.core import Params, process
from openbooks.core.guard import ALLOWED_EXT
from openbooks.statements.ocr_providers import (
    ALLOW_REMOTE_ENV,
    ConfigError,
    ProviderConfig,
    PROVIDER_ENV,
    PROVIDERS_FILE_ENV,
    CLOUD_ENGINES,
    _resolve_tesseract,
    load_settings,
)
from openbooks.statements.pdf_front import last_ocr_engines, last_ocr_run

HARNESS_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
RESULTS_DIR = HARNESS_DIR / "bench-out"
SKILLS_DIR = HARNESS_DIR / "skills"
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8777
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 64 * 1024
LOCAL_HOST_HEADER = re.compile(r"(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?")
UI_REQUEST_HEADER = "X-OB-UI"
BODY_DEADLINE_SECONDS = 60
READ_CHUNK_BYTES = 64 * 1024
RESULT_KINDS = frozenset({"ocr-compare", "speed-bench", "screenshot-bench", "model-context-bench", "token-cost", "risk-coverage", "bench-result"})
TEXT_FIELDS = frozenset({"currency", "date_order", "opening", "provider", "remote_consent", "api_key"})
DATE_ORDERS = frozenset({"dmy", "mdy"})
CURRENCY = re.compile(r"[A-Za-z]{3}")
PLAIN_NUMBER = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)")
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}
SECURITY_HEADERS = (
    ("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Content-Type-Options", "nosniff"),
    ("Cache-Control", "no-store"),
)
logger = logging.getLogger("openbooks.ui")
VERIFY_LIMIT = threading.BoundedSemaphore(2)
RATE_LOCK = threading.Lock()
RECENT_VERIFICATIONS: deque[float] = deque()
VERIFY_TIMEOUT_SECONDS = 330


class RequestError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class EnvStatus:
    name: str
    set: bool


@dataclass(frozen=True)
class ProviderStatus:
    id: str
    engine: str
    remote: bool
    available: bool
    issue: str | None
    env: tuple[EnvStatus, ...]


@dataclass(frozen=True)
class Upload:
    filename: str
    payload: bytes
    fields: dict[str, str]


def is_local_host(host_header: str | None) -> bool:
    return host_header is not None and LOCAL_HOST_HEADER.fullmatch(host_header) is not None


def safe_join(base: Path, relative: str) -> Path | None:
    if not relative or "\\" in relative or "\x00" in relative:
        return None
    root = base.resolve()
    target = (root / relative).resolve()
    return target if target.is_relative_to(root) else None


def provider_status(config: ProviderConfig, environ: Mapping[str, str]) -> ProviderStatus:
    env = tuple(EnvStatus(name, bool(environ.get(name))) for name in config.env.values())
    if config.engine in {"llamaparse", "mistral_ocr"}:
        available = False
        issue = "word-box adapter is not implemented"
    elif config.engine == "tesseract":
        available = _resolve_tesseract(environ) is not None
        issue = None if available else "tesseract binary not found"
    elif config.engine == "easyocr":
        available = importlib.util.find_spec("easyocr") is not None
        issue = None if available else "easyocr is not installed"
    else:
        available = all(item.set for item in env)
        issue = None if available else "missing environment variables: " + ", ".join(item.name for item in env if not item.set)
    return ProviderStatus(config.id, config.engine, config.remote, available, issue, env)


def providers_payload(environ: Mapping[str, str] = os.environ) -> dict[str, Any]:
    settings = load_settings(None, environ)
    return {
        "default": settings.default,
        "fallback": settings.fallback,
        "remote_enabled": settings.allow_remote and environ.get(ALLOW_REMOTE_ENV) == "1",
        "providers": [asdict(provider_status(config, environ)) for config in settings.providers.values()],
    }


def read_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def skills_payload() -> list[dict[str, str]]:
    frontmatters = (read_frontmatter(path) for path in sorted(SKILLS_DIR.glob("*/SKILL.md")))
    return [{"name": fields["name"], "description": fields.get("description", "")} for fields in frontmatters if "name" in fields]


def result_kind(name: str) -> str:
    stem = Path(name).stem.split(".", 1)[0]
    return stem if stem in RESULT_KINDS else "other"


def results_payload() -> dict[str, list[dict[str, Any]]]:
    root = RESULTS_DIR.resolve()
    files: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.rglob("*.json")):
            name = path.relative_to(root).as_posix()
            if path.is_file() and safe_join(root, name) is not None:
                stat = path.stat()
                files.append({"name": name, "kind": result_kind(name), "size": stat.st_size, "mtime": stat.st_mtime})
    return {"files": files}


def parse_params(fields: Mapping[str, str]) -> Params:
    currency = fields.get("currency", "").strip()
    if currency and not CURRENCY.fullmatch(currency):
        raise RequestError(HTTPStatus.BAD_REQUEST, "currency must be a three-letter code")
    opening_text = fields.get("opening", "").strip()
    if opening_text and not PLAIN_NUMBER.fullmatch(opening_text):
        raise RequestError(HTTPStatus.BAD_REQUEST, "opening must be a plain number")
    opening = Decimal(opening_text) if opening_text else None
    date_order = fields.get("date_order", "").strip() or None
    if date_order is not None and date_order not in DATE_ORDERS:
        raise RequestError(HTTPStatus.BAD_REQUEST, "date_order must be dmy or mdy")
    return Params(currency=currency.upper() or None, opening=opening, date_order=date_order)


def read_upload(content_type: str, body: bytes) -> Upload:
    message = BytesParser(policy=HTTP).parsebytes(f"Content-Type: {content_type}\r\n\r\n".encode("latin-1") + body)
    if not message.is_multipart():
        raise RequestError(HTTPStatus.BAD_REQUEST, "malformed multipart body")
    filename: str | None = None
    payload = b""
    fields: dict[str, str] = {}
    for part in message.get_payload():
        if not isinstance(part, Message):
            continue
        name = part.get_param("name", header="content-disposition")
        if name == "file":
            filename = part.get_filename() or ""
            payload = part.get_payload(decode=True) or b""
        elif name in TEXT_FIELDS:
            fields[name] = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
    if filename is None:
        raise RequestError(HTTPStatus.BAD_REQUEST, "file is required")
    return Upload(filename, payload, fields)


def verify_path(document: Path, params: Params) -> dict[str, Any]:
    doc = process(document, params)
    engines = last_ocr_engines()
    ocr = None
    if engines:
        run = last_ocr_run()
        ocr = {"engines": list(engines), "fallback_used": bool(run and run.used_fallback)}
    return {"status": "released" if doc.get("status") == "ok" else "refused", "doc": doc, "ocr": ocr}


def verify_isolated(upload: Upload, provider: str) -> dict[str, Any]:
    env = {**os.environ, PROVIDER_ENV: provider}
    if upload.fields.get("remote_consent") != "true":
        env.pop(ALLOW_REMOTE_ENV, None)
    with tempfile.TemporaryDirectory(prefix="openbooks-ui-") as directory:
        source = Path(directory) / ("document" + Path(upload.filename).suffix.lower())
        source.write_bytes(upload.payload)
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--verify-worker"],
                input=json.dumps({"path": str(source), "fields": upload.fields}), text=True, capture_output=True,
                env=env, timeout=VERIFY_TIMEOUT_SECONDS, check=False,
            )
        except subprocess.TimeoutExpired:
            raise RequestError(HTTPStatus.GATEWAY_TIMEOUT, "verification timed out") from None
        if result.returncode != 0:
            raise RequestError(HTTPStatus.INTERNAL_SERVER_ERROR, "verification failed")
        try:
            return json.loads(result.stdout)
        except (ValueError, TypeError):
            raise RequestError(HTTPStatus.INTERNAL_SERVER_ERROR, "verification failed") from None


def check_provider(fields: Mapping[str, str]) -> str:
    settings = load_settings()
    provider = fields.get("provider", "").strip() or "tesseract"
    selected = settings.providers.get(provider)
    if selected is None and provider in {"tesseract", "easyocr"}:
        selected = ProviderConfig(provider, provider, {}, {}, False)
    if selected is None:
        raise RequestError(HTTPStatus.BAD_REQUEST, "unknown OCR provider")
    api_key = fields.get("api_key", "")
    if api_key and (selected.engine != "azure_docintel" or len(api_key) > 4096 or "\x00" in api_key):
        raise RequestError(HTTPStatus.BAD_REQUEST, "invalid API key for selected provider")
    if selected.engine in {"llamaparse", "mistral_ocr"}:
        raise RequestError(HTTPStatus.BAD_REQUEST, "selected OCR provider is not implemented")
    remote = selected.remote or selected.engine in CLOUD_ENGINES
    if remote and fields.get("remote_consent") != "true":
        raise RequestError(HTTPStatus.FORBIDDEN, "remote OCR consent is required")
    if remote and not (settings.allow_remote and os.environ.get(ALLOW_REMOTE_ENV) == "1"):
        raise RequestError(HTTPStatus.FORBIDDEN, "remote OCR is not enabled in configuration")
    return provider


def admit_verification() -> None:
    now = time.monotonic()
    with RATE_LOCK:
        while RECENT_VERIFICATIONS and RECENT_VERIFICATIONS[0] <= now - 60:
            RECENT_VERIFICATIONS.popleft()
        if len(RECENT_VERIFICATIONS) >= 20:
            raise RequestError(HTTPStatus.TOO_MANY_REQUESTS, "verification rate limit exceeded")
        RECENT_VERIFICATIONS.append(now)


class UiHandler(BaseHTTPRequestHandler):
    server_version = "OpenBooksUI"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:
        self._dispatch(self._route_get)

    def do_POST(self) -> None:
        self._dispatch(self._route_post)

    def log_message(self, format: str, *args: Any) -> None: return

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        self._send_json(HTTPStatus(code), {"error": HTTPStatus(code).phrase})

    def _dispatch(self, route: Callable[[str], None]) -> None:
        path = urlsplit(self.path).path
        if not is_local_host(self.headers.get("Host")):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden host"})
            return
        try:
            route(path)
        except RequestError as error:
            self._send_json(error.status, {"error": str(error)})
        except ConfigError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "provider configuration is invalid"})
        except Exception as error:
            logger.error("%s %s failed: %s", self.command, path, type(error).__name__)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal error"})

    def _route_get(self, path: str) -> None:
        if path in ("/", "/index.html"):
            self._send_static("index.html")
        elif path.startswith("/static/"):
            self._send_static(unquote(path.removeprefix("/static/")))
        elif path == "/api/providers":
            self._send_json(HTTPStatus.OK, providers_payload())
        elif path == "/api/skills":
            self._send_json(HTTPStatus.OK, skills_payload())
        elif path == "/api/results":
            self._send_json(HTTPStatus.OK, results_payload())
        elif path.startswith("/api/results/"):
            self._send_result(unquote(path.removeprefix("/api/results/")))
        else:
            raise RequestError(HTTPStatus.NOT_FOUND, "not found")

    def _route_post(self, path: str) -> None:
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}", f"https://{host}"}:
            raise RequestError(HTTPStatus.FORBIDDEN, "forbidden origin")
        if path != "/api/verify":
            raise RequestError(HTTPStatus.NOT_FOUND, "not found")
        if self.headers.get(UI_REQUEST_HEADER) != "1":
            raise RequestError(HTTPStatus.FORBIDDEN, "missing UI request header")
        self._verify()

    def _send_static(self, relative: str) -> None:
        target = self._existing_file(STATIC_DIR, relative)
        self._send(HTTPStatus.OK, target.read_bytes(), CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream"))

    def _send_result(self, relative: str) -> None:
        target = self._existing_file(RESULTS_DIR, relative)
        if target.suffix != ".json":
            raise RequestError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "only .json results are served")
        self._send(HTTPStatus.OK, target.read_bytes(), CONTENT_TYPES[".json"])

    @staticmethod
    def _existing_file(base: Path, relative: str) -> Path:
        target = safe_join(base, relative)
        if target is None:
            raise RequestError(HTTPStatus.BAD_REQUEST, "invalid path")
        if not target.is_file():
            raise RequestError(HTTPStatus.NOT_FOUND, "not found")
        return target

    def _verify(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            raise RequestError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "multipart/form-data is required")
        length = self._content_length()
        if length > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES:
            raise RequestError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "upload exceeds 20 MB")
        upload = read_upload(content_type, self._read_body(length))
        if len(upload.payload) > MAX_UPLOAD_BYTES:
            raise RequestError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "upload exceeds 20 MB")
        if Path(upload.filename).suffix.lower() not in ALLOWED_EXT:
            raise RequestError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "file type is not supported")
        parse_params(upload.fields)
        provider = check_provider(upload.fields)
        admit_verification()
        if not VERIFY_LIMIT.acquire(blocking=False):
            raise RequestError(HTTPStatus.SERVICE_UNAVAILABLE, "verification capacity reached")
        try:
            result = verify_isolated(upload, provider)
        finally:
            VERIFY_LIMIT.release()
        self._send_json(HTTPStatus.OK, result)

    def _read_body(self, length: int) -> bytes:
        deadline = time.monotonic() + BODY_DEADLINE_SECONDS
        body = bytearray()
        while len(body) < length:
            if time.monotonic() > deadline:
                raise RequestError(HTTPStatus.REQUEST_TIMEOUT, "request body read timed out")
            try:
                chunk = self.rfile.read1(min(READ_CHUNK_BYTES, length - len(body)))
            except socket.timeout:
                raise RequestError(HTTPStatus.REQUEST_TIMEOUT, "request body read timed out") from None
            if not chunk:
                break
            body.extend(chunk)
        if len(body) != length:
            raise RequestError(HTTPStatus.BAD_REQUEST, "incomplete upload")
        return bytes(body)

    def _content_length(self) -> int:
        raw = self.headers.get("Content-Length")
        if raw is None:
            raise RequestError(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required")
        if not (raw.isascii() and raw.isdigit()):
            raise RequestError(HTTPStatus.BAD_REQUEST, "invalid Content-Length")
        return int(raw)

    def _send_json(self, status: HTTPStatus, payload: Any) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        logger.info("%s %s %d", self.command or "-", urlsplit(self.path).path, status.value)


class UiServer(ThreadingHTTPServer):
    request_slots = threading.BoundedSemaphore(16)

    def get_request(self) -> tuple[Any, Any]:
        request, address = super().get_request()
        request.settimeout(15)
        return request, address

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self.request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.request_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()

    def handle_error(self, request: Any, client_address: Any) -> None:
        logger.error("connection error: %s", sys.exc_info()[0].__name__)


def create_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return UiServer((LOOPBACK_HOST, port), UiHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ui.server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--verify-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.verify_worker:
        request = json.load(sys.stdin)
        fields = request["fields"]
        api_key = fields.pop("api_key", "")
        if api_key:
            os.environ["AZURE_DOCINTEL_KEY"] = api_key
        output = json.dumps(verify_path(Path(request["path"]), parse_params(fields)), ensure_ascii=False, default=str)
        if api_key:
            output = output.replace(api_key, "[REDACTED]").replace(json.dumps(api_key)[1:-1], "[REDACTED]")
        print(output)
        return 0
    os.environ.setdefault(PROVIDERS_FILE_ENV, str(HARNESS_DIR / "openbooks.providers.toml"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = create_server(args.port)
    host, port = server.server_address[:2]
    print(f"Open Books UI on http://{host}:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
