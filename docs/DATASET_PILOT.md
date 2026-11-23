# Open Books dataset and training pilot

23 November 2026

The shipped model abstained on 2,529 of 2,611 words (96.86%) on AgamiAI Digital Type 1 `00001.pdf`. This is a synthetic fixture. The digital parser extracted the transaction rows, and the running-balance gate refused the file. The model's abstention rate measures how often it produced an ambiguous role set. Proposal accuracy, coverage of critical fields, and document decisions need their own scores. [Pinned source fixture](https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements/tree/e921370fcd61cdeeb25a55fa34e476dfabf18be8/train/India_Bank_Statement_Digital_Type1)

On the 810 tokens aligned to evidence for 162 labeled transactions on this file, the top role matched 570 (70.37%), and the model abstained on 733 (90.49%). Two of 77 singleton predictions disagreed with the labels, both on credit. The baseline uses parser geometry aligned to the publisher's rows.

## Data ready for the trainer

| Artifact | Evidence |
| --- | --- |
| `out/dataset-pilot/agami-manifest.json` | 400 Agami PDF/JSON pairs, with 200 identical transaction groups shared by digital and scanned versions. All 400 fail a running-balance check against their corresponding JSON. The manifest records file checksums and grouping keys. |
| `out/dataset-pilot/agami-type2-role-labels.jsonl` | 100 Digital Type 2 files, 594 pages, and 48,009 word labels across 16,003 transactions. The exporter requires every extracted date, direction, amount and running balance in a file to match the publisher's JSON, then uses the parser's evidence boxes. |
| `out/dataset-pilot/pilot-baselines.json` | 20 Agami digital PDFs, all 3,211 rows matching on those four fields, and all 20 files correctly refused by the balance gate. The parser also refused all five locally available independent Bankstatemently challenge PDFs with OCR disabled. This was a local compatibility smoke test. The publisher holds the reference labels for scoring. |

