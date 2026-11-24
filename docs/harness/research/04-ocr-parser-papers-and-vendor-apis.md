# OCR parser papers and vendor APIs (research note 04)

Date of research: 2026-11-24. Scope: verify T2 adapter facts, survey 2023-2026 papers and benchmarks, Tesseract tuning for digit tables, and claim wording versus LlamaParse. No repo code was changed.

Labels: **[VF]** verified fact (primary source fetched), **[VC]** vendor claim, **[IB]** independent benchmark, **[H]** hypothesis. Confidence: H/M/L. Anything not confirmed is marked **UNVERIFIED**.

## Ranked shortlist (read first)

1. **Textract DetectDocumentText is the cleanest geometry source.** Word boxes are ratios of page size (0-1), so the adapter can normalize without page-unit logic. [VF, H] `Blocks[]` with `BlockType == "WORD"`, `Text`, `Geometry.BoundingBox`. Source: S7, S8.
2. **Azure prebuilt-read gives word polygons plus page unit.** Units are inch for PDF and pixel for images, so the adapter must read the page `unit` per page. [VF for the page field, VC for the unit rule] S4, S5.
3. **LlamaParse v2 needs `output_options.additional_outputs: ["word_bbox"]` for word boxes.** Item boxes (`expand=["items"]`) are in points with `page_width`/`page_height`, unlike v1 (fractions). [VF] S2, S3.
4. **Mistral OCR: treat as page-markdown only until proven otherwise.** Only image-level `bbox` (x, y, width, height) surfaced in secondary sources. Word boxes: UNVERIFIED (official docs returned 404 twice). [UNVERIFIED] S9, S10.
5. **Google Document AI REST `:process` is verified for endpoint and Bearer auth**, but API-key support and the word-token path are UNVERIFIED. [VF for endpoint, UNVERIFIED for the rest] S6, S11.
6. **Tesseract: use 300 DPI rescaling, PSM 7 on cropped single-line cells, and a digit whitelist.** Per-cell crops beat a global page pass for digits. [VF for DPI and PSM list; H for the cell-crop plan] S12, S13.
7. **Multi-engine voting and running-balance constraints have no published bank-statement benchmark.** The closest is AI-BAAM (Malaysian statements, ~110 PDFs), which reports qualitative findings only. [IB, L] S14.
8. **Do not claim parity with LlamaParse.** The only shared-benchmark evidence (ParseBench) is authored by LlamaIndex and reports LlamaParse Agentic at 84.9%. Our claims need our own held-out, labelled bank statement set. [VF, H] S15.

## 1. Vendor API facts for T2 adapters

### 1a. Mistral OCR
- Endpoint, auth header, schema: official page `https://docs.mistral.ai/capabilities/document_ai/basic_ocr/` and `https://docs.mistral.ai/capabilities/OCR/basic_ocr` returned HTTP 404; `https://docs.mistral.ai/studio/document-processing/basic_ocr` also 404. Endpoint and auth: **UNVERIFIED** from primary source.
- Secondary search snippet (LiteLLM OCR docs, `https://docs.litellm.ai/docs/ocr`, not fetched): per-page object has `index`, `markdown`, `images` (each with `bbox` `x,y,width,height`), and page dimensions (`dpi`, `height`, `width` in pixels). Images are base64 only when requested. [Secondary, M/L]
- Word-level boxes: no evidence found. Answer to the question: **page markdown plus image-level boxes; word boxes UNVERIFIED (likely absent).** Confidence L.
- The `bbox_annotation_format` feature annotates figures and charts against a JSON schema. It is not word geometry. [Secondary, M]

### 1b. LlamaParse (v2)
- Endpoint: `POST https://api.cloud.llamaindex.ai/api/v2/parse` (URL or `file_id` JSON body); `POST /api/v2/parse/upload` (multipart); `GET /api/v2/parse/{job_id}`. [VF] Source: `https://developers.llamaindex.ai/python/cloud/llamaparse/api-v2-guide/` (fetched, date not shown on page).
- Auth: `Authorization: Bearer <API_KEY>`. [VF] same source.
- Gotcha: top-level `max_pages` returns `422 extra_forbidden`; use `page_ranges` inside the body. [VF] same source.
- GET response nests job fields under `job` (read `job.status`). Create response is top-level `id`, `status`. [VF] same source.
- Items: `expand=["items"]` returns per-page structured items (tables, headings, paragraphs). Each item has `type`, markdown, and a `bbox` list of `{x, y, w, h}`. Coordinates are in page points; `page_width`/`page_height` define the frame; PDF `/Rotate` is applied. Example heading box `x 72.0, y 100.0, w 200.0, h 12.0`. [VF] `https://developers.llamaindex.ai/llamaparse/parse/features/layout-and-bounding-boxes/` (from search snippet; re-fetch to confirm exact nesting). M.
- v1 layout extraction uses fractions 0-1, not points. Do not mix. [VF] `https://developers.llamaindex.ai/llamaparse/parse/v1/features/layout_extraction/` (snippet). M.
- Word boxes: `output_options.additional_outputs: ["word_bbox"]`, returned as a JSONL presigned URL under `raw_words_content_metadata`. [VF] v2 guide. Exact JSONL row keys: **UNVERIFIED** (check `https://developers.llamaindex.ai/llamaparse/parse/examples/parse_granular_bboxes/`).

