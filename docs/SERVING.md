# How Open Books is packaged and served

Read [MODEL.md](MODEL.md) first for what the model does. This page is about the pieces around it: which package does what, how they find each other, which processes run in production, and what to check after a deploy. [PACKAGES.md](PACKAGES.md) is the older build-and-publish plan for the package split.

## 1. Runtime topology

```
 Browser ──HTTPS──► Next.js server  (web/, port 3000)
                      │  /api/runs   /api/roles   /api/link   /api/engine/*   /api/ask
                      │  (the browser never talks to the engine)
                      ▼  HTTP, loopback only, no auth
                    Engine service  (server/, FastAPI, 127.0.0.1:8765)
                      │  imports
                      ▼
                    Python package openbooks (core + providers, found through entry points)
                      │  optional, only with --model / POST /v1/roles
                      ▼
                    Typed heads  (models/roles_head.pt + roles_calibration.json, PyTorch, GPU if present)

 /api/ask  ──►  open-weights LLM API (separate; answers questions about released documents; totals computed by code)
```

Design rules that follow from this:

- **The engine has no authentication and binds to loopback.** Only the Next.js server may reach it. If the engine runs on another host, put it on a private network or behind a reverse proxy with its own auth; do not expose port 8765.
- **Uploaded files live in a per-request temp directory and are deleted when the request ends** (`runs.Run.cleanup`). Nothing is stored server-side. History stays in the browser (IndexedDB).
- **The model is optional.** Without weights or PyTorch the engine still serves every file type; only `--model` runs and `/v1/roles` are unavailable, and `/v1/health` says why.

## 2. The packages

### Python (`packages/py/`, install name → import name)

| Distribution | Import | Role | Depends on |
|---|---|---|---|
| `openbooks` | `openbooks` | The one public package (since 0.2.0), with five parts: | `jsonschema`, `openpyxl`, `pypdfium2` (`[scan]` adds EasyOCR, PyTorch, Pillow, NumPy) |
| | `openbooks.core` | The `openbooks.v1` contract and JSON schema, Decimal normalisation, balance gates, refusal codes, **layout detection and the provider registry**, `openbooks` CLI | |
| | `openbooks.statements` | Bank CSV, OFX, MT940, PDFs, OCR and the **typed heads with their weights** (`[scan]`) | |
| | `openbooks.gateways` | Stripe, Razorpay, PayPal, Wise | |
| | `openbooks.tax` | Form 26AS, AIS, FIRA, 1099-B, trial balance (experimental layouts) | |
| | `openbooks.doctor` | `openbooks doctor`: dependency, provider, model-integrity checks and a proven-or-refused self-test | |
| `lumeo-openbooks-lab` | `openbooks_lab` | **Private, never published**: synthetic data, golden sets, calibration fitting, payout matching | `openbooks[scan]` |
| `openbooks-server` (`server/`) | `openbooks_server` | FastAPI service with bundled synthetic samples | `openbooks`, FastAPI, uvicorn. Optional `lumeo-openbooks-lab` enables payout matching. |

### npm (`packages/js/`, pnpm workspace)

`@lumeo_hq/openbooks-core`, `@lumeo_hq/openbooks-statements`, `@lumeo_hq/openbooks-gateways`, `@lumeo_hq/openbooks-tax`, `@lumeo_hq/openbooks-doctor` and the `@lumeo_hq/openbooks` command-line package are **typed wrappers around the Python engine**. No parsing happens in JavaScript; they need `pip install openbooks` on the same machine. The web app in `web/` is a separate Next.js project that talks to the engine service over HTTP and does not use these packages.

### How the parts find each other

