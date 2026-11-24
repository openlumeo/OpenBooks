# 11. Speed and accuracy techniques for OCR and table parsing (financial pages)

Date of research: 2026-11-24. Scope: research only, no code changes.
Labels: VERIFIED (read in a primary source), VENDOR/AUTHOR CLAIM, COMMUNITY (forum or anecdote), HYPOTHESIS, UNVERIFIED (no source found or source not read).
Project numbers (tesseract startup ~0.27 s/page, PNG encode 67 ms, global document lock) come from `docs/harness/LOAD_REVIEW_SLICE1.md` and are not re-measured here.

## Ranked shortlist

| # | Technique | Speed | Accuracy | Verdict |
|---|---|---|---|---|
| 1 | In-process Tesseract engine pool, one engine per worker, `OMP_THREAD_LIMIT=1` | High (removes per-page process start) | None | experiment (adopt if benchmark confirms) |
| 2 | Text-layer-first, per-page routing (keep, measure fallbacks) | High on digital pages | Neutral | adopt (already in design) |
| 3 | 300 DPI, 10 px border, deskew, adaptive binarisation before OCR | Small cost, may add time | Medium-High on digit glyphs | adopt (cheap, documented) |
| 4 | Running-balance constrained repair of digit errors | Low cost | High on recoverable rows | experiment |
| 5 | Re-OCR only low-confidence numeric crops (psm 7/8, digit whitelist) | Medium (small crops) | Medium | experiment |
| 6 | Confidence abstention gated by balance proof | Neutral | Reduces wrong releases | adopt as policy |
| 7 | Column geometry clustering from word boxes (text layer and TSV) | Neutral | Medium on multi-column tables | experiment |
| 8 | tessdata_fast vs tessdata_best model choice on the labelled set | Fast gains about 2x vs best | Unknown, needs measurement | experiment |

Rejected by default: multi-engine voting on every page (cost multiplies; use only on disagreement after 4 to 5 are measured).

## 1. In-process engine pool and OMP_THREAD_LIMIT

