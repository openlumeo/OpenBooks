# Open Books inference rollout and capacity plan

Deploy the existing statement model to the inference host first. Verify its calibrated outputs there, then connect the website VPS over a private network and repeat the same fixture through the public website. After that, measure the production path before changing batching, precision, or the number of workers.

```mermaid
flowchart LR
    B[Browser] -->|HTTPS| V[Website VPS]
    V -->|Private encrypted link| E[Inference host]
    E --> R[PDF extraction or OCR]
    R --> M[Calibrated statement model]
    M --> G[Statement validation and release checks]
```

## Deploy the model and verify the connection

1. Record the inference host address, SSH fingerprint, CPU or GPU, RAM, and private network address. Record the website VPS address, site hostname, and current engine URL. Put the two hosts in the same region when possible. Use an encrypted private link with access to the engine restricted to the website VPS. Keep port 8765 off the public internet.
2. Build the inference service with the model weights and matching calibration. Use the tested CPU image for the first rollout unless the inference host requires a GPU image. Start with one engine process and the existing FP32 calibration. Retain the previous image tag or digest and model identity for rollback.
3. From the inference host, verify readiness, exact model identity, a PDF run with known results, and a screenshot through the role endpoint. From the VPS, check that the same engine responds across the private route and measure the connection latency. Promote only after these checks pass.
4. Point the website VPS at the private engine URL. Run the same smoke test through the public HTTPS website. Check browser progress and completion for a released PDF and a refused fixture. Keep the previous upstream available during cutover. If readiness or output parity fails, restore the previous upstream or engine image.

On the inference host, run from the deployment bundle root. Set the bind address to the host's private VPN IP for VPS access. The default loopback address lets you verify the engine before granting private access.

```sh
export OPENBOOKS_INFERENCE_BIND_IP=10.30.0.2
docker compose -f deploy/compose.inference.yaml up -d --build --wait
node deploy/smoke.mjs --engine "http://$OPENBOOKS_INFERENCE_BIND_IP:8765"
```

On the website VPS, after checking the private route:

```sh
export OPENBOOKS_SITE_ADDRESS=books.example.com
export OPENBOOKS_REMOTE_ENGINE_URL=http://10.30.0.2:8765
docker compose -f compose.yaml -f deploy/compose.vps.yaml up -d --build --wait web proxy
node deploy/smoke.mjs "https://$OPENBOOKS_SITE_ADDRESS"
```

Replace both example addresses. On a VPS with an existing reverse proxy, start only `web`. Attach a containerized proxy to the same network as Next.js, or publish the web port to loopback for a host proxy. The smoke test supplies INR, day-first dates, and model checking, and verifies the expected amounts and model identity. Pass a synthetic PNG or JPEG as the last argument to exercise OCR. Use the existing sandbox for local checks. Use redacted statements with known transaction values for accuracy evaluation.

The inference service is deployed on the 2 vCPU VPS with one worker, two CPU threads and loopback binding. Through an SSH tunnel, the PDF fixture released 10 expected transactions with the model identity recorded and the screenshot produced 89 OCR words. The website connection is pending the website host details.

## Rollout tooling in the repo

| Piece | Where | What it does |
| --- | --- | --- |
| Admission control | `server/openbooks_server/admission.py`, `middleware.py`, `drain.py`, `metrics.py` | Bounds in-flight jobs, queue depth, in-flight bytes and OCR pages. Over a limit the caller gets `429` + `Retry-After` and a JSON body at once; queued work that waits past `OPENBOOKS_QUEUE_TIMEOUT_S` or whose client disconnects is dropped. Limits: `OPENBOOKS_MAX_INFLIGHT` (2), `_MAX_QUEUE` (8), `_MAX_INFLIGHT_BYTES` (256 MiB), `_MAX_OCR_PAGES` (60), `_RETRY_AFTER_S` (5). |
| Request IDs and stage timing | same | `X-Request-ID` is accepted or generated, echoed and logged. Queue, extraction/OCR, model, calibration and serialization time are recorded per request. |
| Metrics | `GET /metrics` | Prometheus histograms per stage and input kind (`pdf_text`, `ocr`), request and rejection counters, in-flight gauge. Combine replicas from the buckets. |
| Liveness, readiness, drain | `/healthz`, `/readyz` | `SIGTERM` makes `/readyz` return `503`, lets in-flight work finish (`OPENBOOKS_DRAIN_TIMEOUT_S`), then exits. |
| Replicas | `deploy/compose.replicas.yaml`, `deploy/Caddyfile.lb` | Two engine replicas behind a private load balancer that routes only to ready replicas. |
| Cutover and rollback | `deploy/rollout.sh deploy <tag> \| rollback \| status` | Records the previous image tag and model identity, runs `smoke.mjs`, promotes only on a pass, and restores the previous tag on `rollback`. |
| Load test and gate | `deploy/loadtest.mjs` | Open-loop warmup, sustained and burst modes. Writes the benchmark CSV columns above and exits non-zero when the promotion gate fails. |
| Web proxy | `web/lib/server/engine.ts` | Forwards `X-Request-ID`, retries only connection-setup failures (never a started or streamed request), and passes `Retry-After` through to the browser. |

## Latency and responsiveness

Measure upload, private link, queue wait, PDF or OCR extraction, feature preparation, model forward, calibration, validation, and response serialization separately. Break down p50, p95, and p99 by PDF text versus scan, page count, and token count. A prior local GPU profile of one six-page text PDF reported 101.5 ms for word extraction and 34.7 ms for a batched forward pass. Its parser and hardware differ from the target deployment. Use it to choose what to instrument first. [Open Books model profile](PROFILE_ROLES.md)

