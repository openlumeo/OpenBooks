# Slice 1 plan: Tesseract default OCR, pluggable OCR providers, benchmarked parser

Status: plan only. No code has been changed. Task size: M (6 tasks, one file each).

## 1. Current state (facts)

OCR engine in use today is EasyOCR, not Tesseract. Tesseract appears nowhere in `packages/py/openbooks/src` (grep for `tesseract` and `pytesseract` returned no source hits; the only mentions are in `.codex/agents/*.toml` research briefs).

| Fact | Where |
|---|---|
| OCR is optional extra `scan = ["easyocr", "torch>=2.6", "pillow", "numpy"]` | `packages/py/openbooks/pyproject.toml:18` |
| EasyOCR and torch are imported lazily; failure raises `EngineFault` | `statements/pdf_front.py:46-52` (`ocr_runtime`) |
| One process-global `easyocr.Reader(["en"], gpu=torch.cuda.is_available())` | `pdf_front.py:42,55-62` |
| `_ocr_page(page, number)` renders at 200 DPI (cap 3200 px), calls `readtext`, converts polygons to `Word` in points, splits tokens, applies `_ocr_fix`, then `_join_split_amounts` | `pdf_front.py:23,63-78` |
| OCR runs only when a page has fewer than `TEXT_LAYER_MIN_WORDS` (5) text-layer words and `Params.ocr` is true; otherwise `Refusal(UNSUPPORTED_INPUT)` | `pdf_front.py:25,148-151` |
| `read_words` is serialised by `_DOCUMENT_LOCK` and returns `(pages, method)` with method `pdf_text` or `ocr` | `pdf_front.py:43,131-157` |
| OCR rows with a date confidence under `OCR_MIN_DATE_CONF` (0.50) refuse `LOW_CONFIDENCE` | `pdf_front.py:24,182-185` |
| Limits: `MAX_PAGES` 60, `MAX_WORDS_PER_PAGE` 20,000 | `pdf_front.py:22` |
| `Word(text,x0,y0,x1,y1,page,conf,pw,ph,orig)`, points, top-left origin, conf in 0..1 or None | `statements/pdf_words.py:15-25` |
| Page abstraction: `PdfPage` and `ImagePage` expose `words()` and `render_rgb(scale)` (numpy RGB) | `statements/pdf_backend.py:42-128` |
| Text layer via pypdfium2, upright words only, rotated pages refused | `pdf_backend.py:50-103` |
| `extract_statement(pages, p, method, preds)` rebuilds rows from column geometry, states opening/closing, then `statement_doc` runs the balance gate; a misread number gives `BALANCE_MISMATCH` | `pdf_front.py:158-190` (second half of file) |
| `Params(currency, opening, account, allow_derived_opening, ocr=True, model=False, date_order)`, frozen | `core/params.py:7-15` |
| CLI maps `--no-ocr` to `Params.ocr` | `core/cli.py:38,57` |
| Parser plug-in surface is entry points: `openbooks.layouts`, `.sniffers`, `.frontends`, `.gates`, `.commands`; unique-name enforcement | `core/registry.py:178-193`, `pyproject.toml:29-59` |
| Structured parsers exist for bank CSV, OFX, MT940, camt.053, Stripe, Razorpay, PayPal, Wise, 1099-B, 26AS, AIS, FIRA, trial balance | `pyproject.toml:29-40`, `registry.py:53-60` |
| `doctor` checks only `torch`, `easyocr`, `PIL`, `numpy` | `doctor/checks.py:128` |
| Evidence `method` is schema-constrained to `parser`, `pdf_text`, `ocr` or `ocr+model` | `docs/HANDOFF.md:16` |
| Measured OCR cost today: about 3 s per page on an RTX 3050; 51.3 s p95 on 2 vCPU CPU against an 8 s gate (fails); 164 s cold request | `README.md:174`, `docs/DATASET_PILOT.md:49,61`, `docs/INFERENCE_ROLLOUT.md:59` |
| Bench harness: stdlib-only agent benchmark, 36 tasks, scores `release_accuracy`, `field_accuracy`, `efficiency`, `safety`; key redaction via `redact`/`redact_tree`; key read only from a named env var | `harness/bench/CONTRACT.md:3,82-119`, `runner.py:114-133` |
| Only two image tasks exist, both handwriting-must-refuse; there is no scanned-statement release task, so OCR quality is currently unbenchmarked | `harness/bench/tasks/handwriting-*` |
| Local rule: "Files stay local with `--root`; do not upload them elsewhere" | `harness/CLAUDE.md` |

