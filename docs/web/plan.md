# Open Books Web Implementation Plan

> A task and interface map for the first build of the web app. Every task ends in a runnable test or check.

**Goal:** A Lumeo-branded, conversation-style web app that runs files through the Open Books engine and answers questions about the released documents.

**Architecture:** FastAPI service (`OpenBooks/server`) wraps `openbooks.pipeline.process` and `openbooks.link.link` and streams per-file stage events over SSE. A Next.js 16 app (`OpenBooks/web`) proxies to it through route handlers, keeps history in IndexedDB, and runs Q&A against the Claude API with deterministic Decimal tools.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, python-multipart, pytest + httpx TestClient · Next.js 16.4.1, React 19.2, TypeScript 5.9, Tailwind 4.1 (`@tailwindcss/postcss`), `geist` 1.7.0, Inter via `next/font/google`, `lucide-react`, `idb`, `decimal.js`, `zod`, `@anthropic-ai/sdk`, Vitest + fake-indexeddb.

**Spec:** `docs/web/design.md` · Product: `PRODUCT.md` · Brand: `d:\Code\Lumeo\Lumeo_Pay-Prototype-\DESIGN.md`

## Global Constraints

- Brand: Lumeo DESIGN.md is binding. Radius 0 everywhere except glass (20px). Geist ≤ 500 weight, display only. Inter for UI. Geist Mono uppercase + tracking for labels and figures, `tabular-nums`. One lavender (`--accent-2`) moment per viewport. Text on accent always uses `--on-accent`. Plum is atmosphere only. `--unmatched` is the only error colour. Dark on `:root` by default, light under `[data-theme="light"]`, stamped before paint. Brand PNGs copied verbatim and swapped with `.brand-asset--*`.
- Tokens are copied verbatim from Lumeo `app/theme-tokens.css`, `type-scale.css` and `site-chrome.css` into `web/app/brand/`, each with a header naming the source.
- Money: never `Number()` an amount. Display engine strings as-is; aggregate with `decimal.js`.
- Engine output is displayed and downloaded byte-faithful (no reformatting of doc fields).
- Refusal codes and messages are shown verbatim.
- Do not claim PayPal, Wise or 1099 anywhere.
- The maturity note `EARLY RELEASE · TESTED ON SYNTHETIC DATA` is visible in the sidebar and on the empty state.
- Model `claude-opus-5-5`, adaptive thinking, `output_config.effort: "medium"`, `betas: ["server-side-fallback-2026-07-01"]`, `fallbacks: "default"`.
- The engine service binds `127.0.0.1:8765`; the browser never calls it directly.
- `prefers-reduced-motion`: every animation collapses and the final state renders.

## File map

```
OpenBooks/
  src/openbooks/pipeline.py            MODIFY  process(..., on_stage=None)
  tests/test_on_stage.py               CREATE
  server/pyproject.toml                CREATE  package openbooks_server
  server/openbooks_server/__init__.py  CREATE
  server/openbooks_server/app.py       CREATE  FastAPI app + routes
  server/openbooks_server/runs.py      CREATE  temp-dir run loop -> SSE events (generator)
  server/openbooks_server/catalog.py   CREATE  /formats data, /health checks, samples registry
  server/tests/test_server.py          CREATE
  web/                                 Next.js app
    package.json, tsconfig.json, next.config.ts, postcss.config.mjs, vitest.config.ts, .env.example
    public/brand/{mark,lockup}-{white,black}.png   copied from Lumeo
    app/layout.tsx                     fonts, ThemeScript, metadata
    app/page.tsx                       <Workspace/>
    app/globals.css                    imports brand/*.css + app styles
    app/brand/theme-tokens.css         verbatim Lumeo
    app/brand/type-scale.css           verbatim Lumeo
    app/brand/site-chrome.css          verbatim Lumeo
    app/styles/app.css                 workspace components in Lumeo language
    app/api/engine/[...path]/route.ts  GET proxy: health, formats, samples, samples/:id
    app/api/runs/route.ts              POST proxy, SSE pass-through
    app/api/link/route.ts              POST proxy
    app/api/ask/route.ts               Claude streaming Q&A with tools
    lib/types.ts                       openbooks.v1 TS types, Thread/Turn types
    lib/sse.ts                         parseSSE(stream) async generator
    lib/stages.ts                      STAGES, stageForRefusal(code)
    lib/ledger.ts                      columnsFor(batchKind), batch summary fields
    lib/query.ts                       queryTransactions(docs, filter) Decimal-safe
    lib/digest.ts                      buildDigest(docs) for the model context
    lib/store.ts                       IndexedDB thread store
    lib/engine-client.ts               client fetchers: runFiles(), link(), ask()
    lib/session-files.ts               in-memory File registry for re-run
    components/brand/{lumeo-mark,brand-lockup,theme-script,theme-toggle}.tsx
    components/workspace.tsx           layout + state orchestration
    components/sidebar.tsx
    components/composer.tsx  components/params-panel.tsx
    components/empty-state.tsx
    components/turns/{user-turn,run-turn,ask-turn}.tsx
    components/run-card/{run-card,stage-trail,data-tab,assertions-tab,evidence-tab,json-tab,refusal-fix}.tsx
    components/links-panel.tsx
    tests/*.test.ts
```