On the first VPS smoke run, about 164 seconds elapsed between the PDF response and the following screenshot role response. The container peaked at 1.40 GiB of resident and cached memory and used about 0.93 GiB of swap during OCR. It stayed healthy with zero OOM kills. This was a single cold OCR request. Profile the warm path and test smaller detector input sizes against known fields before raising scan concurrency. If swapping persists, give OCR more RAM or move it to a separate worker host.

Keep a warm model where requests are served and reuse the VPS-to-engine connection. Stream progress after upload and send periodic heartbeats during long processing. Give the client separate upload and processing timeouts. Cancel work that is still queued when a client disconnects. Apply retries to connection setup or idempotent job submissions with the same request ID. Once an SSE response starts, reconnect to the existing job if resumable jobs are introduced.

The first deployment has one inference host. For redundancy, put at least two warm replicas on separate hosts behind a private load balancer. Route to ready replicas, drain in-flight requests during rollout, and verify failover while a second replica is serving traffic. Size the remaining capacity for the agreed load after losing a replica.

Separate text PDFs from OCR-heavy jobs as traffic grows. Scale OCR workers independently with a cap on active rendered pages. Reuse OCR output within an authorized upload session if the same document is opened in Model reading. Key short-lived reuse by upload ID, OCR settings and version, and tenant. Set a byte limit and TTL and clear entries when processing ends or the session expires.

## Memory and KV cache

The statement model is a bidirectional encoder. It reads each window once, and its attention activations can be released after the forward pass. There is no persistent decoder KV cache on this route. Keep the model weights resident once per worker, cap tokens and padded window length per batch, and limit OCR work in progress. The current role endpoint batches windows of a document with a 4,096 padded-token cap. [Open Books model profile](PROFILE_ROLES.md)

1. Keep upload bytes on disk as the multipart parser permits. Limit both bytes and decoded pixels and release each rendered page as soon as OCR has finished. Measure peak RSS during OCR, feature construction, and JSON serialization. If large role responses are material, add an opt-in paged or streamed response while preserving the current contract for existing clients.
2. Budget host RAM as baseline OS and services plus idle model worker RSS, peak incremental memory per concurrent OCR job, queue and response buffers, and headroom. Measure GPU peak allocated and reserved memory independently. Start with 30% headroom and set hard limits on in-flight bytes, pages, and tokens. Reject excess traffic with a retry delay when the queue is full.
3. Test small cross-request batches grouped by window length only if profiling shows the model is the bottleneck. Sweep the wait and token caps together. Promote FP16, BF16, or INT8 only after checking logits, conformal sets, refusals, and released amounts against the FP32 baseline. Refit calibration for the chosen precision if the outputs shift.

If the separate Q&A decoder is later self-hosted, assign it a separate memory and request budget. Approximate KV bytes per live token as `2 × layers × KV heads × head dimension × bytes per element`. A hypothetical decoder with 32 layers, 8 KV heads, head dimension 128 and BF16 needs about 512 MiB for a 4,096-token sequence before weights and other overhead. Cap context and active sequences, size the KV pool from measured free VRAM, and use paged allocation with eviction. Share only public prompt prefixes across tenants. Monitor time to first token, live KV usage, evictions, and preemptions. [vLLM engine configuration](https://docs.vllm.ai/en/stable/configuration/engine_args/)

## Load tests and plots

Run a one-worker benchmark on the target hardware with redacted or synthetic PDFs and scans. Warm up, then test a realistic traffic mix at increasing offered rates until p95 latency, errors, or memory hit the limit. Follow with a 1,000-request burst and a sustained run. Record offered and accepted requests per second separately so rejections cannot look like good latency. Add replicas on sustained queue delay and resource utilization. Set rate limits and maintain bounded queues while new capacity starts.

| Plot | X axis | Y axis | Split |
| --- | --- | --- | --- |
| Latency under load | Offered requests/s | p50, p95 and p99 end-to-end ms | Text PDF, scan, page bucket |
| Time per stage | Offered requests/s | Queue, upload and processing p95 ms | Extraction, OCR, features, model, response |
| Memory and saturation | Concurrent jobs | Peak RSS MiB and GPU VRAM MiB | Idle, steady load, burst |
| Traffic served | Offered requests/s | Accepted completions/s and rejection rate | Status code and input type |
| Model quality | Model and runtime version | Field match, abstention and refusal rate | Statement layout and input type |

Export benchmark rows with `run_id,input_kind,page_bucket,offered_rps,completed_rps,in_flight,p50_ms,p95_ms,p99_ms,queue_p95_ms,ocr_p95_ms,model_p95_ms,peak_rss_mib,peak_vram_mib,rejected_pct,error_pct`. Keep percentile samples per input group. Store aggregate latency histograms and derive percentiles from the buckets when combining replicas. [Prometheus histogram guidance](https://prometheus.io/docs/practices/histograms/)

The [capacity scenarios CSV](inference-capacity-scenarios.csv) contains illustrative inputs for plotting. It assumes 40% scans, two seconds of OCR service per scan and a 65% utilization target. Required OCR slots equal `ceil(scan requests/s × mean OCR seconds / target utilization)`. A slot means one concurrently served OCR job at the resources measured in the benchmark. The 1,000-user sustained case is roughly 17 requests/s, and 1,000 submissions over five seconds is 200 requests/s. Use measured service time and traffic mix before provisioning. An instantaneous burst larger than the admission limit should produce bounded waits and explicit rejections.

Use proposed canary objectives of under 300 ms to the first status after upload, under 2 seconds p95 for warm single-page text PDFs, and under 8 seconds p95 for single-page scans at the agreed offered load. Revisit them after the baseline. Promotion requires matching release and refusal results on the fixture suite, no out-of-memory restarts during the sustained run, and acceptable p95 latency with enough memory headroom for the next traffic step.
