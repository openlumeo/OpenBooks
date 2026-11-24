from __future__ import annotations

import base64
import ipaddress
import json
import random
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from urllib.parse import urlsplit

from openbooks.statements.ocr_providers import (
    CapabilityRefused,
    ConfigError,
    ProviderConfig,
    ProviderError,
    ProviderUnavailable,
    redact_secrets,
    register_engine,
)
from openbooks.statements.pdf_words import Word

CLOUD_DPI = 300
HTTP_TIMEOUT_SECONDS = 60
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RATE_LIMIT_STATUSES = frozenset({429})
RETRY_BASE_SECONDS = 1.0
RETRY_CAP_SECONDS = 30.0
RETRY_MAX_RETRIES = 3
RETRY_BUDGET_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 1.0
POLL_LIMIT = 120
POLL_DEADLINE_SECONDS = 120.0
TEXTRACT_TIMEOUT_SECONDS = 60
TEXTRACT_MAX_ATTEMPTS = 3
UNIT_TOLERANCE = 0.01
HTTPS_PORT = 443
AZURE_ANALYZE_PATH = "/documentintelligence/documentModels/{model}:analyze"
AZURE_API_VERSION = "2024-11-30"
AZURE_KEY_ENV = "AZURE_DOCINTEL_KEY"
AZURE_ENDPOINT_ENV = "AZURE_DOCINTEL_ENDPOINT"
AZURE_LOCAL_SUFFIXES = (".localhost", ".local", ".localdomain", ".internal")
AZURE_DNS_NAME = re.compile(r"(?=[a-z0-9.-]{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]")
GOOGLE_TOKEN_ENV = "GOOGLE_DOCAI_ACCESS_TOKEN"
GOOGLE_HOST = "documentai.googleapis.com"
GOOGLE_LOCATION = re.compile(r"[a-z]{2,}(?:-[a-z0-9]+)*")
GOOGLE_PROJECT = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]+")
GOOGLE_PROCESSOR = re.compile(r"[A-Za-z0-9_-]+")
PNG_MIME = "image/png"
TEXTRACT_CONFIDENCE_SCALE = 100.0
WORD_BOXES_UNVERIFIED = "word boxes not verified for this provider"


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class Backoff:
    sleep: Callable[[float], None] = time.sleep
    uniform: Callable[[float, float], float] = random.uniform


Transport = Callable[[HttpRequest], HttpResponse]


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_NO_REDIRECT_OPENER = urllib.request.build_opener(_RefuseRedirects)


def _lower_keys(headers: Any) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def urlopen_transport(request: HttpRequest) -> HttpResponse:
    raw = urllib.request.Request(request.url, data=request.body, headers=dict(request.headers),
                                 method=request.method)
    try:
        with _NO_REDIRECT_OPENER.open(raw, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return HttpResponse(response.status, _lower_keys(response.headers), response.read(MAX_RESPONSE_BYTES + 1))
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, _lower_keys(error.headers), error.read(MAX_RESPONSE_BYTES + 1))


def _attempt(transport: Transport, request: HttpRequest, engine_id: str) -> HttpResponse:
    try:
        return transport(request)
    except OSError as error:
        raise ProviderUnavailable(f"{engine_id} unreachable: {type(error).__name__}") from None


def _retry_delay(response: HttpResponse, attempt: int, backoff: Backoff) -> float:
    raw = _lower_keys(response.headers).get("retry-after", "")
    if raw.replace(".", "", 1).isdigit():
        return min(float(raw), RETRY_CAP_SECONDS)
    return backoff.uniform(0.0, min(RETRY_CAP_SECONDS, RETRY_BASE_SECONDS * 2 ** attempt))


def _send(transport: Transport, request: HttpRequest, engine_id: str, backoff: Backoff) -> HttpResponse:
    retry_statuses = RETRY_STATUSES if request.method == "GET" else RATE_LIMIT_STATUSES
    response = _attempt(transport, request, engine_id)
    spent = 0.0
    for attempt in range(RETRY_MAX_RETRIES):
        if response.status not in retry_statuses:
            break
        delay = _retry_delay(response, attempt, backoff)
        if spent + delay > RETRY_BUDGET_SECONDS:
            break
        backoff.sleep(delay)
        spent += delay
        response = _attempt(transport, request, engine_id)
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise ProviderError(f"{engine_id} response exceeds the size limit")
    if not 200 <= response.status < 300:
        raise ProviderError(f"{engine_id} HTTP {response.status}")
    return response


