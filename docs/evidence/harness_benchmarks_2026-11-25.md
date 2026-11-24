# OpenBooks harness benchmark results, 2026-11-25

## (a) Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home, 10.0.26300 |
| CPU | AMD Ryzen 5 7640HS, 12 logical CPUs (per speed bench `machine`) |
| Python | 3.13.5 |
| Tesseract | 5.4.0.20240606 |
| Git HEAD | `a999999` (branch `codex/harness-website-launch`). Working tree was not clean at session start: modified `.impeccable/config.json`, `harness/ui/server.py`, `harness/ui/static/styles.css`; untracked `harness/bench-out/`, `harness/ui/static/fonts/`. None of these were touched by this run. |
| Local harness UI | `http://127.0.0.1:8777/api/providers` responded. Tesseract and EasyOCR available; Azure, Google, AWS, Mistral, LlamaParse unavailable (missing env vars, or adapter not implemented). |
| Model API keys | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` all unset in the shell. No remote calls were made. |

## (b) Results

Every value below comes from a command run in this session. Raw JSON is in `docs/evidence/` with the 2026-11-25 suffix.

### Test suites

| Benchmark / check | Metric | Value | n | Method | Command | Status |
|---|---|---|---|---|---|---|
| Harness tests | pass count | 218 passed | 218 tests | pytest | `cd harness && python -m pytest -q` | MEASURED |
| Bench tests | pass count | 174 passed | 174 tests | pytest | `cd harness && python -m pytest -q bench/tests` | MEASURED |
| Engine package tests | pass count | 980 passed, 1 xfailed | 981 | pytest | `cd packages/py/openbooks && python -m pytest -q -x` | MEASURED |

### Token cost (`token_cost.v1`, tokenizer cl100k_base, local MCP build)

Method: serialized MCP payloads counted with tiktoken. Request tokens are what the client sends. Response tokens are what the server returns. This is payload size, not provider billing and not answer quality.

Commands:
- `cd harness && python -m bench.token_cost --input-mode upload --mcp-command "node ../packages/js/cli/dist/mcp/cli.js" --out <scratch>/tok_up`
- `cd harness && python -m bench.token_cost --input-mode file --mcp-command "node ../packages/js/cli/dist/mcp/cli.js" --out <scratch>/tok_file`

Fixtures: 3 bundled samples (balanced CSV, tampered CSV, camt.053 XML), 3 detail levels each.

| Metric | Value | n | Method | Status |
|---|---|---|---|---|
| `tools/list` size | 514 tokens | 1 | tiktoken | MEASURED |
| `resources/list` size | 122 tokens | 1 | tiktoken | MEASURED |
| Upload mode, standard request+response, summed over 3 fixtures | 1,319 + 332 = 1,651 | 3 | tiktoken | MEASURED |
| File mode, standard request+response, summed over 3 fixtures | 105 + 332 = 437 | 3 | tiktoken | MEASURED |
| Standard request tokens, file vs upload | 105 vs 1,319 (92% less) | 3 | tiktoken | MEASURED |
| Total request+response, file vs upload | 437 vs 1,651 (73.5% less) | 3 | tiktoken | MEASURED |
| Verdict response tokens | 77 (vs 332 standard, 77% less) | 3 | tiktoken | MEASURED |
| Tampered CSV, all 3 detail levels, both modes | `refused`, code `BALANCE_MISMATCH` | 6 | MCP tool output | MEASURED |
| Balanced CSV and camt.053, all detail levels, both modes | `ok` | 12 | MCP tool output | MEASURED |

Per-fixture request tokens, upload vs file (standard): balanced CSV 160 vs 40, tampered CSV 161 vs 41, camt.053 998 vs 24.

### Speed (`speed-bench.v1`, Tesseract, 5 scanned PDFs, 10 pages)

Command: `cd harness && python -m bench.speed_bench --limit 5 --seed 7 --pages-per-doc 2 --out <scratch>/speed`

Documents are scanned PDFs from the India bank statement fixtures, not screenshots.

| Metric | Value | n | Method | Status |
|---|---|---|---|---|
| Render 200 dpi, p50 / p95 | 128 ms / 155 ms | 10 pages | per-stage timer | MEASURED |
| PNG encode 200 dpi, p50 / p95 | 710 ms / 787 ms | 10 pages | per-stage timer | MEASURED |
| `prepare_for_ocr`, p50 / p95 | 665 ms / 1,049 ms | 10 pages | per-stage timer | MEASURED |
| Tesseract OMP default, p50 / p95 | 2,061 ms / 3,361 ms | 10 pages | per-stage timer | MEASURED |
| Throughput, 1 worker | 0.482 pages/s (20.8 s wall) | 10 pages | wall clock | MEASURED |
| Throughput, 2 workers | 0.928 pages/s (10.8 s wall) | 10 pages | wall clock | MEASURED |
| Throughput, 4 workers | 1.365 pages/s (7.3 s wall) | 10 pages | wall clock | MEASURED |

### Risk coverage (`risk-coverage.v1`)

Command: `cd harness && python -m bench.risk_coverage ../docs/evidence/ocr_compare_20_scans_2026-11-25.json --out <scratch>/risk`

Input is `overall_only` (no per-document confidence), so only the overall wrong-release count is reported.

| Provider | Docs | Released | Wrong released | Max coverage at 0 wrong | Status |
|---|---:|---:|---:|---:|---|
| tesseract | 20 | 0 | 0 | 0.0% | MEASURED |
| easyocr | 20 | 0 | 0 | 0.0% | MEASURED |

A zero-release result is a safe refusal, not an accuracy result. It shows the engine did not release wrong data on these scans. It does not show it extracted any correctly.

### Scanned statement latency (existing evidence, recomputed here from `ocr_compare_20_scans_2026-11-25.json`)

Command: read-only computation over the JSON in `docs/evidence/`. Not re-run.

| Provider | Docs | Status counts | p50 latency | min / max | Status |
|---|---:|---|---:|---|---|
| tesseract | 20 | refused: 17 `PARSE_ERROR`, 3 `BALANCE_MISMATCH` | 42.7 s | 26.1 s / 55.1 s | MEASURED (prior run) |
| easyocr | 20 | refused: 16 `PARSE_ERROR`, 4 `UNKNOWN_LAYOUT` | 66.6 s | 58.9 s / 98.8 s | MEASURED (prior run) |

The brief said Tesseract p50 is about 41 s. The file gives 42.7 s. The file is the source.

### Agent-task runner (`python -m bench run`)

| Metric | Value | Status |
|---|---|---|
| Model-driven task scores (release accuracy, field accuracy, efficiency, safety, overall) | none | NOT RUN |
| Reason | No provider API key is set in the environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` all unset). The run needs a key and calls a paid model. I did not read `web/.env.local` or any other secret file. | NOT RUN |
| Task catalogue | 36 tasks listed by `cd harness && python -m bench list` (subcommands: `run`, `score`, `list`). No keyless self-check was found for the runner. | MEASURED (list only) |