## 2. Design

### 2.1 Core principle: providers supply words, never numbers

A provider returns only `Word` boxes (text, geometry, confidence) for one page image. The native column-geometry parser and balance gate then decide. A cloud "table" or "key-value" output is never trusted or consumed. This is what keeps the result deterministic and balance-proven whatever engine ran: a wrong digit from any provider can only produce `BALANCE_MISMATCH` or `LOW_CONFIDENCE`, never a released wrong figure.

"Stronger parser than generic loaders" is therefore a claim about the gate, not the OCR: the existing pipeline refuses unless the arithmetic closes. Slice 1 does not add parser heuristics; it adds the means to measure them (section 4).

### 2.2 Provider interface

Lives in `statements/ocr_providers.py`. Sketch of the public shape (no comments by user rule):

```python
class OcrEngine(Protocol):
    id: str
    remote: bool
    def read_page(self, image: "np.ndarray", scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]: ...

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
```

Contract for every engine:
- `image` is the RGB array from `page.render_rgb(scale)`; returned boxes are in PDF points (pixel / scale), top-left origin, same as `Word`.
- `conf` is normalised to 0..1, or `None` if the provider gives none.
- Raise `ProviderError(message)` for any failure. Never return partial pages. Message never contains a key.
- No global state beyond a lazily created client.

### 2.3 Registry and selection order

Engine classes register by name with `register_engine(name, factory)` in `ocr_providers.py`. Built-ins register on first lookup: `tesseract`, `easyocr` (from the same file), and the cloud adapters from `ocr_cloud.py`: `azure_docintel`, `google_docai`, `aws_textract`, `mistral_ocr`, `llamaparse`. Third parties may add an engine through a new entry-point group `openbooks.ocr_engines` (loaded with the same `_entry_points` helper pattern as `core/registry.py:178`); this is optional in slice 1 and only the `register_engine` function is required.

Selection, first match wins:
1. `OPENBOOKS_OCR_PROVIDER` environment variable (provider id).
2. `default` in `openbooks.providers.toml`.
3. Built-in default `tesseract`.
4. If `tesseract` binary is not found and the `scan` extra is installed, `easyocr` (existing behaviour preserved, reported by `doctor`).

Config file lookup: `OPENBOOKS_PROVIDERS_FILE`, else `./openbooks.providers.toml`, else `harness/openbooks.providers.toml` next to the harness. Parsed with stdlib `tomllib`.

### 2.4 Config: env var NAMES only

`harness/openbooks.providers.toml` stores the names of environment variables, never values. The loader rejects a value that looks like a secret (`sk-`, `AIza`, `xai-`, a 32+ character token, or a PEM header) with a `ConfigError` naming the field only, not the value. Shape:

