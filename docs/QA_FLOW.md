# Q&A flow, the typed model, parameters and limits

This page documents how a question about released documents is answered, how the pre-trained typed model fits in, every parameter that controls it, the request limits, and the security audit of this release. Topology and packaging are in [SERVING.md](SERVING.md); the model itself is in [MODEL.md](MODEL.md).

## 1. End to end

```
 Browser (IndexedDB history)
   │ 1  files                       │ 5  question + released docs
   ▼                                ▼
 Next.js  /api/runs  /api/roles     Next.js  /api/ask
   │  size guard (411/413)            │  size guard, rate limit (429), schema check
   ▼                                  ▼
 Engine service (FastAPI, loopback)   OpenAI-compatible chat API (OpenRouter by default)
   │ 2  detect → parse → normalise      │ 6  streamed answer + tool calls
   │    → balance → validate            ▼
   │ 3  --model: typed heads read     Tool loop in Next.js (TypeScript, decimal.js)
   │    each word (role, value type,    query_transactions  → exact counts, sums, by_direction
   │    abstain) and cross-check        get_evidence        → page, bbox, raw text, method
   ▼ 4  released openbooks.v1 doc or typed refusal
```

1. The browser uploads files to `/api/runs`. The Next.js server checks the declared size, then streams the upload to the engine on loopback.
2. The engine runs each file through the four proof stages. A file is released only when every balance check ties out against figures printed in the file; otherwise it is refused with a typed code and no data.
3. With `model: true`, the typed heads (`models/roles_head.pt` and `models/roles_calibration.json`) read each word of a PDF or scan and give a role, a value type and a conformal set, and they abstain when unsure. The result is recorded on the document as `file.model` with the weights and calibration hashes. `POST /v1/roles` returns the model's raw per-word reading.
4. The browser keeps released documents and refusals in its own history.
5. A question goes to `/api/ask` with the thread history and the released documents. Refused documents carry no data and are skipped.
6. The Next.js server calls the language model. Money is never added by the model: the model calls tools, TypeScript runs them over the documents in decimal arithmetic, and the model words the answer from the tool results.

## 2. Parameters

### Engine run parameters (`params` and per-file `file_params`)

| Parameter | Type | Meaning |
|---|---|---|
| `currency` | 3-letter code | Statement currency, upper-cased. |
| `opening` | plain decimal | Opening balance when the file does not print one. |
| `account` | text | Account label. |
| `allow_derived_opening` | bool | Accept an opening balance derived from the first row; the result is marked not independent. |
| `ocr` | bool | Allow OCR for scans and images. |
| `model` | bool | Run the typed heads as a cross-check. |
| `date_order` | `dmy` or `mdy` | Resolves ambiguous dates; ambiguous dates are refused without it. |

### Q&A environment (web server only, never in client code)

| Variable | Default | Meaning |
|---|---|---|
| `OPENBOOKS_LLM_API_KEY` | none | API key for the chat endpoint. Q&A is off without it. |
| `OPENBOOKS_LLM_MODEL` | none | Model id, for example `nvidia/nemotron-3-ultra-550b-a55b:free` (free) or `qwen/qwen3-next-80b-a3b-instruct` (paid). Q&A is off without it. |
| `OPENBOOKS_LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint. |
| `OPENBOOKS_ENGINE_URL` | `http://127.0.0.1:8765` | Where the Next.js server finds the engine. |

Chat request, fixed in `web/app/api/ask/route.ts`: streaming, `temperature` 0, `max_tokens` 3000, at most 8 tool turns, provider routing `sort: "latency"` with `require_parameters: true` so the fastest provider that supports tool calls is chosen. The system prompt and the document digest are sent first and unchanged, which lets provider-side prefix caching serve follow-up questions.

### Tools the model may call

| Tool | Returns |
|---|---|
| `query_transactions` | `count`, `sums` per currency, `by_direction` (count and sums for credit and debit separately), up to 200 rows, `skipped_refused`. |
| `get_evidence` | Page, bounding box, row, raw printed text and extraction method for a record or field. |

`by_direction` exists so credit and debit totals come from code. Before it was added, a free model split a blended total by hand and reported credits of 5,557.26 instead of 6,857.26.

## 3. Request limits

| Route | Limit | Over the limit |
|---|---|---|
| `/api/runs` | 100 MB declared body | 413 |
| `/api/roles` | 25 MB declared body | 413 |
| `/api/link` | 4 MB declared body | 413 |
| `/api/ask` | 4 MB declared body, 30 questions per minute | 413, 429 |
| any upload or JSON route | no `Content-Length` | 411 |
| engine, per file | 20 MiB, 20 files per run | typed refusal, 422 |

The question limit is one global in-memory window per server process, which fits a single-instance deployment. Before serving several users, add authentication and per-user limits.

## 4. Security audit of this release

Scope: the Next.js route handlers, the engine's upload and sample handling, and the parser sinks. Method: read each entrypoint end to end and prove reachability with a minimal request. Static scanners were not run, and this is not a penetration test.

| Finding | Severity | Status |
|---|---|---|
| Upload and JSON proxies forwarded bodies of any size, so a remote client could fill the engine's disk or memory | High | Fixed: declared-size guard on every proxy route, verified with 413 and 411 requests |
| `/api/ask` was unauthenticated and uncapped, so anyone who could reach the app could spend the API key | High | Mitigated: 4 MB body cap and 30 questions per minute; authentication is still the long-term fix |
| Engine `run.error` returned raw exception text, which could include server paths | Low | Fixed: generic message to the client, detail in the server log |
| Plugin loading broke when the `importlib_metadata` backport was active (class mismatch), refusing every file | Medium | Fixed: entry points are recognised by shape, with a regression test |
| Credit and debit totals could be hand-split by the model | Correctness | Fixed: `by_direction` from code |

Checked and found safe: the engine proxy allowlist uses anchored patterns and the samples lookup is a dictionary keyed by id, so there is no path traversal; uploaded filenames are reduced to a safe basename inside a per-run temp directory; model weights load with `weights_only=True`; there is no `pickle`, `yaml.load`, `eval`, `shell=True` or `subprocess` in the engine or packages; the UI renders answers as text and has no HTML injection sinks; the LLM endpoint is set by the server environment, not by the user, so there is no SSRF through it. Document text is passed to the model as data, and the model's only tools are read-only.

Free models are rate limited and their providers may log prompts. Do not send real financial documents through a `:free` model without checking the provider's data policy.

## 5. Verification

- Web: `tsc --noEmit` clean; 27 Vitest tests pass, including `by_direction` and the guards.
- Python: the full suite passes (423 passed, 16 skipped; the skipped tests are the slow ones gated behind `OB_SLOW=1`). The registry regression test covers the backport class mismatch.
- Live end to end through the proxy: a bank CSV and a text PDF both released, the PDF was read by the typed model (`file.model` present), `/api/roles` returned 200, and the question "How many transactions, and total credits and debits?" returned 8 transactions, credits 6,857.26 INR (5) and debits 2,756.86 INR (3), matching the document. First token about 1.6 s and complete answer about 6.7 s on the free model; this is a single measurement, not a benchmark.
