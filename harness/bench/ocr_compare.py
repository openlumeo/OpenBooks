from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import random
import re
import sys
import time
import tomllib
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from bench.runner import redact, redact_tree
from bench.score import _to_decimal

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "data" / "raw" / "agami_indian_bank_statements" / "train"
DEFAULT_OUT = ROOT / "out" / "ocr-compare"
DEFAULT_SETTINGS = ROOT / "harness" / "openbooks.providers.toml"
SCHEMA = "ocr-compare.v1"
SCANNED_MARK = "scanned"
FIELD_COUNT = 3
REMOTE_ENV = "OPENBOOKS_ALLOW_REMOTE_OCR"
MAX_REMOTE_PAGES = 20
CLOUD_ENGINES = frozenset({"azure_docintel", "google_docai", "aws_textract", "mistral_ocr", "llamaparse"})
SECRET_SHAPE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|xai-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ya29\.[0-9A-Za-z_-]{20,}|eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}|[0-9a-f]{32,}")
PAGE_MARKER = re.compile(rb"/Type\s*/Page(?!s)")
HEADER = "| Provider | Status | Docs | Release acc | Field acc | Wrong releases | p50 s | p95 s | Pages | Est. cost USD | Refusals / notes |"


@dataclass(frozen=True)
class Figures:
    opening: Decimal | None
    closing: Decimal | None
    currency: str | None


@dataclass(frozen=True)
class Sample:
    name: str
    path: Path
    label: Figures
    pages: int


@dataclass(frozen=True)
class Extraction:
    status: str
    code: str | None = None
    figures: Figures | None = None
    engines: tuple[str, ...] = ()
    fallback: bool = False
    remote: bool = False


@dataclass(frozen=True)
class Observation:
    name: str
    extraction: Extraction
    latencies: tuple[float, ...]
    pages: int


@dataclass(frozen=True)
class ProviderRun:
    provider_id: str
    status: str
    reason: str | None
    observations: tuple[Observation, ...]
    price_per_page: float | None
    remote: bool


@dataclass(frozen=True)
class RunScores:
    provider_id: str
    status: str
    reason: str | None
    documents: int
    release_accuracy: float | None
    field_accuracy: float | None
    wrong_release_count: int
    refusal_codes: dict[str, int]
    p50_s: float | None
    p95_s: float | None
    pages: int
    est_cost_usd: float | None


def _currency(value: Any) -> str | None:
    return value.strip().upper() if isinstance(value, str) and value.strip() else None


def load_sample(pdf: Path) -> Sample | None:
    raw = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    label = Figures(_to_decimal(raw.get("opening_balance")), _to_decimal(raw.get("closing_balance")), _currency(raw.get("currency")))
    if label.opening is None or label.closing is None or label.currency is None:
        return None
    pages = len(PAGE_MARKER.findall(pdf.read_bytes()))
    return Sample(f"{pdf.parent.name}/{pdf.stem}", pdf, label, pages)


def list_samples(fixtures: Path, limit: int, seed: int) -> list[Sample]:
    pdfs = sorted(p for p in fixtures.rglob("*.pdf") if p.with_suffix(".json").is_file())
    pool = [p for p in pdfs if SCANNED_MARK in p.parent.name.lower()] or pdfs
    chosen = sorted(random.Random(seed).sample(pool, min(limit, len(pool))))
    return [sample for sample in map(load_sample, chosen) if sample is not None]


def extract_with_pipeline(sample: Sample) -> Extraction:
    from openbooks.core import Params
    from openbooks.core.errors import Refusal
    from openbooks.statements import pdf_front

    try:
        data, *_ = pdf_front.extract_document(sample.path, Params())
        batch = data["batches"][0]
        figures = Figures(_to_decimal(batch["opening"]["amount"]), _to_decimal(batch["closing"]["amount"]), _currency(batch.get("currency")))
        result = Extraction("released", None, figures)
    except Refusal as refusal:
        result = Extraction("refused", refusal.code)
    except Exception as error:
        result = Extraction("error", type(error).__name__)
    session = pdf_front.last_ocr_run()
    engines = tuple(pdf_front.last_ocr_engines())
    return replace(result, engines=engines, fallback=bool(session and session.fallback_used), remote=bool(session and session.remote_used))