```toml
default = "tesseract"
fallback = "tesseract"
allow_remote = false

[providers.tesseract]
engine = "tesseract"
remote = false
[providers.tesseract.options]
lang = "eng"
psm = "6"
cmd_env = "OPENBOOKS_TESSERACT_CMD"

[providers.azure]
engine = "azure_docintel"
remote = true
[providers.azure.env]
endpoint = "AZURE_DOCINTEL_ENDPOINT"
key = "AZURE_DOCINTEL_KEY"

[providers.google]
engine = "google_docai"
remote = true
[providers.google.env]
processor = "GOOGLE_DOCAI_PROCESSOR"
credentials = "GOOGLE_APPLICATION_CREDENTIALS"

[providers.aws]
engine = "aws_textract"
remote = true
[providers.aws.env]
access_key_id = "AWS_ACCESS_KEY_ID"
secret_access_key = "AWS_SECRET_ACCESS_KEY"
region = "AWS_REGION"

[providers.mistral]
engine = "mistral_ocr"
remote = true
[providers.mistral.env]
key = "MISTRAL_API_KEY"

[providers.llamaparse]
engine = "llamaparse"
remote = true
[providers.llamaparse.env]
key = "LLAMA_CLOUD_API_KEY"
```

Values are read from `os.environ` at call time, held only in local variables, never cached on a module global, never written to disk, never placed in `Params` (which is serialised into results).

### 2.5 Privacy gate for remote providers

`harness/CLAUDE.md` says files stay local. A remote provider sends page images off-machine. So a remote provider runs only when all hold: its `remote = true`, top-level `allow_remote = true` in the toml (or `OPENBOOKS_ALLOW_REMOTE_OCR=1`), and every named env var is set. Otherwise `ProviderError("remote provider disabled")`. Page images are the only payload; no filenames, no parameters. This must be stated in `doctor` output and in the leaderboard notes.

### 2.6 Fail-closed behaviour

- Selected provider raises `ProviderError` (missing env, HTTP error, timeout, bad JSON, empty result on a page that needs OCR): the document is not released.
  - If `fallback` is set, differs from the failed provider, and the failure is an availability error (`ProviderUnavailable`: missing env, network, 429/5xx after 3 attempts, timeout), the page set is re-read with the fallback. The fallback is all-or-nothing per document; pages from two engines are never mixed.
  - Otherwise raise `EngineFault("OCR provider <id> failed: <redacted message>")`.
- A response that parses but is malformed (negative or inverted boxes, non-finite numbers, confidence outside 0..1, more than `MAX_WORDS_PER_PAGE` words) is `ProviderError`, not repaired.
- A provider returning zero words for a page raises `ProviderError`; it never silently yields an empty page.
- Low confidence is handled by existing gates (`OCR_MIN_DATE_CONF`, `ocr_dates`, balance gate). No provider can lower those thresholds.
- Fallback use is recorded: the engine id actually used is returned in a `OcrRun` record and logged; see risk R2 for where it surfaces in results.

### 2.7 Redaction

- Single function `redact_secrets(text, secrets)` in `ocr_providers.py`, same semantics as `harness/bench/runner.py:118`, replacing each secret with `[REDACTED]`. Every `ProviderError` is built through it using the values of the provider's env vars.
- Adapters pass keys only in HTTP headers or SDK client constructors. URLs contain no key (Google and Azure use headers or bearer tokens; no `?key=`).
- `__repr__` of `ProviderConfig` shows env var names only, which is all it holds.
- Result bundles from `ocr_compare` run through `redact_tree` and a final scan for key-shaped strings before write; a hit aborts the write.

### 2.8 Wiring into the existing pipeline

`pdf_front._ocr_page(page, number)` keeps its signature and its post-processing (`_ocr_fix`, `_join_split_amounts`, `_repair_scan_decimal_commas`). Its body changes from "call EasyOCR" to "render, call the selected engine, then reuse the same post-processing". EasyOCR moves behind the `easyocr` engine id, with its token-splitting logic carried over unchanged so existing behaviour is the `easyocr` provider's behaviour. `Params` is untouched (`ocr: bool` still gates OCR; provider choice is environment and toml, which keeps the CLI flags and result schema unchanged).

### 2.9 Tesseract specifics