- Evidence: a Tesseract developer-community thread recommends calling the library directly, because wrapping the executable adds per-call startup cost ([COMMUNITY](https://groups.google.com/g/tesseract-ocr/c/HA_q6F1_34E) via search; thread title "use multi threads in tesseract", UNVERIFIED for exact wording).
- Tesseract's benchmark page recommends `OMP_THREAD_LIMIT=1` for versions 4.x and later, and says the OpenMP build wastes CPU and is disabled by default in 5.0.1+ ([VERIFIED](https://tesseract-ocr.github.io/tessdoc/Benchmarks.html), page undated, timings from a Dec 2021 to Jan 2022 build, Intel i7-10750H, 15-run average, pytesseract wrapper, single test image).
- Same page, 5.0.1 tessdata_best timing: 6.20 s (no OpenMP), 3.46 s (OpenMP build). This is a single image, so it shows the thread effect only ([VERIFIED](https://tesseract-ocr.github.io/tessdoc/Benchmarks.html)).
- Community reports say the variable must be set before process start and that tesserocr multithreading did not help for one user ([COMMUNITY](https://groups.google.com/g/tesseract-ocr/c/Zo4jqQT0--w)). tesserocr itself: UNVERIFIED for current API details; the project is at https://github.com/sirfz/tesserocr (not read).
- Expected effect: removes most of the 0.27 s/page startup; parallelism from processes, not threads. Confidence: medium.
- Complexity: medium (engine lifecycle, crash isolation, a worker per CPU). Memory: each engine loads its traineddata (tessdata_best is about 638 MiB compressed per the search summary, UNVERIFIED size; tessdata_fast about 336 MiB), so workers multiply model RAM.
- Accuracy risk: none if output is byte-identical; verify.
- Measure: pages/s and p95 latency on the labelled Agami scans, subprocess vs pool at 1, 2, 4 workers, with output diff = 0.

## 2. Text-layer-first, per-page routing

- Hypothesis: digital pages never need OCR; mixed documents need per-page, not per-document, decisions.
- Evidence: the project plan already routes this way (`docs/harness/PLAN.md`). No external numbers found; treat as industry-standard practice, UNVERIFIED as a benchmark.
- Risk: text layers that are present but wrong (bad font maps, hidden OCR layers from scanners). Mitigate by comparing text-layer digits against a sampled OCR page.
- Measure: fraction of pages routed to OCR, and digit mismatch rate between text layer and OCR on a sample.

## 3. Preprocessing: 300 DPI, border, deskew, binarisation

- Evidence: Tesseract says it "works best on images which have a DPI of at least 300 dpi"; deskew "severely impacts the quality of the OCR"; a 10 px border helps, but big borders hurt single-token images; Otsu can be suboptimal on uneven backgrounds, and 5.0.0 added Adaptive Otsu and Sauvola ([VERIFIED](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), undated page).
- Relevance to project: `PNG encode 67 ms` suggests the image path is already a cost; render at 300 DPI only for OCR pages, and avoid re-encoding (pass arrays in memory).
- Expected effect: accuracy up on small digits (4 to 6 pt); time may rise with DPI. Confidence: high on direction, medium on size.
- Complexity: low. Memory: a 300 DPI A4 grey page is about 8.7 MB raw; UNVERIFIED arithmetic, check.
- Risk: over-binarisation merges thin strokes (0 vs 8 confusion). Measure per-setting.
- Measure: digit-level error rate on the labelled scans per preprocessing setting.

## 4. Running-balance constrained repair

- Hypothesis: for a statement with opening balance B0 and per-row amounts a_i, balance B_i = B_{i-1} + a_i. When a row fails the balance check, search over the low-confidence digit alternatives (0/8, 1/7, 5/6, decimal position) for the smallest edit that closes the equation. This is the strongest accuracy lever specific to this product.
- Evidence: no literature found that uses this exact constraint (UNVERIFIED). FinCriticalED shows numeric values and monetary units are the most fragile fact types for OCR and VLM systems, and critical errors cluster on complex layouts ([VERIFIED](https://arxiv.org/abs/2511.14998), first submitted 19 Nov 2025, v3 7 Apr 2026, 859 pages, 9,481 facts, 13 systems).
- Risk: a repair can make a wrong value balance (two errors cancel, or a missing row is absorbed). Keep the balance proof as the release gate and report repaired cells separately.
- Expected effect: fewer abstentions on recoverable rows. Complexity: medium. Memory: negligible.
- Measure: on the labelled scans, count rows that were wrong and balanced-after-repair with the wrong value (false repairs). Target: zero false repairs on the labelled set before release.

## 5. Re-OCR of low-confidence numeric crops

- Evidence: `tessedit_char_whitelist` exists and the ImproveQuality page recommends it for known character sets, with psm 7 (single line) and 8 (single word) for small regions ([VERIFIED](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)). The page does not say whether the whitelist is honoured under LSTM mode (UNVERIFIED; test it, do not assume). Community reports say whitelists work with LSTM for some users ([COMMUNITY](https://groups.google.com/g/tesseract-ocr/c/N-7-lLrx5bw), anecdotal).
- Expected effect: small crops are cheap; accuracy gain only if confidence is informative.
- Risk: a whitelist can force a wrong digit when the cell holds a minus sign, a parenthesis, or a currency mark. Include those in the whitelist.
- Measure: digit error rate on crops with and without whitelist, per psm.

## 6. Confidence abstention gated by balance proof

- Evidence: selective prediction is standard, but no table-OCR source was read (UNVERIFIED for numbers). Use Tesseract word confidence (TSV) as one input only.
- Policy: release a page only when the balance proof passes and every numeric token has confidence above a threshold, or was repaired by a rule in 4. Otherwise abstain and return the page as review.
- Measure: coverage (fraction released) versus false-release rate, swept over the threshold on the labelled set. Target false-release near zero, accepting lower coverage.

## 7. Column geometry clustering and header detection

- Evidence: the text layer and Tesseract TSV both give word boxes. Table structure work (TFLOP, arXiv 2501.11800, author-reported 99.45 TEDS on FinTabNet, VENDOR/AUTHOR CLAIM, not reproduced) uses layout cues; no 2025 to 2026 financial benchmark with independent numbers was found (UNVERIFIED).
- Approach: cluster right edges of numeric tokens to find amount columns; use the header row for names; check each column for decimal alignment.
- Measure: column assignment accuracy on the labelled scans; TEDS is a weak metric here, use a semantic judge. Note a March 2026 study finds an LLM judge correlates with humans at r = 0.93, versus TEDS 0.68 and GriTS 0.70, across 21 PDF parsers on 100 synthetic documents ([VERIFIED](https://arxiv.org/abs/2603.18652), submitted 19 Mar 2026, revised 1 Jun 2026).

## 8. tessdata_fast vs tessdata_best

- Evidence: tessdata_fast is fastest and least accurate; tessdata_best is slowest and most accurate and is the only set that can be fine-tuned; tessdata is integerised legacy plus LSTM, faster than best and slightly less accurate ([VERIFIED](https://tesseract-ocr.github.io/tessdoc/Data-Files.html), undated). The Benchmarks page gives 5.0.1 timings of 6.20 s (best), 2.12 s (fast), 2.91 s (tessdata) on one image ([VERIFIED](https://tesseract-ocr.github.io/tessdoc/Benchmarks.html)).
- Risk: fast may lose digit accuracy; no accuracy numbers were found from maintainers (UNVERIFIED).
- Measure: digit error rate and pages/s for fast, default, and best on the labelled Agami scans. Choose per page class if needed.

## Not covered by sources (UNVERIFIED)

- Multi-engine voting, selective OCR region choice and calibration methods: no primary source read in this pass.
- LLM post-correction for financial digits: arXiv 2502.01205 ("OCR Error Post-Correction with LLMs in Historical Documents: No Free Lunches", Feb 2025) is about historical text, not financial tables ([VERIFIED title and date only](https://arxiv.org/abs/2502.01205v1)). It suggests post-correction can be risky, so do not use an LLM as the release decision.
- FastTab (arXiv 2605.22422, 2026) reports speed and S-TEDS, but its numbers were not read (UNVERIFIED).

## Benchmark plan on the labelled Agami scans

- Metrics: field-level exact match on amounts and dates; digit error rate; balance-proof pass rate; false-release rate; coverage; pages/s; p50 and p95 latency; peak RSS per worker.
- Conditions: fixed hardware, same image set, 3 runs, OMP_THREAD_LIMIT=1, record Tesseract version and traineddata hash.
- Gate: no technique is adopted unless the false-release rate does not rise.

## Sources

- https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- https://tesseract-ocr.github.io/tessdoc/Benchmarks.html
- https://tesseract-ocr.github.io/tessdoc/Data-Files.html
- https://arxiv.org/abs/2511.14998
- https://arxiv.org/abs/2603.18652
- https://arxiv.org/pdf/2501.11800
- https://arxiv.org/abs/2502.01205v1
- https://groups.google.com/g/tesseract-ocr/c/HA_q6F1_34E
- https://groups.google.com/g/tesseract-ocr/c/Zo4jqQT0--w
- https://groups.google.com/g/tesseract-ocr/c/N-7-lLrx5bw