def observe(samples: Sequence[Sample], extract: Callable[[Sample], Extraction], repeats: int) -> tuple[Observation, ...]:
    observations = []
    for sample in samples:
        attempts = []
        for _ in range(max(1, repeats)):
            started = time.perf_counter()
            attempts.append((extract(sample), time.perf_counter() - started))
        latencies = tuple(round(elapsed, 4) for index, (_, elapsed) in enumerate(attempts) if repeats == 1 or index > 0)
        observations.append(Observation(sample.name, attempts[0][0], latencies, sample.pages))
    return tuple(observations)


def preflight(provider_id: str, settings_path: Path | None) -> tuple[str, bool, str | None]:
    from openbooks.core.errors import EngineFault
    from openbooks.statements import ocr_providers, pdf_front

    if not (hasattr(pdf_front, "last_ocr_run") and hasattr(pdf_front, "last_ocr_engines")):
        return "", False, "pipeline does not route OCR through ocr_providers yet"
    try:
        settings = ocr_providers.load_settings(settings_path)
        engine = ocr_providers.select_engine(settings)
    except (ocr_providers.ProviderError, ocr_providers.ConfigError, EngineFault) as error:
        return "", False, str(error)
    config = settings.providers.get(provider_id)
    expected = config.engine if config is not None else provider_id
    if engine.id != expected:
        return expected, False, f"resolved to {engine.id}; fallback is disabled in benchmarks"
    remote = bool(engine.remote or (config is not None and config.remote) or expected in CLOUD_ENGINES)
    return expected, remote, None


@contextlib.contextmanager
def provider_environment(provider_id: str, settings_path: Path | None) -> Iterator[None]:
    from openbooks.statements.ocr_providers import PROVIDER_ENV, PROVIDERS_FILE_ENV

    overrides = {PROVIDER_ENV: provider_id}
    if settings_path is not None:
        overrides[PROVIDERS_FILE_ENV] = str(settings_path)
    saved = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def remote_block(remote: bool, allow_flag: bool, environ: Mapping[str, str]) -> str | None:
    if remote and not (allow_flag and environ.get(REMOTE_ENV) == "1"):
        return f"remote provider disabled; needs --allow-remote and {REMOTE_ENV}=1"
    return None


def remote_page_block(samples: Sequence[Sample], limit: int) -> str | None:
    pages = sum(sample.pages for sample in samples)
    return f"{pages} pages exceed --max-remote-pages {limit}" if pages > limit else None


def mislabel_reason(observations: Sequence[Observation], expected: str) -> str | None:
    mixed = any(o.extraction.fallback or any(e != expected for e in o.extraction.engines) for o in observations)
    return f"engines used differ from requested {expected} (fallback or other engine); not scored" if mixed else None


def run_provider(provider_id: str, samples: Sequence[Sample], settings_path: Path | None, repeats: int, allow_remote: bool, max_pages: int, price_per_page: float | None) -> ProviderRun:
    with provider_environment(provider_id, settings_path):
        expected, remote_hint, reason = preflight(provider_id, settings_path)
        if reason is None and remote_hint:
            reason = remote_block(True, allow_remote, os.environ) or remote_page_block(samples, max_pages)
        if reason is not None:
            return ProviderRun(provider_id, "skipped", reason, (), price_per_page, False)
        if remote_hint:
            sys.stderr.write(f"privacy notice: {provider_id} is a remote OCR provider; {sum(s.pages for s in samples)} page(s) will be sent to it\n")
        observations = observe(samples, extract_with_pipeline, repeats)
    remote = any(o.extraction.remote for o in observations)
    reason = mislabel_reason(observations, expected) or remote_block(remote, allow_remote, os.environ)
    if reason is not None:
        return ProviderRun(provider_id, "skipped", reason, (), price_per_page, False)
    return ProviderRun(provider_id, "ok", None, observations, price_per_page, remote)


def field_matches(actual: Figures | None, label: Figures) -> int:
    if actual is None:
        return 0
    pairs = ((actual.opening, label.opening), (actual.closing, label.closing), (actual.currency, label.currency))
    return sum(1 for got, want in pairs if got is not None and got == want)


def percentile(values: Sequence[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(1, math.ceil(share * len(ordered))) - 1], 3)