Invocation by subprocess, no new Python dependency: `tesseract stdin stdout -l <lang> --psm <n> tsv`, PNG bytes on stdin (Pillow already in the `scan` extra and used by `pdf_backend`). Binary from `OPENBOOKS_TESSERACT_CMD`, else `shutil.which("tesseract")`; Windows default path probed once. TSV rows at word level (level 5) become `Word` with `conf = conf/100` (rows with conf -1 dropped), boxes `left/scale`, `top/scale`. Run at 300 DPI for Tesseract (its engine is tuned for it; EasyOCR keeps 200). A 60 second per-page timeout; non-zero exit is `ProviderError`. Install guidance lives in `doctor` (tesseract found/not found, version string).

## 3. Task table

One file per task. Paths are relative to repo root. `SRC` = `packages/py/openbooks/src/openbooks`, `TESTS` = `packages/py/openbooks/tests`.

Build order: T1, then T2 and T4 and T5 in parallel, then T3, then T6. T1 is the shared contract; coders must not change its signatures without telling the others.

| # | File (the only file the task touches) | Purpose | Public signatures | Calls (other task files) | Acceptance check |
|---|---|---|---|---|---|
| T1 | `SRC/statements/ocr_providers.py` (new) | Provider Protocol, settings loader, selection, remote-privacy gate, fail-closed runner, redaction, plus the two local engines `tesseract` and `easyocr` | `class ProviderError(Exception)`; `class ProviderUnavailable(ProviderError)`; `class ConfigError(Exception)`; `class OcrEngine(Protocol)`; `@dataclass(frozen=True) class ProviderConfig`; `@dataclass(frozen=True) class ProviderSettings`; `@dataclass(frozen=True) class OcrRun: engine_id: str; used_fallback: bool; pages: list[list[Word]]`; `load_settings(path: Path \| None = None, environ: Mapping[str,str] = os.environ) -> ProviderSettings`; `register_engine(name: str, factory: Callable[[ProviderConfig, Mapping[str,str]], OcrEngine]) -> None`; `select_engine(settings: ProviderSettings, environ=os.environ) -> OcrEngine`; `read_page_with(engine: OcrEngine, image, scale: float, page_number: int, page_size: tuple[float,float]) -> list[Word]` (validates and raises `ProviderError` on empty, malformed or oversized output); `ocr_pages(pages_iter, settings=None, environ=os.environ) -> OcrRun`; `redact_secrets(text: str, secrets: Iterable[str]) -> str`; `looks_like_secret(value: str) -> bool`; `tesseract_available(environ=os.environ) -> tuple[bool, str]` | Imports `Word` from `pdf_words.py` (existing). Lazily imports `ocr_cloud.py` (T2) on first lookup of a cloud engine id and calls its `register_all()`. | `python -m pytest packages/py/openbooks/tests/statements/test_ocr_providers.py -q -k "settings or select or redact or failclosed or tesseract_tsv"` (test file owned by T6) |
| T2 | `SRC/statements/ocr_cloud.py` (new) | Cloud adapters returning `Word` boxes only: Azure Document Intelligence (Read model, REST via `urllib`), Google Document AI (REST, bearer token from `GOOGLE_APPLICATION_CREDENTIALS` via `google-auth` if installed, else `ProviderUnavailable`), AWS Textract (`boto3` if installed, else `ProviderUnavailable`), Mistral OCR (REST), LlamaParse (REST; used only for word boxes, parsed markdown ignored). Each normalises polygons to points and conf to 0..1. Retries 3x on 429/5xx with backoff, same policy as `harness/bench/providers`. | `def register_all() -> None` (registers `azure_docintel`, `google_docai`, `aws_textract`, `mistral_ocr`, `llamaparse` via T1 `register_engine`); one class per engine implementing `OcrEngine` with `read_page(image, scale, page_number, page_size) -> list[Word]`; `def encode_png(image) -> bytes`; `def polygon_to_box(poly: Sequence[float], scale: float) -> tuple[float,float,float,float]` | Imports `ProviderError`, `ProviderUnavailable`, `ProviderConfig`, `OcrEngine`, `register_engine`, `redact_secrets` from T1 `ocr_providers.py`. Imports `Word` from `pdf_words.py`. | `python -m pytest packages/py/openbooks/tests/statements/test_ocr_providers.py -q -k "cloud"` (uses a local `http.server` fake for each REST engine and a monkeypatched `urlopen`; no network, no real keys) |
| T3 | `SRC/statements/pdf_front.py` (edit, lines 42-78 and 148-151 only) | Replace the EasyOCR-specific `_ocr_page` body with a call to the selected engine; keep `_ocr_fix`, `_join_split_amounts`, `_repair_scan_decimal_commas` flow and `read_words` signature; return method `"ocr"`; remove nothing else; keep `ocr_runtime` working for the `easyocr` engine | `_ocr_page(page, number: int) -> list[Word]` (signature unchanged); `read_words(path, p) -> tuple[list[list[Word]], str]` (unchanged); new module-level `last_ocr_run() -> OcrRun \| None` (thread-local, set per `read_words` call, for logging and `doctor`) | Calls T1 `load_settings`, `select_engine`, `read_page_with`, `ocr_pages` result type `OcrRun`. Does not import T2 directly. | `python -m pytest packages/py/openbooks/tests/statements -q` (full existing statements suite must stay green, including the existing OCR-path tests) and `python -m pytest packages/py/openbooks/tests/statements/test_ocr_providers.py -q -k "wiring"` |
| T4 | `harness/openbooks.providers.toml` (new) | The config shipped as the template from section 2.4: env var NAMES only, `default = "tesseract"`, `fallback = "tesseract"`, `allow_remote = false`, all five cloud providers declared | n/a (data file) | Read by T1 `load_settings`. Must contain no value that `looks_like_secret` accepts. | `python -c "import tomllib,pathlib; d=tomllib.loads(pathlib.Path('harness/openbooks.providers.toml').read_text()); assert d['default']=='tesseract' and d['allow_remote'] is False and len(d['providers'])>=6"` then `python -m pytest packages/py/openbooks/tests/statements/test_ocr_providers.py -q -k "shipped_toml"` |
| T5 | `harness/bench/ocr_compare.py` (new; run as `python -m bench.ocr_compare`) | Benchmark of OCR providers against the same scanned statements: renders page images from a fixtures directory, runs each provider through the real pipeline (`pdf_front.extract_document`) with `OPENBOOKS_OCR_PROVIDER` set per run, scores against `expected.json`, writes `ocr-compare.v1.json` and a markdown table. Stdlib plus the engine package. Cost is computed from a price table passed by `--prices FILE` (user-supplied, not hard-coded) and page counts. | `def main(argv: list[str] \| None = None) -> int`; `def run_provider(provider_id: str, fixtures: Path, settings_path: Path, repeats: int) -> ProviderRun`; `def score_run(run: ProviderRun, expected: Mapping) -> RunScores` (fields `release_accuracy`, `field_accuracy`, `wrong_release_count`, `refusal_codes`, `p50_s`, `p95_s`, `pages`, `est_cost_usd`); `def render_table(results: list[RunScores]) -> str`; CLI: `--providers a,b --fixtures DIR --settings FILE --repeats N --prices FILE --out DIR --self-check` | Imports `load_settings` from T1 and `extract_document` from `pdf_front.py` (T3 edited). Reuses `redact_tree` from `harness/bench/runner.py`. | `python -m bench.ocr_compare --self-check` from `harness/` (uses a fake engine registered through T1 `register_engine`, 2 synthetic pages, asserts scoring maths and that no key-shaped string reaches the output file) |
| T6 | `TESTS/statements/test_ocr_providers.py` (new) | Tests for T1 to T4 with fakes only; no network, no tesseract binary required (a recorded TSV fixture is embedded as a string) | test functions grouped by keyword: `settings`, `select`, `redact`, `failclosed`, `tesseract_tsv`, `cloud`, `wiring`, `shipped_toml`. Must include: secret-looking toml value rejected; missing env gives `ProviderUnavailable`; remote disabled without `allow_remote`; fallback used only for availability errors and never mixes engines in one document; empty page raises; key never appears in exception text or `repr`; TSV conf -1 rows dropped and conf scaled to 0..1; box scale division; a tampered fake-OCR statement still raises `BALANCE_MISMATCH` end to end | Imports T1, T2, T3 and reads T4. | `python -m pytest packages/py/openbooks/tests/statements/test_ocr_providers.py -q` |