`openbooks.core` owns **what exists and in what order** (the known layouts and sniffers); detection never depends on which providers are registered. Providers (the built-in `openbooks.statements`, `openbooks.gateways`, `openbooks.tax`, or a third-party plugin) only supply implementations, through entry points declared in `packages/py/openbooks/pyproject.toml` (or the plugin's own):

| Entry-point group | Name → value | Example in `openbooks.statements` |
|---|---|---|
| `openbooks.layouts` | layout id → `parse(args, params)` | `bank_csv.v1` |
| `openbooks.sniffers` | layout id → `parse(text, params)` for formats recognised from their text | `ofx.v1`, `mt940.v1` |
| `openbooks.frontends` | `document` → object with `extract(path, params)` and `identity(params)` | PDFs and scans |
| `openbooks.gates` | `kind[:label]` → `gate(batch, transactions)` | `statement:ocr_dates` |
| `openbooks.linkers` | `default` → `link(docs)` and `run_link(paths, out)` | payout matching |

Consequences: registration is what makes a layout work. A file whose layout has no registered provider is refused with `UNKNOWN_LAYOUT` (`ProviderMissing`). It is **never** routed to a looser parser, which could claim a file meant for the missing one. **Running from `PYTHONPATH` instead of installing skips entry-point registration**, so layouts will not be found; always `pip install` (editable is fine).

### Install matrix

| You want | Install |
|---|---|
| Everything except OCR and the model | `pip install openbooks` |
| Plus OCR for scans and the typed heads | `pip install "openbooks[scan]"` (EasyOCR, PyTorch ≥ 2.6, Pillow) |
| From a source checkout | `pip install -e packages/py/openbooks -e server` (add `-e packages/py/openbooks-lab` for payout matching) |
| Check the install | `openbooks doctor` (exit 0 ok, 1 a check failed, 2 usage, 3 doctor crashed; `--json` for machines) |

Model assets are looked up in order: `$OPENBOOKS_MODELS_DIR`, the `data/` directory packaged inside `openbooks.statements`, then the repo `models/` directory in a source checkout. The calibration names the sha256 of its weights and a mismatch refuses to load.

## 3. The engine service (`server/openbooks_server/`)

Start it: `python -m uvicorn openbooks_server.app:app --host 127.0.0.1 --port 8765` (the model is loaded at startup so the first request is not slow).

| Route | Method | Purpose |
|---|---|---|
| `/v1/health` | GET | Engine and schema version, OCR and linking availability, `model_ready`, `model_issue`, `model_identity`, size limit (20 MB), allowed extensions. `model_weights_present` remains a compatibility alias for `model_ready`. |
| `/v1/formats` | GET | Supported layouts grouped for the UI, plus the unverified ones |
| `/v1/samples`, `/v1/samples/{id}` | GET | Synthetic golden files for trying the app |
| `/v1/runs` | POST (multipart `files`, `params`, `file_params`) | Process up to 20 files; **server-sent events**: `file.started`, `file.stage`, `file.done` (one `openbooks.v1` document, released or refused), `run.done` |
| `/v1/roles` | POST (multipart `file`, `params`) | The typed heads' own reading of one PDF or scan: `openbooks.roles.v1` |
| `/v1/link` | POST (JSON `docs`) | Link payouts and remittances to bank credits (`openbooks.links.v1`). Requires the optional linker. |

`params` (validated by `runs.parse_params`): `currency` (3 letters), `opening` (plain decimal), `account`, `allow_derived_opening`, `ocr`, `model`, `date_order` (`dmy`/`mdy`). Bad values return 422 with a message fit for the user.

### `POST /v1/roles` in detail

Input: one `.pdf`, `.png`, `.jpg` or `.jpeg` (other types: 422 `UNSUPPORTED_INPUT`; over 20 MB: 413) and optional `params` (`ocr`, `date_order` are used).

```jsonc
{
  "schema_version": "openbooks.roles.v1",
  "method": "pdf_text",                       // or "ocr"
  "pages": [{ "page": 1, "width": 595.0, "height": 842.0, "tokens": [{
      "text": "Balance",
      "box": [0.06, 0.08, 0.13, 0.10],        // fractions of the page, origin top-left
      "role": "other",                        // most likely role
      "role_set": ["other", "date"],          // conformal set: roles the model cannot rule out
      "vtype": "text", "type_set": ["text"],
      "abstained": true                       // role_set is not exactly one role
  }]}],
  "summary": { "tokens": 2611, "abstained": 2514, "abstain_rate": 0.9628,
               "by_role": {"desc": 947}, "inference_ms": 111.1, "device": "cuda" },
  "model": { "weights_sha256": "…", "calibration_sha256": "…" }
}
```

Errors: 422 `{error: <refusal code>, message}` for unreadable, encrypted, oversized or OCR-needed-but-off files; 503 `model_unavailable` when weights or PyTorch are missing; 502 from the web tier when the engine is unreachable.

Concurrency: one forward pass runs on the GPU at a time (a lock in `inference.py`); the windows of one document are batched together. Run **one uvicorn worker per GPU**, since each worker loads its own copy of the weights. Throughput across many simultaneous requests is not measured here and would need a request queue.

## 4. The web tier (`web/`)

| Next.js route | Forwards to | Notes |
|---|---|---|
| `/api/runs` | `POST /v1/runs` | Streams the upload in and the SSE out |
| `/api/roles` | `POST /v1/roles` | Streams the upload; client call `predictRoles()` in `web/lib/engine-client.ts`, types in `web/lib/types.ts` |
| `/api/link` | `POST /v1/link` | |
| `/api/engine/[...path]` | `GET /v1/health`, `formats`, `samples`, `samples/{id}` | Allow-listed paths only |
| `/api/ask` | OpenRouter (open-weights model) | Optional; needs `OPENBOOKS_LLM_API_KEY` and `OPENBOOKS_LLM_MODEL`; uses released documents only |

Environment (`web/.env.example`): `OPENBOOKS_ENGINE_URL` (default `http://127.0.0.1:8765`) and optional `OPENBOOKS_LLM_API_KEY` and `OPENBOOKS_LLM_MODEL`. The UI shows "Model ready/off" from `/v1/health` and enables the "Model cross-check" box only when the engine reports the model present.

Request size limits, the `/api/ask` rate limit, the Q&A parameters and the security audit are in [QA_FLOW.md](QA_FLOW.md).

Where the model's output reaches the user today: the cross-check box on a run (the released card shows the weights hash chip, and evidence methods read "model cross-checked"), and `LOW_CONFIDENCE` refusals. The per-word reading from `/v1/roles` is available to the browser through `predictRoles()` but no screen renders it yet.

## 5. Running it

Development (two processes):

```bash
pip install -e "packages/py/openbooks[scan]" -e packages/py/openbooks-lab -e server
cd web && pnpm install && cp .env.example .env.local
pnpm dev:all            # engine on 127.0.0.1:8765, web on http://localhost:3000
```

Production (same host):

```bash
python -m uvicorn openbooks_server.app:app --host 127.0.0.1 --port 8765     # engine, one worker
cd web && pnpm build && pnpm start                                            # Next.js on :3000, behind your TLS terminator
```

No Dockerfile or process supervisor ships today; run both under whatever your host uses (systemd, a container, pm2) and restart them together after replacing weights.

## 6. Pre-deploy and post-deploy checks

Before: `pytest server/tests`, `cd web && pnpm typecheck && pnpm test`, `openbooks doctor --strict`, and for the model `OB_SLOW=1 python -m pytest -q`.

After:

```bash
curl -s http://127.0.0.1:8765/v1/health          # model_weights_present must be true if you ship the heads
curl -s -F "file=@statement.pdf" -F 'params={"ocr":false}' http://127.0.0.1:8765/v1/roles | head -c 400
curl -s http://localhost:3000/api/engine/health   # the same answer through the web tier
```

Checklist:

- [ ] Engine reachable only from the web tier (loopback or private network); port 8765 not public.
- [ ] `models/` (or `OPENBOOKS_MODELS_DIR`) holds `roles_head.pt`, `roles_calibration.json`, `roles_manifest.json`; `/v1/health` shows `model_weights_present: true`.
- [ ] `models/jepa_encoder.pt` is **not** deployed (CC BY-SA pretraining, internal only; it is git-ignored).
- [ ] Packages installed, not on `PYTHONPATH` (entry points), and `openbooks doctor` passes.
- [ ] `OPENBOOKS_LLM_API_KEY` set only on the web server if questions are wanted; never in client code.
- [ ] After a model update, the calibration was refitted for the new weights (otherwise the engine refuses `--model` and says so in `model_issue`).
- [ ] You accept that the model abstains heavily on unseen layouts ([MODEL.md](MODEL.md) §7).

## 7. Adding a provider

1. Add a subpackage `packages/py/openbooks/src/openbooks/<name>/` and declare its entry points in the groups above in `packages/py/openbooks/pyproject.toml` (a third-party plugin declares them in its own distribution instead). New layout ids must also be added to the core's known-layout list, since core owns detection order.
2. Add its layout ids to `FORMATS` in `server/openbooks_server/catalog.py` (a test fails if a layout is emitted but not listed, or listed but not emitted).
3. Add a golden case in `openbooks_lab` (one balanced file that must release, one tampered twin that must be refused).
4. Add its files to `tests/packaging/test_wheels.py`, then follow the publishing checklist in [PYTHONOPENBOOKSPACKAGES.md](PYTHONOPENBOOKSPACKAGES.md).
