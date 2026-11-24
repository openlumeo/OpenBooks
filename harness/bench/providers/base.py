from __future__ import annotations

import email.utils
import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 1.0
MAX_RETRY_AFTER_S = 60.0
MAX_ERROR_BODY_CHARS = 500
REDACTED = "[REDACTED]"
RATE_LIMIT_STATUS = 429
SERVER_ERROR_STATUS = 500


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    stop: str


class ProviderError(Exception):
    pass


class _Transient(Exception):
    def __init__(self, message: str, retry_after: float | None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def redact(text: str, secret: str) -> str:
    return text.replace(secret, REDACTED) if secret else text


def retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        seconds = when.timestamp() - time.time()
    if not math.isfinite(seconds):
        return None
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_S)


def usage_from(values: dict[str, Any], input_key: str, output_key: str) -> Usage:
    return Usage(
        input_tokens=int(values.get(input_key) or 0),
        output_tokens=int(values.get(output_key) or 0),
    )


def _send(url: str, headers: dict[str, str], data: bytes, timeout: float, secret: str) -> bytes:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        body = redact(error.read().decode("utf-8", "replace"), secret)[:MAX_ERROR_BODY_CHARS]
        message = redact(f"HTTP {error.code} from {url}: {body}", secret)
        if error.code == RATE_LIMIT_STATUS or error.code >= SERVER_ERROR_STATUS:
            raise _Transient(message, retry_after_seconds(error.headers.get("Retry-After"))) from None
        raise ProviderError(message) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        raise _Transient(redact(f"connection error calling {url}: {error}", secret), None) from None


def _backoff(retry_index: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return retry_after
    return BACKOFF_BASE_S * 2**retry_index


def _decode(raw: bytes, url: str, secret: str) -> dict[str, Any]:
    text = redact(raw.decode("utf-8", "replace"), secret)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        raise ProviderError(f"invalid JSON from {url}") from None
    if not isinstance(payload, dict):
        raise ProviderError(f"unexpected JSON payload from {url}")
    return payload


def post_json(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: float,
    *,
    secret: str = "",
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **headers}
    attempt = 0
    while True:
        try:
            raw = _send(url, request_headers, data, timeout, secret)
        except _Transient as transient:
            attempt += 1
            if attempt >= MAX_ATTEMPTS:
                raise ProviderError(str(transient)) from None
            sleep(_backoff(attempt - 1, transient.retry_after))
            continue
        return _decode(raw, url, secret)


class Provider:
    name: str = ""
    default_base_url: str = ""
    requires_key: bool = True
    sleep: Callable[[float], None] = staticmethod(time.sleep)

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        if self.requires_key and not api_key:
            raise ValueError(f"{self.name} provider needs an API key")
        self.model = model
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.timeout = timeout
        self._api_key = api_key or ""

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model!r}, base_url={self.base_url!r})"

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        url, headers, body = self.build_request(system, messages, tools)
        payload = post_json(
            url,
            headers,
            body,
            self.timeout,
            secret=self._api_key,
            sleep=self.sleep,
        )
        return self.parse_reply(payload, len(messages))

    def build_request(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        raise NotImplementedError

    def parse_reply(self, payload: dict[str, Any], turn: int) -> Reply:
        raise NotImplementedError
