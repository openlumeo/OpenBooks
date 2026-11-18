# Open Books Web: design spec

Date: 2026-11-18 · Status: approved direction (user answers: deterministic engine + LLM Q&A, local-only history, "Open Books by Lumeo" brand, TypeScript frontend, best-fit backend)

## 1. Goal

A conversation-style web app for the Open Books engine. A user drops financial files into a thread. Each file comes back as one `openbooks.v1` JSON document (released) or a typed refusal, shown as a run card that follows the four pipeline stages. The user can then ask questions about the released documents in plain language. The answers come from an open-weights model, but every number in an answer is computed by code, not by the model.

Primary user (PRODUCT.md): chartered accountants and bookkeepers in India processing client files. Deployment target: hosted by Lumeo.

Non-goals (v1): accounts or auth, server-side storage, editing engine output, mobile-native apps. (PayPal, Wise and Form 1099-B were added to the engine later and are listed as unverified layouts.)

Before a hosted deployment accepts real client data (outside v1, tracked as open decisions in PRODUCT.md): authentication and accounts, data-processing and retention terms, and per-user rate limits on `/v1/runs` and `/api/ask`. v1 is built so these can be added at the Next.js layer without touching the engine service.

## 2. Architecture

```
Browser (Next.js client, IndexedDB history)
   │  same-origin only
   ▼
Next.js 15 server (TypeScript, App Router route handlers)
   ├── /api/runs    ── proxy (SSE pass-through) ──►  FastAPI  /v1/runs
   ├── /api/link    ── proxy ──────────────────────►  FastAPI  /v1/link
   ├── /api/engine  ── proxy ──────────────────────►  FastAPI  /v1/health, /v1/formats, /v1/samples
   └── /api/ask     ── OpenAI-compatible API (openai SDK, OpenRouter by default), tools run in TS over the docs sent by the client
                                                     │
                                                     ▼
                                        FastAPI (Python, OpenBooks/server)
                                        wraps openbooks.pipeline.process() and openbooks.link.link()
```

- **Why a Python sidecar:** the engine is Python (PyMuPDF, EasyOCR, PyTorch). A warm process loads OCR and model weights once and can stream progress. Shelling out to the CLI per file would be cold every time and could not stream.
- **Why proxy through Next.js:** the browser sees one origin. The FastAPI port is bound to `127.0.0.1` and never exposed, and the LLM API key lives only in the Next.js server environment.
- **Repo layout:** `OpenBooks/server/` (package `openbooks_server` with its own `pyproject.toml` that depends on the `openbooks` engine plus `fastapi`, `uvicorn`, `python-multipart`), `OpenBooks/web/` (Next.js). The engine package under `src/openbooks/` gains one optional hook (section 4) and nothing else.

## 3. Engine service (FastAPI, `OpenBooks/server/openbooks_server/`)

| Endpoint | Behaviour |
|---|---|
| `GET /v1/health` | `{engine_version, schema_version, ocr_available, model_weights_present, max_bytes}`. Doctor-style checks for the UI status bar. |
| `GET /v1/formats` | Supported input groups, extensions and layout ids, taken from engine constants. The empty state reads this so it never claims an unbuilt format. |
| `GET /v1/samples` | Golden-set cases built once per process by `golden.build()` into a temp dir: `[{id, filename, expect_status, expect_code, params}]`. |
| `GET /v1/samples/{id}` | The sample file bytes. |
| `POST /v1/runs` | Multipart: `files[]` (max 20, each ≤ 20 MB) + `params` JSON (global) + optional `file_params` JSON keyed by index. Responds `text/event-stream`. |
| `POST /v1/link` | Body `{docs: [openbooks.v1 ...]}` → `openbooks.links.v1`. |

**`/v1/runs` event stream** (one SSE `event:` per line type, JSON `data:`):
- `file.started` `{index, name, size}`
- `file.stage` `{index, stage: "detect"|"parse"|"normalise"|"balance"|"validate", state: "done"}`
- `file.done` `{index, doc}` — `doc` is exactly what `process()` returned
- `run.done` `{released, refused}`