def score_run(run: ProviderRun, expected: Mapping[str, Figures]) -> RunScores:
    if run.status != "ok":
        return RunScores(run.provider_id, run.status, run.reason, 0, None, None, 0, {}, None, None, 0, None)
    released = [o for o in run.observations if o.extraction.status == "released"]
    matched = [field_matches(o.extraction.figures, expected[o.name]) for o in released]
    correct = sum(1 for count in matched if count == FIELD_COUNT)
    documents = len(run.observations)
    refusals = Counter(
        o.extraction.code if o.extraction.status == "refused" else f"error:{o.extraction.code}"
        for o in run.observations
        if o.extraction.status != "released"
    )
    latencies = [value for o in run.observations for value in o.latencies]
    pages = sum(o.pages for o in run.observations)
    cost = (None if run.price_per_page is None else round(pages * run.price_per_page, 4)) if run.remote else 0.0
    return RunScores(
        provider_id=run.provider_id,
        status="ok",
        reason=None,
        documents=documents,
        release_accuracy=correct / documents if documents else None,
        field_accuracy=sum(matched) / (FIELD_COUNT * len(released)) if released else None,
        wrong_release_count=len(released) - correct,
        refusal_codes=dict(refusals),
        p50_s=percentile(latencies, 0.5),
        p95_s=percentile(latencies, 0.95),
        pages=pages,
        est_cost_usd=cost,
    )


def _show(value: float | None, template: str) -> str:
    return "n/a" if value is None else template.format(value)


def render_table(results: Sequence[RunScores]) -> str:
    rows = [HEADER, "|" + "---|" * 11]
    for score in results:
        notes = score.reason or "" if score.status != "ok" else ", ".join(f"{code} x{count}" for code, count in sorted(score.refusal_codes.items())) or "-"
        cells = [
            score.provider_id,
            score.status,
            str(score.documents),
            _show(score.release_accuracy, "{:.1%}"),
            _show(score.field_accuracy, "{:.1%}"),
            str(score.wrong_release_count),
            _show(score.p50_s, "{:.3f}"),
            _show(score.p95_s, "{:.3f}"),
            str(score.pages),
            _show(score.est_cost_usd, "{:.4f}"),
            notes,
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def build_payload(meta: Mapping[str, Any], samples: Sequence[Sample], runs: Sequence[ProviderRun], scores: Sequence[RunScores]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": dict(meta),
        "documents": [sample.name for sample in samples],
        "providers": [asdict(score) for score in scores],
        "observations": {
            run.provider_id: [
                {"name": o.name, "status": o.extraction.status, "code": o.extraction.code, "latencies_s": list(o.latencies), "pages": o.pages}
                for o in run.observations
            ]
            for run in runs
        },
    }


def scan_for_keys(text: str, secrets: Sequence[str] = ()) -> None:
    if SECRET_SHAPE.search(text):
        raise ValueError("key-shaped string in result; write aborted")
    if any(value in text for value in secrets):
        raise ValueError("secret value in result; write aborted")


def write_payload(payload: Mapping[str, Any], out_dir: Path, secrets: Sequence[str]) -> Path:
    text = json.dumps(redact_tree(dict(payload), list(secrets)), indent=2, sort_keys=True)
    scan_for_keys(text, secrets)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{SCHEMA}.json"
    target.write_text(text + "\n", encoding="utf-8")
    return target


def load_prices(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("prices file must map provider id to USD per page")
    return {str(key): float(value) for key, value in raw.items()}


def secret_env_names(settings_path: Path | None) -> list[str]:
    names = {"AWS_SESSION_TOKEN"}
    with contextlib.suppress(ImportError):
        from openbooks.statements import ocr_providers
        names |= set(getattr(ocr_providers, "ENV_ALLOWLIST", ()))
    for path in (DEFAULT_SETTINGS, settings_path):
        if path is not None:
            providers = tomllib.loads(path.read_text(encoding="utf-8")).get("providers", {})
            names |= {name for table in providers.values() for name in table.get("env", {}).values()}
    return sorted(names)


def secret_values(settings_path: Path | None, environ: Mapping[str, str]) -> list[str]:
    return [environ[name] for name in secret_env_names(settings_path) if environ.get(name)]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m bench.ocr_compare")
    parser.add_argument("--providers", default="tesseract,easyocr")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--settings", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--prices", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--max-remote-pages", type=int, default=MAX_REMOTE_PAGES)
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_check:
        return self_check()
    providers = [item.strip() for item in args.providers.split(",") if item.strip()]
    try:
        secrets = secret_values(args.settings, os.environ)
        prices = load_prices(args.prices)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"configuration error: {type(error).__name__}\n")
        return 2
    samples = list_samples(args.fixtures, args.limit, args.seed)
    if not samples:
        sys.stderr.write("no labelled PDFs found in the fixtures directory\n")
        return 2
    expected = {sample.name: sample.label for sample in samples}
    runs = [run_provider(pid, samples, args.settings, args.repeats, args.allow_remote, args.max_remote_pages, prices.get(pid)) for pid in providers]
    scores = [score_run(run, expected) for run in runs]
    meta = {"fixtures": args.fixtures.name, "limit": args.limit, "seed": args.seed, "repeats": args.repeats}
    try:
        target = write_payload(build_payload(meta, samples, runs, scores), args.out, secrets)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"{error}\n")
        return 2
    sys.stdout.write(redact(render_table(scores), secrets) + "\n")
    sys.stdout.write(f"wrote {target.name}\n")
    return 0