### 1c. Google Document AI (REST, no SDK)
- Endpoint: `POST https://documentai.googleapis.com/v1/{name}:process`, where `name` is `projects/{p}/locations/{loc}/processors/{id}` or `.../processorVersions/{v}`. Regional host pattern: `LOCATION-documentai.googleapis.com` (for example `eu-documentai.googleapis.com`). [VF] `https://docs.cloud.google.com/document-ai/docs/send-request` and `https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/projects.locations.processors/process`.
- Auth: `Authorization: Bearer <access token>`, with the OAuth scope `https://www.googleapis.com/auth/cloud-platform`. The token in the samples comes from `gcloud auth print-access-token`. [VF]
- Without an SDK: mint the token yourself from a service-account JWT (OAuth 2.0 token endpoint). This step is standard Google OAuth but **UNVERIFIED** against the Document AI page here. API-key auth for online processing: **UNVERIFIED** (page does not say).
- Body: `rawDocument: { mimeType, content }` where `content` is base64. [VF] send-request page. Top-level `skipHumanReview`, `fieldMask`, `processOptions`. [VF] reference page.
- Response word path: `document.pages[].tokens[].layout.boundingPoly` and `textAnchor`. **UNVERIFIED** (Document reference page did not render the field list). Coordinates are believed normalized vertices; confirm before coding. Confidence L.

### 1d. Azure Document Intelligence prebuilt-read
- Endpoint and auth: `POST {endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30` with header `Ocp-Apim-Subscription-Key` (or OAuth2 scope `https://cognitiveservices.azure.com/.default`). [VF] `https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/read` (page `ms.date` 2026-08-15, `updated_at` 2026-10-19).
- Result path: `analyzeResults.pages[]` with `pageNumber`, `width`, `height`, `unit`, then `words[]` with `content`, `polygon`, `confidence`, `span`. [VF] same page (example JSON).
- Units: `unit` is `pixel` for images and `inch` for PDFs. Polygon units follow the page unit. [VC/VF] Microsoft `DocumentPageLengthUnit` enum (Pixel=0, Inch=1), `https://learn.microsoft.com/dotnet/api/azure.ai.formrecognizer.documentanalysis.documentpagelengthunit?view=azure-dotnet` (search snippet, not fetched). Confidence M-H. Multiply inches by 72 for PDF points. Arithmetic, not from a source.
- Polygon ordering: clockwise from top-left (per line-level docs, snippet). M.
- Note: the v4 "not supported" list on the page applies to Word/HTML, not PDFs. Read the page before relying on it.

### 1e. AWS Textract DetectDocumentText
- Operation and request: `Document.Bytes` (base64) or `Document.S3Object`. Synchronous limit 10 MB. [VF] `https://docs.aws.amazon.com/textract/latest/dg/API_DetectDocumentText.html`. The page also says the CLI accepts only JPEG/PNG, while the error section lists PDF and TIFF. Test before relying on PDF bytes.
- Endpoint and auth: AWS JSON-RPC style with SigV4 signing; the operation header `X-Amz-Target: Textract.DetectDocumentText`. **UNVERIFIED** from this session (common AWS convention; the Common Parameters page was not fetched). Confidence M.
- Response path: `Blocks[]`, filter `BlockType == "WORD"`, text in `Text`, geometry in `Geometry.BoundingBox` (`Left`, `Top`, `Width`, `Height`) and `Geometry.Polygon[]` (`X`, `Y`). `Page` gives the page number. [VF] API page.
- Coordinates: `Left`/`Top`/`Width`/`Height` are ratios of page width/height (0-1), origin top-left. [VF] `https://docs.aws.amazon.com/textract/latest/dg/API_BoundingBox.html`. `Polygon` is "a fine-grained polygon" within the box. [VF] `https://docs.aws.amazon.com/textract/latest/dg/API_Geometry.html`. Pixel conversion: multiply by rendered page width/height.