Files are written to a per-request temp dir (the engine needs a path and suffix) and deleted in a `finally`. Files are processed one at a time in a worker thread (OCR is heavy). Params map one to one onto `Params(currency, opening: Decimal, account, allow_derived_opening, ocr, model)`. A bad `opening` string returns a 422 before any file runs.

## 4. Engine change (only one)

`process(path, params, on_stage=None)`: an optional callback, called with the stage name after each stage succeeds (`detect`, `parse`, `normalise`, `balance`, `validate`). Parsers normalise as they read, so `parse` and `normalise` are emitted back to back. The UI says so in a tooltip rather than pretending they are separate. Default `None` means no behaviour change, and existing tests must stay green.

For a refusal, the UI maps the refusal code to the stage where it stopped: `UNSUPPORTED_INPUT`/`UNKNOWN_LAYOUT` → Detect, `PARSE_ERROR`/`LOW_CONFIDENCE` → Parse, `BALANCE_MISMATCH` → Balance, `OUTPUT_INVALID` → Validate. This matches the diagram's "unknown layout" and "ties out? no" edges.

## 5. Web app (`OpenBooks/web/`)

Next.js 15 App Router, TypeScript strict, Tailwind v4 with Lumeo tokens copied from Lumeo's `globals.css` (DESIGN.md is binding, sections 2–7), and `next/font` for Geist, Geist Mono and Inter. Dark is the default; a light theme is keyed to `[data-theme="light"]` and stamped before paint.

### Screen

