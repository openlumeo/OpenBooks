"""Pure ASGI middleware: engine-key gate, request-id echo, pre-body refusal, status counter and access log.

Pure ASGI so server-sent events are streamed, not buffered.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Mapping

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import admission as adm
from .auth import engine_key_from_env, is_authorised
from .metrics import registry
from .responses import reject_response, unauthorised_response

log = logging.getLogger("openbooks_server")
REQUEST_ID_HEADER = b"x-request-id"
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,128}")
GUARDED_ROUTES = frozenset({("POST", "/v1/runs"), ("POST", "/v1/roles")})  # refused before the upload body is read
ROUTE_LABELS = frozenset({"/v1/runs", "/v1/roles", "/v1/link", "/v1/health", "/v1/formats", "/v1/samples",
                          "/healthz", "/readyz", "/metrics"})
SAMPLE_ROUTE_PREFIX = "/v1/samples/"
SAMPLE_ROUTE_LABEL = "/v1/samples/{id}"
UNKNOWN_ROUTE_LABEL = "other"

Headers = Mapping[bytes, bytes]


def valid_request_id(raw: str) -> str:
    """Echo a caller's request id only if it is 1-128 safe characters; otherwise mint a fresh one."""
    return raw if REQUEST_ID_PATTERN.fullmatch(raw) else uuid.uuid4().hex


def route_label(path: str) -> str:
    """Bounded metric label for a path, so arbitrary URLs cannot explode cardinality."""
    if path.startswith(SAMPLE_ROUTE_PREFIX):
        return SAMPLE_ROUTE_LABEL
    return path if path in ROUTE_LABELS else UNKNOWN_ROUTE_LABEL


def declared_length(headers: Headers) -> int:
    """The Content-Length the caller declared; a missing or malformed value counts as zero."""
    try:
        return int(headers.get(b"content-length", b"0") or 0)
    except ValueError:
        return 0


def early_refusal(method: str, path: str, headers: Headers) -> JSONResponse | None:
    """A 429/503 response for a guarded route that would be refused on admission, else None."""
    if (method, path) not in GUARDED_ROUTES:
        return None
    reason = adm.current.precheck(declared_length(headers))
    return reject_response(reason) if reason else None


class OpsMiddleware:
    """Wraps the app: authenticates, tags each request with an id, refuses early and records each request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.key = engine_key_from_env()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers: dict[bytes, bytes] = dict(scope["headers"])
        if not is_authorised(self.key, scope["path"], headers):
            return await unauthorised_response()(scope, receive, send)
        rid = valid_request_id(headers.get(REQUEST_ID_HEADER, b"").decode("latin-1"))
        scope.setdefault("state", {})["request_id"] = rid
        status, t0 = [500], time.perf_counter()

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status[0] = message["status"]
                message = {**message, "headers": [*message.get("headers", []), (REQUEST_ID_HEADER, rid.encode())]}
            await send(message)

        try:
            refusal = early_refusal(scope["method"], scope["path"], headers)
            if refusal is not None:
                return await refusal(scope, receive, send_with_id)
            await self.app(scope, receive, send_with_id)
        finally:
            self._record(scope, rid, status[0], t0)

    @staticmethod
    def _record(scope: Scope, rid: str, status: int, t0: float) -> None:
        route = route_label(scope["path"])
        registry.inc("openbooks_requests_total", route=route, status=str(status))
        log.info("request_id=%s %s %s status=%s ms=%.1f", rid, scope["method"], route, status,
                 (time.perf_counter() - t0) * 1000)