def _unexpected(engine_id: str) -> ProviderError:
    return ProviderError(f"{engine_id} returned an unexpected response shape")


def _json_object(response: HttpResponse, engine_id: str) -> dict[str, Any]:
    try:
        data = json.loads(response.body)
    except ValueError as error:
        raise ProviderError(f"{engine_id} returned invalid JSON") from error
    if not isinstance(data, dict):
        raise _unexpected(engine_id)
    return data


def _object_list(node: Mapping[str, Any], key: str, engine_id: str) -> list[Any]:
    value = node.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise _unexpected(engine_id)
    return value


def _number(node: Mapping[str, Any], key: str, engine_id: str) -> float:
    value = node.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _unexpected(engine_id)
    return float(value)


def _unit(value: float, engine_id: str) -> float:
    if not -UNIT_TOLERANCE <= value <= 1 + UNIT_TOLERANCE:
        raise ProviderError(f"{engine_id} returned a normalised coordinate outside the page")
    return value


def _origin(url: str) -> tuple[str, str | None, int]:
    parts = urlsplit(url)
    return parts.scheme, parts.hostname, parts.port or HTTPS_PORT


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _validated_endpoint(raw: str) -> str:
    parts = urlsplit(raw)
    host = parts.hostname or ""
    unsafe = (
        parts.scheme != "https" or "@" in parts.netloc or parts.query or parts.fragment
        or parts.path not in ("", "/") or parts.netloc.partition(":")[2] not in ("", str(HTTPS_PORT))
        or _is_ip_literal(host) or not AZURE_DNS_NAME.fullmatch(host) or host.endswith(AZURE_LOCAL_SUFFIXES)
    )
    if unsafe:
        raise ConfigError("azure endpoint must be an https DNS hostname without credentials or unusual port")
    return raw.rstrip("/")


def _google_url(location: str, project: str, processor: str) -> str:
    host = f"{location}-{GOOGLE_HOST}"
    url = f"https://{host}/v1/projects/{project}/locations/{location}/processors/{processor}:process"
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in (GOOGLE_HOST, host) or parts.port is not None:
        raise CapabilityRefused("google_docai url is not a Document AI host")
    return url


def polygon_to_box(poly: Sequence[float], scale: float) -> tuple[float, float, float, float]:
    if len(poly) < 4 or len(poly) % 2 or scale <= 0:
        raise ProviderError("malformed polygon")
    xs, ys = poly[0::2], poly[1::2]
    return min(xs) / scale, min(ys) / scale, max(xs) / scale, max(ys) / scale


def encode_png(image: Any) -> bytes:
    try:
        from PIL import Image
    except ImportError as error:
        raise ProviderUnavailable("Pillow is required to encode page images; install 'openbooks[scan]'") from error
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()


def _word(text: str, box: tuple[float, float, float, float], conf: float, page_number: int,
          page_size: tuple[float, float]) -> Word:
    x0, y0, x1, y1 = box
    return Word(text, x0, y0, x1, y1, page_number, conf, page_size[0], page_size[1])


def _required_env(config: ProviderConfig, environ: Mapping[str, str], slot: str, default_name: str) -> str:
    name = config.env.get(slot, default_name)
    value = environ.get(name, "")
    if not value:
        raise ProviderUnavailable(f"missing environment variable {name}")
    return value


def _option(config: ProviderConfig, name: str, pattern: re.Pattern[str] | None = None) -> str:
    value = config.options.get(name, "")
    if not value:
        raise ConfigError(f"{config.id} requires option {name}")
    if pattern is not None and not pattern.fullmatch(value):
        raise ConfigError(f"{config.id} option {name} is malformed")
    return value