- **Sidebar (flat module, hairline right border):** Lumeo mark + "Open Books" wordmark (Geist 400) + mono eyebrow `BY LUMEO`. The Lumeo wordmark artwork is not reconstructed. Below it: a `New run` primary button, then the thread list (mono timestamps). At the bottom: the engine status strip (`ENGINE · OCR · MODEL`, with a live dot), a persistent quiet maturity note (`EARLY RELEASE · TESTED ON SYNTHETIC DATA`, linking to the README's Limitations), and the theme toggle. The empty state repeats the maturity note in one line under the lede.
- **Conversation column** (max 880px): turns stack top to bottom.
- **Composer** (bottom, `.field-input` language, radius 0): drag-and-drop zone over the whole column, attach button, textarea, and a `Params` popover (currency, opening balance, account, allow derived opening, OCR on/off, model cross-check). Send behaviour depends on the input: files present → run; text only → ask.
- **Empty state:** H1 "Proven JSON, or a typed refusal." (Geist 400), a lede, four input-group modules taken from `/v1/formats` (Bank statements, Gateway settlements, Tax documents, Excel workpapers), and a `Try a sample` row that loads golden cases into the composer.

### Turns

- **User run turn:** file chips (name, size), params summary in mono.
- **Assistant run turn:** a header line `2 RELEASED · 1 REFUSED`, then one **RunCard** per file, then a **Links** panel when the thread has a payout or FIRA plus a bank statement.
- **RunCard:** filename, `sha256` (short, copyable), chips for `detected_format`, `layout_version` and `method`. A four-step **stage trail** (Detect → Parse → Normalise → Balance) that lights up from live SSE events. A verdict: the `RELEASED` stamp, which is the one lavender moment for that card's viewport, or `REFUSED · CODE` with a rose left border and the engine's message verbatim. Tabs:
  - **Data:** a batch summary (kind, period, opening/closing/payout/printed totals) and a transaction ledger with mono, tabular numbers and columns that depend on the batch kind (statement, settlement, tax_statement, ais, fira, trial_balance).
  - **Assertions:** `.recon` rows (rule, expected, computed, a mint left border when passed, an `INDEPENDENT` chip).
  - **Evidence:** pick a record, see page, bbox, row, raw_text, method and confidence for each field. Clicking a ledger row jumps here.
  - **JSON:** the full doc, collapsible, with copy and download (`<name>.openbooks.json`). A turn-level "Download all" saves one JSON file per input (no zip), matching the engine's one-file-in, one-JSON-out contract.
- **Refusal recovery:** if a refusal message asks for an opening balance or currency, the card shows inline fields and a `Re-run` button. This works while the original `File` is still in memory (same tab). After a reload the button explains that the file must be attached again.
- **User ask turn → assistant answer turn:** streamed markdown. Tool calls show as a collapsed mono line (e.g. `QUERY · direction=debit · desc~"UPI" → 14 rows, 23,410.00 INR`).

### State and storage

IndexedDB (`idb`) stores threads `{id, title, createdAt, updatedAt, turns[]}`. Turns hold the returned docs and answers, never the original file bytes. The title is the first file name or the first question. "Delete thread" and "Clear all" are available. An in-memory map `turnId → File[]` lets a refusal be re-run within the session.

## 6. Ask (LLM Q&A)

- Route `POST /api/ask` with body `{question, history, docs}`, where `docs` are the thread's run results (released docs plus refusal stubs). The route streams the reply back.
- Model set by `OPENBOOKS_LLM_MODEL` (an open-weights, tool-calling model; free or paid on OpenRouter), `temperature: 0`, `max_tokens: 3000`, OpenRouter routing `provider.sort: "latency"` with `require_parameters`. The system prompt and docs digest come first as a stable prefix so provider-side prefix caching can hit, and the question comes last.
- **Context sent to the model:** for each doc, the file name, status, layout, batches and assertions, plus a transaction count. Released docs with ≤ 200 transactions are included in full. Larger ones are reached only through tools. Refusals carry their code and message. The `evidence` maps are reached only through tools.
- **Tools (run in TypeScript; amounts handled as decimal strings with `decimal.js`, never floats):**
  - `query_transactions({file?, direction?, kind?, description_contains?, date_from?, date_to?, min_amount?, max_amount?, limit?})` → matching rows plus `count` and an exact `sum` per currency.
  - `get_evidence({file, record_id, field?})` → evidence entries.
- **Rules in the system prompt:** answer only from these documents. Get every total or count from `query_transactions`, never from mental arithmetic. Cite file and record ids. A refused file has no data; explain its refusal code and what would fix it. Say plainly when a question cannot be answered from the documents.
- If no LLM credentials are set, `/api/ask` returns 503 with a clear message. The composer then shows "Q&A needs OPENBOOKS_LLM_API_KEY and OPENBOOKS_LLM_MODEL on the web server", and runs keep working.

## 7. Errors

- Engine unreachable → a banner and a disabled send button for runs; the status strip turns rose.
- An SSE stream that drops mid-run → files without a `file.done` show `INTERRUPTED` with a retry button (same-tab files).
- Over 20 files or a client-side file > 20 MB → blocked in the composer with the reason. The engine still enforces its own limits; the client check is only for faster feedback.
- Model errors: typed SDK errors are mapped to short messages (rate limit, auth, unavailable).

## 8. Testing

- **Engine:** the existing suite stays green; a new test checks the `on_stage` call order on an ok CSV and stopping at Detect on an unknown layout.
- **Server (pytest + TestClient):** a CSV release streams `file.started → stages → file.done(ok) → run.done`; a tampered twin streams `file.done(refused, BALANCE_MISMATCH)`; a bad opening → 422; `/v1/link` on a Razorpay settlement + bank CSV pair; `/v1/samples` lists and serves files; temp files are removed.
- **Web (Vitest):** SSE parser, refusal → stage map, the decimal `query_transactions`, the docs-digest builder, and an IndexedDB thread store round trip (fake-indexeddb).
- **Manual/E2E (Playwright):** load a sample → released card; a tampered sample → refused card on the Balance stage; an ask question returns a cited total; light/dark; 375px width.

## 9. Dev ergonomics

- `OpenBooks/server`: `pip install -e . -e server` (from `OpenBooks/`) then `uvicorn openbooks_server.app:app --port 8765`.
- `OpenBooks/web`: `pnpm i && pnpm dev`. Env: `OPENBOOKS_ENGINE_URL=http://127.0.0.1:8765`, `OPENBOOKS_LLM_API_KEY` and `OPENBOOKS_LLM_MODEL` (optional).
- A root `README` section explains both, plus a `pnpm dev:all` script that starts both processes.