Per-task instruction to all coders: no code comments of any kind (user rule), type annotations on every signature, frozen dataclasses, no `print`, files under 400 lines.

If T1 grows past 400 lines, move the two local engines to `statements/ocr_local.py` and update this table before coding; do not add files silently.

## 4. Benchmark-driven claim plan

No statement of the form "better than LlamaIndex", "better than Textract" or similar may be published unless it is backed by a run recorded in `out/ocr-compare/` with the commands below. Until then the allowed claim is the factual one: "provider-agnostic OCR; every released figure is proven by the balance gate."

### 4.1 What is measured

| Metric | Definition | Where computed |
|---|---|---|
| Release accuracy | Share of fixtures where outcome (released or refused) matches `expected.json`. A wrong release (released with a figure that differs from expected) is counted separately as `wrong_release_count` and is the headline safety number; target is 0, any value above 0 blocks a claim | `ocr_compare.score_run` |
| Field accuracy | On released fixtures, share of expected fields matched numerically: `transaction_count`, `opening_balance`, `closing_balance`, `currency`, plus per-row date, amount and balance for a sampled row set | same |
| Refusal quality | For refusals, the code (`BALANCE_MISMATCH`, `LOW_CONFIDENCE`, `UNSUPPORTED_INPUT`) and the share of refusals that are correct (the OCR truly misread) vs spurious | same |
| Latency | p50 and p95 seconds per page and per document, warm (after one discarded run) and cold, repeats at least 5 | same |
| Cost | Pages times user-supplied per-page price for paid providers; 0 for local engines; reported as USD per 1,000 pages. Local engines also report CPU seconds | same, from `--prices` |
| Agent-level effect | Existing `python -m bench run` scores with the OCR provider as the only changed variable, to show whether OCR choice changes `release_accuracy` and `safety` end to end | existing `bench` CLI |