## 2. Papers and benchmarks (2023-2026)

| Ref | Source and date | Metric | Reported number | Label, confidence |
|---|---|---|---|---|
| P1 | ParseBench, arXiv 2604.08538, submitted 2026-04-09, v3 2026-04-13. `https://arxiv.org/abs/2604.08538` | Five dimensions (tables, charts, content faithfulness, semantic formatting, visual grounding). Exact per-dimension metrics not confirmed. | LlamaParse Agentic 84.9% (top); Docling, Marker, Unstructured not reported in fetched text. ~2,000 pages, 14 methods, enterprise docs (insurance, finance, gov). | IB, but LlamaIndex co-authors. M. |
| P2 | MinerU2.5, arXiv 2509.22186 `https://arxiv.org/pdf/2509.22186` | TEDS, TEDS-S | Top or near-top on PubTabNet, FinTabNet, CC-OCR, OCRBench v2. Exact cell values not extracted. | IB (authors' own). M. |
| P3 | PaddleOCR-VL, arXiv 2510.14528 `https://arxiv.org/pdf/2510.14528` | TEDS on OmniDocBench table blocks | 0.9195 overall, 512 cropped tables (OmniDocBench v1.5). | IB (authors' own). M. |
| P4 | AI-BAAM, arXiv 2510.16066 `https://arxiv.org/abs/2510.16066` | Qualitative table extraction on ~110 Malaysian bank statements (6 banks). Compares Azure prebuilt bank-statement OCR, olmOCR, PaddleOCR-VL, Surya. | Template matching best when formats are fixed; flexible OCR better when they vary. No running-balance or field F1 found. | IB, L-M (not fetched in full). |
| P5 | Invoice vision-LLM vs Docling-to-markdown, arXiv 2509.04469 `https://arxiv.org/html/2509.04469v1` | Field-level accuracy split by numeric, textual, identifier (IBAN) fields | Not extracted. | IB, M. Invoices not statements. |
| P6 | Unstructured benchmark `https://unstructured.io/benchmarks` (last updated 2026-03-31 per snippet) | Table-level content accuracy; over 1,000 enterprise pages | Docling Default 0.716 table accuracy (snippet). | VC (vendor), L. |
| P7 | Table-evaluation review, arXiv 2208.00385 `https://arxiv.org/pdf/2208.00385` | TEDS vs TEDS-S (structure only, cell text ignored) | Metric definition, no parser numbers. | IB (method), M. |
| P8 | OmniDocBench, CVPR 2025 `https://openaccess.thecvf.com/content/CVPR2025/supplemental/Ouyang_OmniDocBench_Benchmarking_Diverse_CVPR_2025_supplemental.pdf` | End-to-end table TEDS and edit distance | Marker and MinerU appear in end-to-end tables (snippet). Numbers not extracted. | IB, M. |

Metric notes: TEDS compares tree structure plus cell text. TEDS-S ignores text and checks row/column/span topology. Edit distance is used for text and reading order. Field F1 is standard for key-value extraction but no 2023-2026 bank statement paper I found reports it. [H]

Applicable ideas for a deterministic statement parser:
- **Running-balance constraint** (`balance_i = balance_{i-1} + credit - debit`): a free, exact validator for every parsed row. Use it as the oracle for accepting OCR output. [H] Expected benefit: flags digit-level OCR errors without ground truth. Accuracy risk: a single missing row can mask a compensating error, so require the statement's opening and closing balance too.
- **Column-geometry clustering** (x-centre clustering of WORD boxes into debit/credit/balance columns). Textract, Azure and LlamaParse all expose word geometry, so this works across engines. [H]
- **Multi-engine voting**: align tokens across engines by box overlap, then vote per digit, using the balance constraint as tie-breaker. No published bank-statement evidence supports this; test it. [H]

## 3. Tesseract tuning for digit-heavy tables

- DPI: "Tesseract works best on images which have a DPI of at least 300 dpi, so it may be beneficial to resize images." [VF] `https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html` (section "Rescaling").
- PSM: modes 0-13 "as of 3.21"; default is 3 (fully automatic, no OSD). PSM 7 is single text line; PSM 6 is a uniform block; PSM 11 is sparse text. [VF] same page.
- Whitelist: `tessedit_char_whitelist` is recommended "if you know you will only encounter a subset of the characters". [VF] same page. Whether the LSTM engine honors it: **UNVERIFIED** from the fetched text. Test with `--oem 1` on our crops before relying on it.
- Forum evidence (anecdotal, L): PSM 7 with a digit whitelist gave near-perfect digits on a single-line crop; a separate-pass approach (letters, digits, punctuation) raised success from 8% to 87% on one user's table. Sources: `https://groups.google.com/g/tesseract-ocr/c/...` threads (search results, not fetched individually).
- Hypothesis (H): per-cell crops at 300 DPI, PSM 7, digits plus `.,-()` whitelist, with the balance check as validation, will beat a whole-page PSM 6 pass on digit cells. Benchmark: 50 synthetic statements, cell-level digit accuracy, both configurations.

## 4. What we can honestly claim versus LlamaIndex/LlamaParse

Our current position: no public accuracy numbers for OpenBooks.

Claims we can make now:
- Deterministic validation (running-balance check, opening/closing balance) on each output. Verifiable by construction on our own fixtures. [H, but testable]
- Local processing with no document leaving the machine, if we run Tesseract only. Verifiable from the code path. Do not claim this for cloud adapters.
- Relative cost per page, once measured on our fixtures with published list prices. Cost sheet lives in a separate file.

Claims we cannot make without evidence:
- Accuracy parity or superiority over LlamaParse Agentic (ParseBench 84.9%, vendor-co-authored, not bank statements). Evidence needed: a labelled, held-out, synthetic-or-approved bank statement set, same pages through LlamaParse with the same scoring, with the scoring script in the repo.
- Any TEDS or field-F1 number for OpenBooks. Evidence needed: ground-truth JSON per fixture, a published scorer, and confidence intervals over at least 100 statements.
- Speed claims. Evidence needed: wall-clock per page on named hardware, with cold and warm runs.

Minimum evidence bundle for any public claim: dataset description (synthetic or approved only), labelled ground truth, scorer source, versions and dates of each engine, raw outputs, and a rerun script.

## Unresolved items (for the backlog)

- Confirm Mistral word-level output: official reference page needed (404 twice).
- Confirm Google `Document.pages[].tokens[].layout.boundingPoly` and API-key support.
- Confirm Textract endpoint and `X-Amz-Target` from the Common Parameters page.
- Confirm LlamaParse `word_bbox` JSONL row keys.
- Confirm Tesseract whitelist behavior under LSTM.

## Sources

- S1 Mistral OCR basic (404, unverified): https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- S2 LlamaParse v2 guide (fetched): https://developers.llamaindex.ai/python/cloud/llamaparse/api-v2-guide/
- S3 LlamaParse layout and bounding boxes (search snippet): https://developers.llamaindex.ai/llamaparse/parse/features/layout-and-bounding-boxes/
- S4 Azure prebuilt-read (fetched): https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/read
- S5 DocumentPageLengthUnit enum (search snippet): https://learn.microsoft.com/dotnet/api/azure.ai.formrecognizer.documentanalysis.documentpagelengthunit?view=azure-dotnet
- S6 Google send-request (fetched): https://docs.cloud.google.com/document-ai/docs/send-request
- S7 Textract DetectDocumentText (fetched): https://docs.aws.amazon.com/textract/latest/dg/API_DetectDocumentText.html
- S8 Textract BoundingBox and Geometry (fetched): https://docs.aws.amazon.com/textract/latest/dg/API_BoundingBox.html and https://docs.aws.amazon.com/textract/latest/dg/API_Geometry.html
- S9 LiteLLM OCR (search snippet, not fetched): https://docs.litellm.ai/docs/ocr
- S10 Mistral annotations (search snippet): https://docs.mistral.ai/studio/document-processing/annotations.md
- S11 Google process reference (fetched, redirect): https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/projects.locations.processors/process
- S12 Tesseract ImproveQuality (fetched): https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- S13 Tesseract forum threads (search snippets): https://groups.google.com/g/tesseract-ocr/c/EmOkHTz8g4k/m/GoiSdcskAQAJ and https://groups.google.com/g/tesseract-ocr/c/COJ4IjcrL6s
- S14 AI-BAAM: https://arxiv.org/abs/2510.16066 ; invoice benchmark: https://arxiv.org/html/2509.04469v1
- S15 ParseBench: https://arxiv.org/abs/2604.08538
- P2 MinerU2.5: https://arxiv.org/pdf/2509.22186 ; P3 PaddleOCR-VL: https://arxiv.org/pdf/2510.14528 ; P6 Unstructured: https://unstructured.io/benchmarks ; P7: https://arxiv.org/pdf/2208.00385 ; P8 OmniDocBench: https://openaccess.thecvf.com/content/CVPR2025/supplemental/Ouyang_OmniDocBench_Benchmarking_Diverse_CVPR_2025_supplemental.pdf
- Not fetched (cited only in snippets): Docling vs LlamaParse comparisons, DEV pdfmux article (vendor-affiliated, not used for numbers).