Agami publishes synthetic PDFs and transaction JSON under Apache 2.0. Use its roles for extraction and its inconsistent documents as negative cases for release. The cloned Bankstatemently repository supplies five PDFs at `2d8d31d68dcedbf9028b87f6c7df286f53a6c7de`. The publisher describes a larger 15-case benchmark with a separate grading service. [AgamiAI dataset](https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements) · [Bankstatemently benchmark](https://github.com/bankstatemently/bank-statement-parsing-benchmark/tree/2d8d31d68dcedbf9028b87f6c7df286f53a6c7de)

Run from the repository root with the document extras installed and the Agami files at `data/raw/agami_indian_bank_statements/train`.

```powershell
.venv/Scripts/python.exe scripts/audit_agami.py --out out/dataset-pilot/agami-manifest.json
.venv/Scripts/python.exe scripts/export_agami_roles.py --out out/dataset-pilot/agami-type2-role-labels.jsonl
```

Each JSONL record contains a document id, page number, label provenance and tokens with text, a page-normalized bounding box and a nullable role. During training, use null roles for context and mask their role loss. Retain the current fully labeled synthetic examples for description, background and value-type supervision. The exported labels are weak labels because the current parser proposes the geometry, which can underrepresent layouts it cannot read. Review a sample of the boxes by eye before folding the export into training.

## Training and accuracy gates

1. Keep Digital Type 1 and the matching scans out of the first challenger’s training data. Keep each original document with its scans and augmentations. Use the exact profile PDF for debugging, and reserve an untouched challenge set for promotion.
2. Add consented, redacted bank PDFs and scans, starting with the most common customer layouts. Have two reviewers resolve disagreements on date, direction, amount, balance and evidence. Include unfamiliar headers, repeated amounts, wrapped rows, altered digits, and degraded scans. Keep the production promotion set grouped by bank, template family and time.
3. Fine-tune a RoleNet challenger on the mixed corpus, then fit calibration on a separate split using the precision that will serve it. Compare both candidates on the same frozen set. Publish critical-field exact match, role coverage at the same error rate, confident wrong assignments, correct document releases and false releases. A useful first target is a 20-point gain in critical-field coverage at the same or lower confident error rate, with zero observed false releases in the challenge suite.
4. Keep corporate balance sheets on a dedicated path. Use SEC EDGAR Inline XBRL to create reference facts and NSE/BSE filings for Indian Ind AS coverage where reuse terms permit. Match issuer, reporting date, consolidation scope, unit, sign and scale. Use tagged facts directly on the structured path. For PDF-only filings, use a table recognizer and check the assets/liabilities/equity equation against printed totals within their display precision. The current trial balance input contract covers debit and credit ledger tables. [SEC financial statement data](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets) · [NSE integrated filings](https://www.nseindia.in/companies-listing/corporate-integrated-filing) · [BSE filing notice](https://www.bseindia.com/markets/MarketInfo/DownloadAttach.aspx?attachedId=6b163bb8-fbe3-4e14-be9a-47b99f2cfaaf&id=20250523-40)

A separate table-detection experiment can use the MIT-licensed Panhapich set. It contains synthetic statement images with transaction-table boxes. The pilot did not download its 3.53 GB archive. [Dataset card](https://huggingface.co/datasets/Panhapich/bank-statement-detection)

The first experimental challenger froze the encoder and trained only the role head on 12 Type 2 PDFs. It calibrated on five additional Type 2 files and scored eight Type 1 PDFs. Top-1 accuracy moved from 66.23% to 66.14%, abstention from 88.72% to 37.03%, and wrong singleton predictions from 13 to 714 out of 6,435 tokens. The drop in abstention came with a large increase in errors. Retain the shipped model until a challenger improves critical-field coverage without increasing confident errors.

```powershell
.venv/Scripts/python.exe scripts/finetune_agami_roles.py --out out/dataset-pilot/challenger-01
```

## Throughput gates

Profile native extraction, OCR, feature building, inference and validation separately on the target host. Test a fixed mix of native PDFs and scans at rising offered rates. Measure p95 end-to-end latency, queue time, memory, completed pages per second and verified documents per second. Prioritize PDF text extraction before GPU tuning on the profiled native layout. Run OCR only where the text layer is unusable, batch model windows within a bounded token budget and benchmark the balance-check path with that same batching. Try half-precision serving only after recalibration and proof-gate verification. [Local profiling notes](PROFILE_ROLES.md) · [Inference rollout and load tests](INFERENCE_ROLLOUT.md)

The 23 November loopback run completed 4 requests per second at 84 ms p95 for the one-page native PDFs tested, with zero errors and zero rejections. A burst of 100 requests over five seconds completed 93, rejected seven and had zero errors. One-page p95 reached 1,147 ms during that burst. The local sustained run also passed packaged fixture decision checks. These rates describe the local native-PDF load mix and the existing engine limits.

The one-page synthetic OCR smoke test completed both requests but measured 51.3 seconds p95 on CPU against an 8-second gate. Report completed throughput over the entire phase including drain time so a short submission window cannot conceal this backlog.

## Measured results

| Area | Result |
|---|---|
| Role model, 6,435 tokens, 8 held-out PDFs | Top-1 66.23% shipped vs 66.14% challenger. Abstention 88.72% to 37.03%. Confident wrong 13 to 714. Challenger rejected. |
| Role model challenger-02, mixed Type 1 and Type 2 training (60 files) and calibration (24 files), same 8 held-out files | Top-1 99.32%, coverage 99.95%, abstention 1.77%, confident wrong 1. Not yet promoted: synthetic data from one generator family only. |
| Challenger-02 ONNX export (fixed 512-token window, padded), 20,820 held-out tokens | fp32 75.6 MB: argmax agreement 100%, max logit diff 6.7e-06. int8 19.7 MB: argmax agreement 99.02%, max logit diff 0.110. int8 fails the parity gate (argmax and abstain identical to torch); keep fp32 or re-quantize with calibration. |
| Q&A trimmed prompt and tool text, 6 passing models | 24/24 passes unchanged. Input tokens 69,848 to 62,487 (10.5% less). Output tokens 4,187 to 4,148. Results in `out/dataset-pilot/ask-benchmark-trimmed.json`. |
| Native load, 1-page PDFs | 4 req/s sustained, 84 ms p95, 0 errors. |
| Burst, 100 requests in 5 s | 93 completed, 7 rejected, 0 errors, 1,147 ms p95. |
| CPU OCR smoke, 2 requests | 51.3 s p95 against an 8 s gate. Fails. |
| Q&A benchmark, 10 model families via OpenRouter | 33/40 passes. 116,572 tokens: 107,813 input and 8,759 output. Production-wide usage is unmeasured. |

Q&A benchmark per model, four cases each (signed net, date filter, evidence, refusal):

| Model | Pass | Input tokens | Output tokens | Median ms |
|---|---|---|---|---|
| nvidia/nemotron-3-ultra-550b-a55b:free | 4/4 | 13,688 | 984 | 8,458 |
| deepseek/deepseek-v3.2 | 4/4 | 12,790 | 642 | 7,356 |
| google/gemma-4-31b-it | 4/4 | 11,001 | 295 | 3,978 |
| minimax/minimax-m2.5 | 4/4 | 11,401 | 964 | 6,171 |
| moonshotai/kimi-k2.5 | 4/4 | 9,734 | 314 | 2,817 |
| z-ai/glm-4.7 | 4/4 | 11,234 | 988 | 12,846 |
| mistralai/mistral-small-3.2-24b-instruct | 3/4 | 11,341 | 369 | 3,664 |
| openai/gpt-oss-120b | 2/4 | 6,836 | 3,487 | 8,499 |
| qwen/qwen3-next-80b-a3b-instruct | 2/4 | 9,571 | 450 | 1,991 |
| meta-llama/llama-3.3-70b-instruct | 2/4 | 10,217 | 266 | 1,603 |

Sources: `out/ask-benchmark-compact-digest.json`, `out/dataset-pilot/ask-benchmark-more-models.json`, `out/dataset-pilot/load-*.csv`, `out/dataset-pilot/challenger-01/report.json`.

Sandbox MCP over stdio: `search` returns the operation catalog. `execute` takes `steps[]` of `id`, `operation`, `arguments` and returns a result or error per step. Captured shapes are in `out/dataset-pilot/mcp-shapes.json`.

For 2 GB per file, use resumable multipart upload directly to tenant-scoped object storage, then hand a verified object id to a worker. Enforce the byte quota during upload, validate the final size and checksum, and expire incomplete uploads. Use format-specific limits for PDF pages, OCR, workbook expansion and serialized results. CSV needs a bounded-memory reader with balance state across chunks. Process PDF pages incrementally from a seekable staged file, preserving cross-page balance state and evidence. Keep the 20 MiB synchronous limit until 2 GB tests cover interrupted uploads, retries, concurrent jobs, cleanup, parser memory and output equivalence.

1. `POST /uploads` reserves declared bytes from the authenticated tenant and returns an upload id, part size, and expiry. The API issues signed URLs in small batches and binds each URL to the object key and part number. Store the object in a private bucket and track reservation and expiry in PostgreSQL.
2. Completing the multipart upload verifies the storage checksum and byte count. In one database transaction, mark the upload complete and insert a durable job with an idempotency constraint. The worker verifies tenant ownership, processing parameters and content type. The queue carries an object key and checksum, and the worker commits the proof summary and evidence references with the job transition.
3. Treat job state as `queued`, `running`, `released`, `refused`, or `failed`. Lease worker slots, renew claims while running, and make retry and completion idempotent. Track input bytes, scan pages, staging disk, memory, timeout and retained output per tenant. Apply expiration to private inputs and results.
4. Exercise exact byte boundaries, missing and duplicate parts, invalid checksums, expired credentials, client cancellation, worker exit during parsing, replayed completion and cross-tenant reads. Canary one tenant with synthetic inputs before promoting the workflow. Preserve the existing endpoint as the rollback path.
