from __future__ import annotations

import importlib
import importlib.util
import math
import os
import re
import shutil
import subprocess
import threading
import time
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

from openbooks.core.errors import EngineFault
from openbooks.statements.pdf_words import Word

MAX_WORDS_PER_PAGE = 20_000
TESSERACT_TIMEOUT_SECONDS = 60
TESSERACT_DPI = 240
EASYOCR_DPI = 200
PROVIDER_ENV = "OPENBOOKS_OCR_PROVIDER"
PROVIDERS_FILE_ENV = "OPENBOOKS_PROVIDERS_FILE"
ALLOW_REMOTE_ENV = "OPENBOOKS_ALLOW_REMOTE_OCR"
TESSERACT_CMD_ENV = "OPENBOOKS_TESSERACT_CMD"
PROVIDERS_FILENAME = "openbooks.providers.toml"
CLOUD_ENGINES = frozenset({"azure_docintel", "google_docai", "aws_textract", "mistral_ocr", "llamaparse"})
WINDOWS_TESSERACT_PATHS = (r"C:\Program Files\Tesseract-OCR\tesseract.exe",)
TESSERACT_LANG = re.compile(r"[A-Za-z_+]+")
TESSERACT_PSM = re.compile(r"1[0-3]|[0-9]")
SECRET_PREFIXES = ("sk-", "AIza", "xai-")
SECRET_TOKEN = re.compile(r"[A-Za-z0-9_\-+/=]{32,}")
CONCURRENCY_ENV = "OPENBOOKS_OCR_CONCURRENCY"
REMOTE_PAGES_ENV = "OPENBOOKS_OCR_MAX_REMOTE_PAGES"
DEFAULT_REMOTE_CONCURRENCY = 2
DEFAULT_REMOTE_PAGES = 200
OCR_DEADLINE_SECONDS = 300.0
ENGINE_ENV_ALLOWLIST: dict[str, frozenset[str]] = {
    "azure_docintel": frozenset({"AZURE_DOCINTEL_ENDPOINT", "AZURE_DOCINTEL_KEY"}),
    "google_docai": frozenset({"GOOGLE_DOCAI_PROCESSOR", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_DOCAI_ACCESS_TOKEN"}),
    "aws_textract": frozenset({"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "AWS_SESSION_TOKEN"}),
    "mistral_ocr": frozenset({"MISTRAL_API_KEY"}),
    "llamaparse": frozenset({"LLAMA_CLOUD_API_KEY"}),
}


class ProviderError(Exception):
    pass


class ProviderUnavailable(ProviderError):
    pass


class CapabilityRefused(ProviderError):
    pass


class ConfigError(Exception):
    pass


class OcrEngine(Protocol):
    id: str
    remote: bool
    preferred_dpi: int

    def read_page(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]: ...


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    engine: str
    env: dict[str, str]
    options: dict[str, str]
    remote: bool


@dataclass(frozen=True)
class ProviderSettings:
    default: str
    fallback: str | None
    allow_remote: bool
    providers: dict[str, ProviderConfig]


@dataclass(frozen=True)
class OcrRun:
    engine_id: str
    used_fallback: bool
    pages: list[list[Word]]


@dataclass(frozen=True)
class PageInput:
    image: Any
    scale: float
    page_number: int
    page_size: tuple[float, float]


EngineFactory = Callable[[ProviderConfig, Mapping[str, str]], OcrEngine]
_REGISTRY: dict[str, EngineFactory] = {}
_REGISTRY_LOCK = threading.Lock()


def redact_secrets(text: str, secrets: Iterable[str]) -> str:
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def looks_like_secret(value: str) -> bool:
    if value.startswith(SECRET_PREFIXES) or "-----BEGIN" in value:
        return True
    return SECRET_TOKEN.fullmatch(value) is not None


def register_engine(name: str, factory: EngineFactory) -> None:
    with _REGISTRY_LOCK:
        _REGISTRY[name] = factory


def _find_providers_file(environ: Mapping[str, str]) -> Path | None:
    named = environ.get(PROVIDERS_FILE_ENV)
    if named:
        return Path(named)
    parents = Path(__file__).resolve().parents
    shipped = parents[6] / "harness" / PROVIDERS_FILENAME if len(parents) > 6 else None
    return shipped if shipped is not None and shipped.is_file() else None


def _reject_secrets(node: Any, field: str) -> None:
    if isinstance(node, str):
        if looks_like_secret(node):
            raise ConfigError(f"secret-looking value in {field}")
    elif isinstance(node, dict):
        for key, value in node.items():
            _reject_secrets(value, f"{field}.{key}")


def _string_table(raw: Any, field: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ConfigError(f"{field} must be a table")
    return {str(k): str(v) for k, v in raw.items()}


def _parse_provider(provider_id: str, raw: Any) -> ProviderConfig:
    field = f"providers.{provider_id}"
    if not isinstance(raw, dict) or not isinstance(raw.get("engine"), str):
        raise ConfigError(f"{field}.engine must be a string")
    remote = raw.get("remote", False)
    if not isinstance(remote, bool):
        raise ConfigError(f"{field}.remote must be a boolean")
    engine = raw["engine"]
    env = _string_table(raw.get("env", {}), f"{field}.env")
    options = _string_table(raw.get("options", {}), f"{field}.options")
    allowed = ENGINE_ENV_ALLOWLIST.get(engine, frozenset())
    if refused := [slot for slot, name in env.items() if name not in allowed]:
        raise ConfigError(f"{field}.env slots {', '.join(sorted(refused))} name variables outside the allowlist for {engine}")
    if options.get("cmd_env", TESSERACT_CMD_ENV) != TESSERACT_CMD_ENV:
        raise ConfigError(f"{field}.options.cmd_env may only be {TESSERACT_CMD_ENV}")
    return ProviderConfig(id=provider_id, engine=engine, env=env, options=options, remote=remote)


def load_settings(path: Path | None = None, environ: Mapping[str, str] = os.environ) -> ProviderSettings:
    source = path if path is not None else _find_providers_file(environ)
    data: dict[str, Any] = {}
    if source is not None:
        try:
            data = tomllib.loads(source.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ConfigError(f"cannot read providers file: {type(error).__name__}") from error
    _reject_secrets(data, "config")
    providers_raw = data.get("providers", {})
    if not isinstance(providers_raw, dict):
        raise ConfigError("providers must be a table")
    fallback, default, allow_remote = data.get("fallback"), data.get("default", "tesseract"), data.get("allow_remote", False)
    if not isinstance(default, str) or not (fallback is None or isinstance(fallback, str)):
        raise ConfigError("default and fallback must be strings")
    if not isinstance(allow_remote, bool):
        raise ConfigError("allow_remote must be a boolean")
    return ProviderSettings(
        default=default,
        fallback=fallback,
        allow_remote=allow_remote,
        providers={pid: _parse_provider(pid, raw) for pid, raw in providers_raw.items()},
    )


def read_page_with(engine: OcrEngine, image: Any, scale: float, page_number: int,
                   page_size: tuple[float, float], secrets: Iterable[str] = ()) -> list[Word]:
    try:
        words = engine.read_page(image, scale, page_number, page_size)
    except ProviderError:
        raise
    except Exception as error:
        raise ProviderError(redact_secrets(f"{engine.id} failed: {type(error).__name__}", secrets)) from None
    if len(words) > MAX_WORDS_PER_PAGE:
        raise ProviderError(f"{engine.id} returned too many words for page {page_number}")
    for word in words:
        _validate_word(engine.id, word)
    return list(words)


def _validate_word(engine_id: str, word: Word) -> None:
    coords = (word.x0, word.y0, word.x1, word.y1)
    if not isinstance(word.text, str) or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in coords):
        raise ProviderError(f"{engine_id} returned a malformed word")
    if word.x1 < word.x0 or word.y1 < word.y0:
        raise ProviderError(f"{engine_id} returned an invalid box")
    if word.conf is not None and not (math.isfinite(word.conf) and 0.0 <= word.conf <= 1.0):
        raise ProviderError(f"{engine_id} returned a confidence outside 0..1")


def _resolve_tesseract(environ: Mapping[str, str], cmd_env: str = TESSERACT_CMD_ENV) -> str | None:
    named = environ.get(cmd_env)
    if named:
        return named if Path(named).is_file() else shutil.which(named)
    found = shutil.which("tesseract")
    if found:
        return found
    return next((p for p in WINDOWS_TESSERACT_PATHS if Path(p).is_file()), None)


def tesseract_available(environ: Mapping[str, str] = os.environ) -> tuple[bool, str]:
    command = _resolve_tesseract(environ)
    if command is None:
        return False, "tesseract binary not found"
    try:
        result = subprocess.run([command, "--version"], capture_output=True, text=True,
                                timeout=TESSERACT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError):
        return False, "tesseract binary not runnable"
    lines = (result.stdout or result.stderr).splitlines()
    return result.returncode == 0, lines[0] if lines else "unknown version"


def parse_tesseract_tsv(tsv: str, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
    words: list[Word] = []
    for line in tsv.splitlines()[1:]:
        cells = line.split("\t", 11)
        if len(cells) < 12 or cells[0] != "5":
            continue
        try:
            left, top, width, height, conf = (float(c) for c in cells[6:11])
        except ValueError as error:
            raise ProviderError("tesseract returned malformed TSV") from error
        text = cells[11].strip()
        if conf < 0 or not text:
            continue
        words.append(Word(text, left / scale, top / scale, (left + width) / scale, (top + height) / scale,
                          page_number, conf / 100.0, page_size[0], page_size[1]))
    return words


class TesseractEngine:
    id = "tesseract"
    remote = False
    preferred_dpi = TESSERACT_DPI

    def __init__(self, config: ProviderConfig, environ: Mapping[str, str]) -> None:
        self.id = config.id
        self._lang = config.options.get("lang", "eng")
        self._psm = config.options.get("psm", "6")
        if not TESSERACT_LANG.fullmatch(self._lang) or not TESSERACT_PSM.fullmatch(self._psm):
            raise ConfigError("tesseract lang must be letters, '+' or '_'; psm must be 0-13")
        self._command = _resolve_tesseract(environ, config.options.get("cmd_env", TESSERACT_CMD_ENV))

    def read_page(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        if self._command is None:
            raise ProviderUnavailable("tesseract binary not found; set OPENBOOKS_TESSERACT_CMD or install tesseract")
        try:
            from PIL import Image
        except ImportError as error:
            raise ProviderUnavailable("Pillow is required for tesseract; install 'openbooks[scan]'") from error
        buffer = BytesIO()
        Image.fromarray(image).convert("L").save(buffer, format="PNG", compress_level=1)
        try:
            result = subprocess.run(
                [self._command, "stdin", "stdout", "-l", self._lang, "--psm", self._psm,
                 "--dpi", str(round(scale * 72)), "tsv"],
                input=buffer.getvalue(), capture_output=True, timeout=TESSERACT_TIMEOUT_SECONDS, check=False,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
        except subprocess.TimeoutExpired as error:
            raise ProviderUnavailable("tesseract timed out") from error
        except OSError as error:
            raise ProviderUnavailable(f"tesseract could not start: {type(error).__name__}") from error
        if result.returncode != 0:
            raise ProviderError(f"tesseract exited with code {result.returncode}")
        return parse_tesseract_tsv(result.stdout.decode("utf-8", errors="replace"), scale, page_number, page_size)


_EASYOCR_READERS: dict[bool, Any] = {}
_EASYOCR_LOCK = threading.Lock()


def _easyocr_reader() -> Any:
    try:
        import easyocr
        import torch
    except (ImportError, OSError, RuntimeError) as error:
        raise ProviderUnavailable("Cannot load OCR. Install or repair 'openbooks[scan]'.") from error
    use_gpu = bool(torch.cuda.is_available())
    with _EASYOCR_LOCK:
        if use_gpu not in _EASYOCR_READERS:
            try:
                _EASYOCR_READERS[use_gpu] = easyocr.Reader(["en"], gpu=use_gpu, verbose=False)
            except (OSError, RuntimeError) as error:
                raise ProviderUnavailable("Could not initialize EasyOCR models or the PyTorch runtime.") from error
        return _EASYOCR_READERS[use_gpu]


class EasyOcrEngine:
    id = "easyocr"
    remote = False
    preferred_dpi = EASYOCR_DPI

    def __init__(self, config: ProviderConfig, environ: Mapping[str, str]) -> None:
        self.id = config.id

    def read_page(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        from openbooks.statements.pdf_front import _OCR_AMOUNT, _ocr_fix

        reader = _easyocr_reader()
        pw, ph = page_size
        out: list[Word] = []
        for poly, text, conf in reader.readtext(image, paragraph=False):
            xs, ys = [q[0] / scale for q in poly], [q[1] / scale for q in poly]
            compact = text.replace(" ", "")
            parts = [compact] if _OCR_AMOUNT.match(compact) else text.split()
            total = sum(len(s) for s in parts) or 1
            x, span = min(xs), max(xs) - min(xs)
            for part in parts:
                width = span * len(part) / total
                fixed = _ocr_fix(part)
                out.append(Word(fixed, x, min(ys), x + width, max(ys), page_number, float(conf), pw, ph,
                                part if fixed != part else None))
                x += width
        return out


register_engine("tesseract", TesseractEngine)
register_engine("easyocr", EasyOcrEngine)


def _lookup_factory(engine_name: str) -> EngineFactory:
    if engine_name not in _REGISTRY and engine_name in CLOUD_ENGINES:
        try:
            importlib.import_module("openbooks.statements.ocr_cloud").register_all()
        except ImportError as error:
            raise ProviderUnavailable(f"cloud OCR adapters unavailable for {engine_name}") from error
    factory = _REGISTRY.get(engine_name)
    if factory is None:
        raise ConfigError(f"unknown OCR engine: {engine_name}")
    return factory


def _config_for(settings: ProviderSettings, provider_id: str) -> ProviderConfig:
    config = settings.providers.get(provider_id)
    if config is not None:
        return config
    if provider_id in ("tesseract", "easyocr"):
        return ProviderConfig(provider_id, provider_id, {}, {}, False)
    raise CapabilityRefused(f"unknown OCR provider: {provider_id}")


def _build_engine(settings: ProviderSettings, provider_id: str, environ: Mapping[str, str]) -> OcrEngine:
    config = _config_for(settings, provider_id)
    secrets = [environ.get(name, "") for name in config.env.values()]
    try:
        if (config.remote or config.engine in CLOUD_ENGINES) and not (
                settings.allow_remote and environ.get(ALLOW_REMOTE_ENV) == "1"):
            raise CapabilityRefused(f"remote OCR provider {provider_id} disabled; set {ALLOW_REMOTE_ENV}=1")
        missing = [name for name in config.env.values() if not environ.get(name)]
        if missing:
            raise ProviderUnavailable(f"missing environment variable {missing[0]}")
        return _lookup_factory(config.engine)(config, environ)
    except ConfigError as error:
        raise CapabilityRefused(redact_secrets(str(error), secrets)) from None
    except ProviderError as error:
        raise type(error)(redact_secrets(str(error), secrets)) from None


def select_engine(settings: ProviderSettings, environ: Mapping[str, str] = os.environ) -> OcrEngine:
    provider_id = environ.get(PROVIDER_ENV) or settings.default or "tesseract"
    config = _config_for(settings, provider_id)
    cmd_env = config.options.get("cmd_env", TESSERACT_CMD_ENV)
    if config.engine == "tesseract" and _resolve_tesseract(environ, cmd_env) is None and importlib.util.find_spec("easyocr") is not None:
        return _build_engine(settings, "easyocr", environ)
    return _build_engine(settings, provider_id, environ)


def _env_secrets(settings: ProviderSettings, environ: Mapping[str, str]) -> list[str]:
    names = {name for allowed in ENGINE_ENV_ALLOWLIST.values() for name in allowed}
    names.update(name for config in settings.providers.values() for name in config.env.values())
    return [environ.get(name, "") for name in sorted(names)]


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = environ.get(name) or str(default)
    if not raw.isdigit() or int(raw) < 1:
        raise ConfigError(f"{name} must be a positive integer")
    return int(raw)


_ENGINE_SLOTS: dict[str, threading.BoundedSemaphore] = {}
_ENGINE_SLOTS_LOCK = threading.Lock()


def _engine_slot(engine_id: str, remote: bool, environ: Mapping[str, str]) -> threading.BoundedSemaphore:
    with _ENGINE_SLOTS_LOCK:
        default = DEFAULT_REMOTE_CONCURRENCY if remote else 1
        return _ENGINE_SLOTS.setdefault(engine_id, threading.BoundedSemaphore(_positive_int(environ, CONCURRENCY_ENV, default)))


class OcrSession:
    def __init__(self, settings: ProviderSettings | None = None, environ: Mapping[str, str] = os.environ,
                 deadline_s: float = OCR_DEADLINE_SECONDS) -> None:
        self._environ = environ
        self._settings = settings if settings is not None else load_settings(environ=environ)
        self._secrets = _env_secrets(self._settings, environ)
        self._deadline = time.monotonic() + deadline_s
        self._remote_budget = _positive_int(environ, REMOTE_PAGES_ENV, DEFAULT_REMOTE_PAGES)
        self._engine: OcrEngine | None = None
        self._engine_ids: list[str] = []
        self._pages: list[list[Word]] = []
        self._fallback_used = False
        self._remote_used = False
        self._remote_pages = 0

    @property
    def engine_ids(self) -> tuple[str, ...]:
        return tuple(self._engine_ids)

    @property
    def fallback_used(self) -> bool:
        return self._fallback_used

    @property
    def remote_used(self) -> bool:
        return self._remote_used

    @property
    def run(self) -> OcrRun:
        return OcrRun(self._engine_ids[-1] if self._engine_ids else "", self._fallback_used, list(self._pages))

    def read_page(self, page: PageInput) -> list[Word]:
        if time.monotonic() >= self._deadline:
            raise EngineFault("OCR deadline exceeded")
        if self._engine is None:
            self._select()
        try:
            words = self._read(self._engine, page)
        except CapabilityRefused:
            raise
        except ProviderUnavailable as unavailable:
            fallback_id = self._settings.fallback
            if self._pages or not fallback_id or fallback_id == self._engine.id:
                raise self._fault(unavailable) from unavailable
            words = self._fall_back(fallback_id, page)
        except ProviderError as error:
            raise self._fault(error) from error
        self._pages.append(words)
        return words

    def _select(self) -> None:
        try:
            engine = select_engine(self._settings, self._environ)
        except ProviderUnavailable as error:
            raise self._fault(error) from error
        self._note(engine)

    def _fall_back(self, fallback_id: str, page: PageInput) -> list[Word]:
        self._fallback_used = True
        try:
            self._note(_build_engine(self._settings, fallback_id, self._environ))
            return self._read(self._engine, page)
        except CapabilityRefused:
            raise
        except ProviderError as error:
            raise self._fault(error) from error

    def _note(self, engine: OcrEngine) -> None:
        self._engine = engine
        if engine.id not in self._engine_ids:
            self._engine_ids.append(engine.id)

    def _read(self, engine: OcrEngine, page: PageInput) -> list[Word]:
        if engine.remote:
            self._spend_remote_page()
        with _engine_slot(engine.id, engine.remote, self._environ):
            return read_page_with(engine, page.image, page.scale, page.page_number, page.page_size, self._secrets)

    def _spend_remote_page(self) -> None:
        if self._remote_pages >= self._remote_budget:
            raise CapabilityRefused(f"remote OCR page budget of {self._remote_budget} pages exceeded")
        self._remote_pages += 1
        self._remote_used = True

    def _fault(self, error: ProviderError) -> EngineFault:
        provider = self._engine.id if self._engine is not None else self._settings.default
        hint = ". Install Tesseract or run pip install 'openbooks[scan]'." if isinstance(error, ProviderUnavailable) else ""
        return EngineFault(f"OCR provider {provider} failed: {error}{hint}")


def ocr_pages(pages_iter: Iterable[PageInput], settings: ProviderSettings | None = None,
              environ: Mapping[str, str] = os.environ) -> OcrRun:
    session = OcrSession(settings, environ)
    session._select()
    for page in pages_iter:
        session.read_page(page)
    return session.run