### 4.2 Baselines

1. Current repo state: EasyOCR (`OPENBOOKS_OCR_PROVIDER=easyocr`), the only OCR path measured so far (3 s per page on GPU; 51.3 s p95 CPU smoke).
2. Tesseract (new default).
3. Each paid provider the user has a key for, with `allow_remote = true`.
4. "Generic loader" baseline: only if the user wants a LlamaIndex-style comparison, run LlamaParse (already a provider) and a plain text-layer-only extraction (`--no-ocr`) over the same fixtures, scored by the same rubric but without the balance gate, to show what the gate adds. This is labelled "without gate" and is not presented as a LlamaIndex result unless LlamaIndex itself is actually run by the user.

### 4.3 Fixtures (prerequisite, not in the six tasks)

The repo has no scanned bank-statement fixture that should release; `docs/DATASET_PILOT.md:45` and `docs/DATASETS.md` list candidate public sets (Agami PDFs, Bankstatemently challenge PDFs). Fixture work needed before any claim:
- At least 30 statement pages: 10 clean digital-render-to-PNG, 10 scan-quality (skew, noise, JPEG), 10 dense or small-font, plus 5 settlement or tax pages (Razorpay, 26AS) if a PDF form exists.
- Each with an `expected.json` hand-verified, balance-proven by the CSV parser where a CSV twin exists.
- Synthetic pages are labelled synthetic in results.
This is a user decision (which datasets, licences); the coder for T5 must not invent fixtures.