class _CloudEngine:
    remote = True
    preferred_dpi = CLOUD_DPI

    def __init__(self, config: ProviderConfig, secrets: Sequence[str] = (),
                 backoff: Backoff = Backoff()) -> None:
        self.id = config.id
        self._secrets = tuple(secret for secret in secrets if secret)
        self._backoff = backoff

    def read_page(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        try:
            return self._read(image, scale, page_number, page_size)
        except ProviderError as error:
            raise type(error)(redact_secrets(str(error), self._secrets)) from None
        except Exception as error:
            raise ProviderError(f"{self.id} read failed: {type(error).__name__}") from None

    def _read(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        raise NotImplementedError


def _png_b64(image: Any) -> str:
    return base64.b64encode(encode_png(image)).decode("ascii")


class AzureDocIntelEngine(_CloudEngine):
    def __init__(self, config: ProviderConfig, environ: Mapping[str, str],
                 transport: Transport = urlopen_transport, backoff: Backoff = Backoff()) -> None:
        key = _required_env(config, environ, "key", AZURE_KEY_ENV)
        super().__init__(config, (key,), backoff)
        self._key = key
        self._endpoint = _validated_endpoint(_required_env(config, environ, "endpoint", AZURE_ENDPOINT_ENV))
        model = config.options.get("model", "prebuilt-read")
        if model not in {"prebuilt-read", "prebuilt-layout"}:
            raise ProviderError(f"{self.id} configured an unsupported Azure model")
        self._analyze_url = f"{self._endpoint}{AZURE_ANALYZE_PATH.format(model=model)}?api-version={AZURE_API_VERSION}"
        self._transport = transport

    def _read(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        body = json.dumps({"base64Source": _png_b64(image)}).encode()
        headers = {"Ocp-Apim-Subscription-Key": self._key, "Content-Type": "application/json"}
        submitted = _send(self._transport, HttpRequest(
            "POST", self._analyze_url, headers, body),
            self.id, self._backoff)
        location = submitted.headers.get("operation-location")
        if not location:
            raise _unexpected(self.id)
        if _origin(location) != _origin(self._endpoint):
            raise ProviderError(f"{self.id} operation location is outside the configured endpoint")
        return self._words(self._await_result(location), scale, page_number, page_size)

    def _await_result(self, location: str) -> dict[str, Any]:
        poll = HttpRequest("GET", location, {"Ocp-Apim-Subscription-Key": self._key})
        deadline = time.monotonic() + POLL_DEADLINE_SECONDS
        for _ in range(POLL_LIMIT):
            result = _json_object(_send(self._transport, poll, self.id, self._backoff), self.id)
            status = result.get("status")
            if status == "succeeded":
                return result
            if status == "failed":
                raise ProviderError(f"{self.id} analysis failed")
            if status not in ("notStarted", "running"):
                raise _unexpected(self.id)
            if time.monotonic() >= deadline:
                break
            self._backoff.sleep(POLL_INTERVAL_SECONDS)
        raise ProviderUnavailable(f"{self.id} analysis timed out")

    def _words(self, result: Mapping[str, Any], scale: float, page_number: int,
               page_size: tuple[float, float]) -> list[Word]:
        analysis = result.get("analyzeResult")
        if not isinstance(analysis, dict):
            raise _unexpected(self.id)
        words: list[Word] = []
        for page in _object_list(analysis, "pages", self.id):
            if page.get("unit") != "pixel":
                raise ProviderError(f"{self.id} returned an unverified coordinate unit")
            for item in _object_list(page, "words", self.id):
                text, polygon = item.get("content"), item.get("polygon")
                if not isinstance(text, str) or not isinstance(polygon, list):
                    raise _unexpected(self.id)
                if not text.strip():
                    continue
                box = polygon_to_box([float(c) for c in polygon], scale)
                words.append(_word(text, box, _number(item, "confidence", self.id), page_number, page_size))
        return words


class GoogleDocAiEngine(_CloudEngine):
    def __init__(self, config: ProviderConfig, environ: Mapping[str, str],
                 transport: Transport = urlopen_transport, backoff: Backoff = Backoff()) -> None:
        token = _required_env(config, environ, "token", GOOGLE_TOKEN_ENV)
        super().__init__(config, (token,), backoff)
        location = _option(config, "location", GOOGLE_LOCATION)
        project = _option(config, "project", GOOGLE_PROJECT)
        processor = _option(config, "processor", GOOGLE_PROCESSOR)
        self._token = token
        self._url = _google_url(location, project, processor)
        self._transport = transport

    def _read(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        body = json.dumps({"rawDocument": {"content": _png_b64(image), "mimeType": PNG_MIME}}).encode()
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        response = _send(self._transport, HttpRequest("POST", self._url, headers, body), self.id, self._backoff)
        document = _json_object(response, self.id).get("document")
        if not isinstance(document, dict) or not isinstance(document.get("text", ""), str):
            raise _unexpected(self.id)
        text = document.get("text", "")
        words: list[Word] = []
        for page in _object_list(document, "pages", self.id):
            for token in _object_list(page, "tokens", self.id):
                piece = self._token_text(token, text)
                if not piece.strip():
                    continue
                box = self._token_box(token, scale, page_size)
                words.append(_word(piece, box, _number(self._layout(token), "confidence", self.id),
                                   page_number, page_size))
        return words

    def _layout(self, token: Mapping[str, Any]) -> Mapping[str, Any]:
        layout = token.get("layout")
        if not isinstance(layout, dict):
            raise _unexpected(self.id)
        return layout

    def _token_text(self, token: Mapping[str, Any], text: str) -> str:
        anchor = self._layout(token).get("textAnchor")
        if not isinstance(anchor, dict):
            raise _unexpected(self.id)
        segments = _object_list(anchor, "textSegments", self.id)
        return "".join(text[int(s.get("startIndex", 0)):int(_number(s, "endIndex", self.id))] for s in segments)

    def _token_box(self, token: Mapping[str, Any], scale: float,
                   page_size: tuple[float, float]) -> tuple[float, float, float, float]:
        poly = self._layout(token).get("boundingPoly")
        if not isinstance(poly, dict):
            raise _unexpected(self.id)
        if poly.get("normalizedVertices"):
            normalized = _object_list(poly, "normalizedVertices", self.id)
            xs = [_unit(float(v.get("x", 0.0)), self.id) for v in normalized]
            ys = [_unit(float(v.get("y", 0.0)), self.id) for v in normalized]
            width, height = page_size
            return min(xs) * width, min(ys) * height, max(xs) * width, max(ys) * height
        vertices = _object_list(poly, "vertices", self.id)
        return polygon_to_box([c for v in vertices for c in (float(v.get("x", 0.0)), float(v.get("y", 0.0)))], scale)


class TextractEngine(_CloudEngine):
    def __init__(self, config: ProviderConfig, environ: Mapping[str, str], client: Any | None = None) -> None:
        super().__init__(config)
        self._client = client if client is not None else _boto_textract_client(config)

    def _read(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        payload = encode_png(image)
        try:
            response = self._client.detect_document_text(Document={"Bytes": payload})
        except Exception:
            raise ProviderError(f"{self.id} request failed") from None
        if not isinstance(response, dict):
            raise _unexpected(self.id)
        width, height = page_size
        words: list[Word] = []
        for block in _object_list(response, "Blocks", self.id):
            if block.get("BlockType") != "WORD":
                continue
            text = block.get("Text")
            geometry = block.get("Geometry")
            if not isinstance(text, str) or not isinstance(geometry, dict):
                raise _unexpected(self.id)
            box = geometry.get("BoundingBox")
            if not isinstance(box, dict) or not text.strip():
                continue
            left = _unit(_number(box, "Left", self.id), self.id)
            top = _unit(_number(box, "Top", self.id), self.id)
            right = _unit(left + _unit(_number(box, "Width", self.id), self.id), self.id)
            bottom = _unit(top + _unit(_number(box, "Height", self.id), self.id), self.id)
            conf = _number(block, "Confidence", self.id) / TEXTRACT_CONFIDENCE_SCALE
            words.append(_word(text, (left * width, top * height, right * width, bottom * height), conf,
                               page_number, page_size))
        return words


def _boto_textract_client(config: ProviderConfig) -> Any:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:
        raise ProviderUnavailable("boto3 is required for aws_textract; install boto3") from error
    client_config = Config(
        connect_timeout=TEXTRACT_TIMEOUT_SECONDS,
        read_timeout=TEXTRACT_TIMEOUT_SECONDS,
        retries={"max_attempts": TEXTRACT_MAX_ATTEMPTS, "mode": "standard"},
    )
    try:
        return boto3.client("textract", region_name=config.options.get("region") or None, config=client_config)
    except Exception as error:
        raise ProviderUnavailable(f"textract client unavailable: {type(error).__name__}") from error


class UnverifiedWordBoxEngine(_CloudEngine):
    def __init__(self, config: ProviderConfig, environ: Mapping[str, str]) -> None:
        super().__init__(config)

    def _read(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        raise CapabilityRefused(WORD_BOXES_UNVERIFIED)


def register_all() -> None:
    register_engine("azure_docintel", AzureDocIntelEngine)
    register_engine("google_docai", GoogleDocAiEngine)
    register_engine("aws_textract", TextractEngine)
    register_engine("mistral_ocr", UnverifiedWordBoxEngine)
    register_engine("llamaparse", UnverifiedWordBoxEngine)