FAKE_SECRET = "sk-selfcheck" + "0" * 24
FAKE_ENV_VALUE = "selfcheck-azure-key-" + "0" * 12


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run_self_check() -> None:
    label = Figures(Decimal("100.00"), Decimal("80.50"), "INR")
    samples = [Sample(f"fake/{index:05d}", Path(f"fake/{index:05d}.pdf"), label, 2) for index in range(1, 5)]
    expected = {sample.name: sample.label for sample in samples}
    outcomes = {
        "fake/00001": Extraction("released", None, label),
        "fake/00002": Extraction("released", None, Figures(Decimal("100.00"), Decimal("80.05"), "INR")),
        "fake/00003": Extraction("refused", "LOW_CONFIDENCE"),
        "fake/00004": Extraction("released", None, label),
    }
    fake = ProviderRun("fake", "ok", None, observe(samples, lambda s: outcomes[s.name], 2), 0.001, False)
    score = score_run(fake, expected)
    _expect(score.documents == 4 and score.wrong_release_count == 1, "counts and wrong release")
    _expect(score.release_accuracy == 0.5, "release accuracy")
    _expect(score.field_accuracy is not None and abs(score.field_accuracy - 8 / 9) < 1e-9, "field accuracy")
    _expect(score.refusal_codes == {"LOW_CONFIDENCE": 1}, "refusal codes")
    _expect(score.est_cost_usd == 0.0 and score.pages == 8, "local cost and pages")
    _expect(score.p50_s is not None and score.p95_s is not None, "latency")
    remote = score_run(ProviderRun("remote", "ok", None, fake.observations, 0.5, True), expected)
    _expect(remote.est_cost_usd == 4.0, "remote cost from price table")
    skipped = score_run(ProviderRun("azure", "skipped", "remote provider disabled", (), 0.5, True), expected)
    _expect(skipped.status == "skipped" and skipped.wrong_release_count == 0, "skipped is not failed")
    _expect("remote provider disabled" in render_table([score, skipped]), "table content")
    for engines, fallback, scored in ((("easyocr",), False, False), (("tesseract",), False, True), (("tesseract",), True, False)):
        observed = observe(samples[:1], lambda s: Extraction("released", None, label, engines, fallback), 1)
        _expect((mislabel_reason(observed, "tesseract") is None) == scored, f"mislabel {engines} fallback={fallback}")
    _expect(remote_block(True, True, {REMOTE_ENV: "1"}) is None, "remote allowed with flag and env")
    _expect(remote_block(True, False, {REMOTE_ENV: "1"}) is not None, "remote needs --allow-remote")
    _expect(remote_block(True, True, {}) is not None, "remote needs env")
    _expect(remote_block(False, False, {}) is None, "local runs are not gated")
    _expect(remote_page_block(samples, 8) is None and remote_page_block(samples, 7) is not None, "remote page cap")
    names = secret_env_names(None)
    _expect("AZURE_DOCINTEL_KEY" in names and "AWS_SESSION_TOKEN" in names, "allowlisted secret names")
    secrets = secret_values(None, {"AZURE_DOCINTEL_KEY": FAKE_ENV_VALUE, "AWS_SESSION_TOKEN": "token-selfcheck"})
    _expect(FAKE_ENV_VALUE in secrets and "token-selfcheck" in secrets, "secret values collected")
    text = json.dumps(redact_tree(build_payload({"fixtures": "fake"}, samples, [fake], [score]), [FAKE_SECRET]), sort_keys=True)
    scan_for_keys(text, secrets)
    for leaked in (json.dumps({"reason": f"leak {FAKE_ENV_VALUE}"}), json.dumps({"reason": FAKE_SECRET})):
        try:
            scan_for_keys(leaked, secrets)
        except ValueError:
            continue
        raise AssertionError("leaked value not refused")


def self_check() -> int:
    try:
        _run_self_check()
    except AssertionError as error:
        sys.stderr.write(f"self-check failed: {error}\n")
        return 1
    sys.stdout.write("self-check ok\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