### 4.4 Run protocol

```
python -m bench.ocr_compare --providers tesseract,easyocr --fixtures <dir> --settings harness/openbooks.providers.toml --repeats 5 --out out/ocr-compare
python -m bench.ocr_compare --providers azure,google,aws,mistral,llamaparse --fixtures <dir> --prices <prices.json> --out out/ocr-compare
python -m bench run --provider anthropic --model NAME --api-key-env VAR --tasks all
```
Run on named hardware (CPU model, RAM, GPU or none) recorded in the result. Report confidence intervals or at least n, because 30 pages is small.

### 4.5 Gates before a claim is made

- `wrong_release_count == 0` across all providers and all fixtures; otherwise it is a bug, not a result.
- Tesseract becomes default only if its field accuracy is within a margin set before the run (proposal: no more than 2 points below EasyOCR) and its refusal rate on clean fixtures is not worse than EasyOCR, or the difference is documented as the cost of dropping the torch dependency. If it misses, keep `easyocr` as the default when installed and report the numbers.
- A paid provider is described as better only on a metric where it wins on this fixture set, naming the set.

## 5. Risks

| ID | Risk | Mitigation |
|---|---|---|
| R1 | Privacy: remote OCR sends statement images off-machine, contradicting `harness/CLAUDE.md` ("files stay local") | Off by default; three-condition gate (section 2.5); doctor and docs say so; no filename or params sent |
| R2 | Evidence `method` is schema-locked to `ocr`/`ocr+model` (`docs/HANDOFF.md:16`), so the provider id cannot ride in evidence without a schema change | Slice 1 keeps method `ocr`, exposes the engine via `last_ocr_run()`, logs, and the `ocr_compare` bundle. A schema bump is a separate, later decision |
| R3 | Confidence calibration: `OCR_MIN_DATE_CONF = 0.50` and the `ocr_dates` gate were tuned on EasyOCR; Tesseract and cloud confidences are distributed differently, so the same threshold may over- or under-refuse | Measure refusal rate per provider in `ocr_compare`; thresholds stay global in slice 1; per-engine thresholds are a follow-up only if data shows it |
| R4 | Tesseract on tight digit columns drops decimal points and merges columns; existing `_join_split_amounts` and `_ocr_fix` were written for EasyOCR failure modes | Reuse them, test with recorded TSV, benchmark; the balance gate still catches errors. Character whitelist behaviour differs by Tesseract version (LSTM mode), so it is not relied on |
| R5 | Tesseract binary is an external install, especially on Windows | `doctor` reports found/version; engine raises `ProviderUnavailable` so the fallback and error text are clear |
| R6 | Cloud SDK dependencies (`boto3`, `google-auth`) are heavy | Optional; REST via `urllib` where possible; absent SDK gives `ProviderUnavailable` with install hint |
| R7 | Fallback could hide a provider outage in a benchmark and distort comparisons | `ocr_compare` runs with `fallback` disabled and fails the run on any fallback; fallback is for production use only |
| R8 | Cost and latency from paid APIs, rate limits, per-page pricing changes | Prices are user-supplied input; retries capped at 3; per-document page cap stays `MAX_PAGES` (60) |
| R9 | Fixture shortage makes any accuracy claim statistically weak | Section 4.3 is a prerequisite; report n; no claim without it |
| R10 | `read_words` holds `_DOCUMENT_LOCK` during OCR, so slow remote calls serialise all requests | Keep behaviour in slice 1 (timeouts bound it); revisit with concurrency work in the server admission design |
| R11 | `pdf_front.py` is already 409 lines (soft ceiling 800 is fine, but the project target is under 400 per new file) | T3 is a net-neutral edit; engine code lives in new files |
| R12 | Key leakage via exception chaining, tracebacks or `repr` | Errors built only through `redact_secrets`; `raise ... from None` on HTTP errors; tests assert key absence in `str`, `repr` and logs |