## Tasks

### Task 1: Engine `on_stage` hook
- [ ] Test `tests/test_on_stage.py`: an ok bank CSV (golden `BANK_HEAD` rows, params opening 1000 INR) records `["detect","parse","normalise","balance","validate"]`; a text file with no known header records `[]` and returns `UNKNOWN_LAYOUT`.
- [ ] Add `on_stage: Callable[[str], None] | None = None` to `process`; emit after detect/parse (parse + normalise back to back), after the gate and after `validate_output`. For PDF/XLSX paths, detect + parse are emitted after their extractor returns.
- [ ] `python -m pytest -q` (fast suite) green.

### Task 2: Engine service
- [ ] `server/pyproject.toml` (deps: fastapi, uvicorn[standard], python-multipart; test: pytest, httpx).
- [ ] `catalog.py`: `formats()` (groups from spec section 5, layout ids from engine constants, `ALLOWED_EXT`), `health()` (`easyocr` importable, `models/roles_head.pt` exists, `SCHEMA_VERSION`, `MAX_BYTES`), `Samples` (lazy `golden.build(tmp)`, `list() -> [{id, filename, expect_status, expect_code, params}]`, `path(id)`).
- [ ] `runs.py`: `iter_run(files: list[tuple[str, bytes]], params: Params, file_params: dict[int, Params]) -> Iterator[tuple[str, dict]]`, written to a temp dir, `process(..., on_stage=...)` per file, events per spec section 3, temp dir removed in `finally`. `parse_params(dict) -> Params` raises `ValueError` on a bad opening or currency.
- [ ] `app.py`: routes `/v1/health`, `/v1/formats`, `/v1/samples`, `/v1/samples/{id}`, `POST /v1/runs` (StreamingResponse, events produced in a worker thread through a queue), `POST /v1/link`. Limit of 20 files, 422 on bad params.
- [ ] `server/tests/test_server.py`: an ok CSV event order; a tampered sample → refused `BALANCE_MISMATCH`; bad opening → 422; link pair; samples list + fetch; the temp dir is cleaned up.

### Task 3: Web scaffold + brand
- [ ] `package.json` with exact versions, scripts `dev`, `build`, `start`, `test`, `typecheck`, `dev:all` (concurrently: uvicorn + next).
- [ ] Copy brand PNGs and the three token CSS files verbatim (header comment naming the source).
- [ ] `layout.tsx`: GeistSans/GeistMono variables, Inter `--font-inter`, `<ThemeScript/>` in `<head>`, `data-theme` absent by default, skip link.
- [ ] Brand components ported from Lumeo (`LumeoMark`, ThemeScript with storage key `openbooks-theme`, ThemeToggle). `BrandLockup` = `LumeoMark` + "Open Books" (Geist 400) + `BY LUMEO` eyebrow; the Lumeo wordmark is never redrawn.
- [ ] `pnpm typecheck` and `pnpm build` pass.

### Task 4: Pure libs + unit tests
- [ ] `types.ts`, `sse.ts`, `stages.ts`, `ledger.ts`, `query.ts`, `digest.ts`, `store.ts` with Vitest coverage: SSE chunk boundaries; refusal → stage map for all 6 codes; `queryTransactions` sums `"0.10"+"0.20"` to exactly `"0.30"`, filters by direction, description and dates, groups sums per currency; `buildDigest` omits evidence and truncates > 200 transactions; store CRUD round trip (fake-indexeddb).

### Task 5: Proxies + Ask route
- [ ] Engine proxy routes (`OPENBOOKS_ENGINE_URL`, default `http://127.0.0.1:8765`), runs SSE pass-through (`duplex: "half"` streaming body), 502 with a JSON error when the engine is down.
- [ ] `/api/ask`: zod-validated body; 503 without credentials; a manual streaming loop on `client.beta.messages.stream` with tools `query_transactions` and `get_evidence` (zod-validated, `is_error` on invalid input); the response is NDJSON events `{type:"text",text}`, `{type:"tool",name,summary}`, `{type:"error",message}`, `{type:"done"}`. The system prompt is frozen and cached; the digest is sent as the first user content block with `cache_control`.

### Task 6: Workspace UI
- [ ] Workspace state machine: threads from the store, active thread, composer → `runFiles` (SSE) or `ask` (NDJSON). Turns persisted on every completed event.
- [ ] Sidebar, EmptyState (formats + samples + maturity), Composer (drop zone, chips, limits, params popover), turns, RunCard with stage trail, tabs, verdict, refusal fix + re-run, JSON download, LinksPanel (after each run, `/api/link` with all ok docs in the thread).
- [ ] Styles in `app/styles/app.css` using only brand tokens.

### Task 7: Verify
- [ ] `pnpm test`, `pnpm typecheck`, `pnpm build`; server `pytest`; engine fast suite.
- [ ] Run both, Playwright: samples ok + tampered, the evidence tab, light/dark, 375px, reduced motion. Impeccable detector over `web/app` and `web/components`; fix findings.
- [ ] README section: how to run.