## (c) Inference and deployment facts

From `docs/harness/LAUNCH.md` and the deploy files. These describe configuration. I did not verify any live deployment.

| Item | Source | Status |
|---|---|---|
| Free local verification kit is the launch product. Optional cloud OCR is opt-in and billed by the provider. | LAUNCH.md | Documented |
| Default OCR is local Tesseract. Remote providers are gated behind `allow_remote` and `OPENBOOKS_ALLOW_REMOTE_OCR=1`. | LAUNCH.md, harness/README.md, local `/api/providers` | Documented and observed locally (`remote_enabled: false`) |
| Single engine container: 2 GiB memory, `OMP_NUM_THREADS` 2, bound to 127.0.0.1:8765, healthcheck via `/app/ready.py`. | `deploy/compose.inference.yaml` | Configured |
| Two engine replicas behind a private Caddy balancer, internal network only. | `deploy/compose.replicas.yaml` | Configured; not run here |
| Image: `python:3.12-slim`, Tesseract `eng`, CPU-only torch, EasyOCR only if `PREFETCH_EASYOCR=1` (default 0). | `deploy/engine.Dockerfile` | Configured; not built here |
| 2 GiB Docker smoke: 18 of 18 screenshot uploads at 1.60 images/s, 4.41 s p95. | LAUNCH.md | Claimed in doc; not re-run here |
| Hosted OCR providers (Azure, Google, AWS, Mistral, LlamaParse) | `/api/providers` | Not deployed or not usable: missing credentials; Mistral and LlamaParse adapters not implemented |
| VPS | Not touched in this run | n/a |

## (d) Claims

### Supported by the numbers above

1. Local file references cut standard request tokens by 92% (1,319 to 105) on the three bundled fixtures, and total request+response by 73.5% (1,651 to 437). Measured as tokenizer payload, not billed cost.
2. Verdict responses are 77 tokens against 332 for standard, on the same fixtures.
3. The tampered CSV was refused with `BALANCE_MISMATCH` at all three detail levels in both input modes. The balanced CSV and camt.053 were released at all levels.
4. Tesseract on the scanned-PDF speed set reached 0.48, 0.93 and 1.37 pages/s at 1, 2 and 4 workers on 10 pages, on this one Windows host.
5. On the 20 scanned statements, both Tesseract and EasyOCR released 0 documents and produced 0 wrong releases. The engine refuses scans; it does not extract them.

### Cannot be claimed from these numbers

- Any competitor comparison. No competitor (LlamaParse, Mistral, LiteParse, or other) was measured in this session.
- Agent answer accuracy, or tokens per verified correct answer. The agent runner did not run, so the per-success ratio is undefined.
- Scanned-statement extraction accuracy or coverage. Zero releases means no extraction was verified.
- Provider billing or cost per document.
- Production throughput or uptime. Speed numbers are 10 pages on one host.
- Anything about the two-replica or single-container deployment being live.
- Screenshot performance beyond the prior LAUNCH.md figures, which were not re-run here.

## (e) Open issues, ranked

1. **No agent-level measurement.** The runner needs a model API key. Until a run is done with a fixed model and task set, there is no answer-accuracy or tokens-per-correct-answer figure.
2. **Scanned statements are not released.** 0 of 20 released on both engines. Any scanned-statement claim in launch copy is unsupported.
3. **Speed sample is small.** 10 pages, 5 documents, one host. Needs a larger run before any published throughput number.
4. **Token numbers are payload only.** They use cl100k_base on the local MCP build, not provider usage, and not a model run. Caching and cold/warm behaviour are not measured.
5. **Deployment is untested here.** Compose and replica configs were read, not built or run in this session.
6. **Working tree is dirty.** Several tracked files are modified and `harness/bench-out/` is untracked. Release evidence should come from a clean commit.
7. **Minor discrepancy.** LAUNCH.md says the seed-7 Tesseract run had median 45.33 s and p95 56.85 s. The 20-scan file gives p50 42.7 s on a different set. Keep the sources separate in any write-up.

## Raw outputs

- `docs/evidence/speed_bench_2026-11-25.json`
- `docs/evidence/token_cost_upload_2026-11-25.json`
- `docs/evidence/token_cost_file_2026-11-25.json`
- `docs/evidence/risk_coverage_2026-11-25.json`
- Existing input: `docs/evidence/ocr_compare_20_scans_2026-11-25.json`
