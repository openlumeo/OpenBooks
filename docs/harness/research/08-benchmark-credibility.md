# 08 Benchmark credibility: how Open Books should measure and publish OCR and parsing claims

Status: research note, 2026-11-24. No code changes. Sources were fetched via search snippets only unless marked otherwise. Anything not confirmed is marked UNVERIFIED.

Evidence labels used below:
- VERIFIED: stated in a primary source (paper, dataset card, repo, vendor doc) that we saw.
- VENDOR: a vendor's own claim, not independently reproduced.
- INDEPENDENT: a third-party rerun with published conditions.
- HYPOTHESIS: our inference, not yet tested.
- UNVERIFIED: plausible or recalled, no source retrieved.

## 1. Ranked shortlist (read first)

1. **Adopt: a sealed, frozen scanned-statement release set with the wrong-release metric as headline.** Publish the scorer, raw outputs and a sealed hold-out. Expected to be the only claim outsiders can check cheaply. Verdict: adopt.
2. **Adopt: risk-coverage reporting (coverage at zero wrong releases, and wrong-release rate at each coverage level).** This reframes "refuse when unsure" as a measurable trade-off, not a slogan. Verdict: adopt.
3. **Experiment: binary unit-test style checks (olmOCR-bench style) for statement facts** (opening balance present, row count, closing balance, currency). Cheap to score, hard to game. Verdict: experiment.
4. **Experiment: a third-party rerun kit (Docker, pinned versions, one command).** Verdict: experiment.
5. **Reject: TEDS or edit-distance as the headline number for statements.** They score layout and text similarity, not the figure a user relies on. Keep them as secondary diagnostics only. Verdict: reject as headline.
6. **Reject: any public "beats X" claim without a third-party rerun.** Verdict: reject until step 4 is done.

## 2. Public leaderboards and their pitfalls

| Benchmark | What it measures | Verified facts | Pitfalls for us |
|---|---|---|---|
| ParseBench (arXiv 2604.08538, submitted 9 Apr 2026, LlamaIndex) | Parsing for agents across tables, charts, faithfulness, semantic formatting, visual grounding | ~2,000 human-verified enterprise pages; 14 methods; LlamaParse Agentic top at 84.88%; dataset on Hugging Face and code on GitHub (VERIFIED from search snippets: https://arxiv.org/abs/2604.08538, https://huggingface.co/datasets/llamaindex/ParseBench, https://github.com/run-llama/ParseBench) | Authored by a vendor that sells a top-ranked product (VENDOR, conflict of interest). Results reported by the same team. ParseBench-2 exists per a LlamaIndex PDF (https://www.llamaindex.ai/files/parsebench-v2-severity-aware-evaluation-of-document-parsing.pdf); its arXiv status UNVERIFIED. |
| OmniDocBench (CVPR 2025, arXiv 2412.07626) | 9 document types, edit distance, TEDS, CDM | Paper and supplement exist (https://openaccess.thecvf.com/content/CVPR2025/papers/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.pdf, https://arxiv.org/html/2412.07626v2) | Edit-distance formatting penalties and ambiguous ground truth are argued by LlamaIndex commentary (https://www.llamaindex.ai/blog/omnidocbench-is-saturated-what-s-next-for-ocr-benchmarks, INDEPENDENT commentary, not a rerun). TEDS can score the same rendered table differently when rowspan vs empty cells are used (secondary: https://engrxiv.org/preprint/download/7558/12334/10627 and Falcon Perception report https://arxiv.org/pdf/2603.27365, UNVERIFIED as to exact numbers). Saturation claim is from a preprint and commentary; primary CVPR limitations section not retrieved. |
| olmOCR-bench (arXiv 2502.18443, Allen AI, Feb 2025) | PDF-to-text with binary unit tests (presence and absence strings) | 1,403 PDFs, 7,010 unit tests; splits include old_scans and table_tests (https://huggingface.co/datasets/allenai/olmOCR-bench, https://arxiv.org/html/2502.18443v2). Authors chose binary tests to avoid LLM judges and fuzzy matching. | Substring tests are strict and can miss document-level fidelity (LlamaIndex review: https://www.llamaindex.ai/blog/olmocr-bench-review-insights-and-pitfalls-on-an-ocr-benchmark). Tests written by the benchmark team can be trained on: olmOCR 2 trains on synthetic unit tests as reward (https://arxiv.org/html/2510.19817v1), so the test style itself is now a training target. |
| DocILE (arXiv 2302.05658; ICDAR 2023 / CLEF 2023 competition) | Key information localisation and extraction (KILE) and line item recognition (LIR) on business documents | 6.7k annotated documents, 100k synthetic, ~1M unlabelled; baselines RoBERTa, LayoutLMv3, Table Transformer (https://arxiv.org/pdf/2302.05658). Requires position as well as value, which supports human verification. | Business invoices, not bank statements. Baseline numbers not read (snippets only). Good model for localisation-plus-value scoring. |
| FUNSD (149 train / 50 test forms) | Form key-value linking | Noisy scans; entities header, question, answer; multi-value entities allowed (search snippet summary, UNVERIFIED primary source) | Small. Layout-specific. Score saturation risk. |
| CORD | Receipts | Not retrieved | UNVERIFIED on annotation quality. |
| SROIE (ICDAR 2019, arXiv 2103.10213) | Scanned receipts: company, date, address, total | 1,000 receipts, 650/350 split; some fields blurred for privacy (https://arxiv.org/pdf/2103.10213). Community reimplementation says the released labels contain a few mistakes and ships corrections (https://github.com/zzzDavid/ICDAR-2019-SROIE, count of errors UNVERIFIED). | Four fields only, no line items, no balances. Template similarity across splits reduces generalisation (paper "Information Redundancy and Biases in Public Document Information Extraction Benchmarks", https://arxiv.org/pdf/2304.14936). |

General pitfalls that apply to all of the above:
- Vendor-run leaderboards: the team that writes the benchmark and sells a parser usually runs it (ParseBench case above).
- Metric choice favours the metric's author. A continuous similarity score rewards formatting, which vendors can tune to.
- Label noise in "gold" sets is common and rarely measured. SROIE is one documented case.
- Template overlap between train and test inflates scores (arXiv 2304.14936 above).

## 3. Metrics for Open Books

Our headline must be about money, not text. Proposed hierarchy:

1. **Wrong-release count and rate (headline).** A release is wrong if any released figure (opening balance, closing balance, transaction count, currency, or a sampled row amount or balance) differs from ground truth. Rate = wrong releases / released documents. Target 0.
2. **Coverage at zero wrong releases.** Fraction of documents released when wrong-release count is 0 on the sealed set. This is the selective-prediction number that matters.
3. **Risk-coverage curve.** Sort documents by the gate's confidence, sweep the threshold, plot wrong-release rate against coverage. Basis: Geifman and El-Yaniv define risk-coverage curves and rejection with a target risk (https://arxiv.org/abs/1705.08500, VERIFIED from abstract; NeurIPS 2017). SelectiveNet (https://proceedings.mlr.press/v97/geifman19a.html) is the trainable variant and not needed here.
4. **Field F1 on released documents.** Per field, exact numeric match after normalising decimal and thousands separators. Report per field and macro-average. Standard F1 definition; no external source needed (UNVERIFIED as a citation, standard definition).
5. **Refusal reasons.** Count by code (`LOW_CONFIDENCE`, `BALANCE_MISMATCH`, provider error). Used to show refusals are honest, not hidden failures.
6. **Diagnostics only:** normalised edit distance and TEDS on table regions. Keep out of the headline. Known to penalise formatting (section 2).

Statistics for zero-error claims (UNVERIFIED, no source fetched): with n released documents and 0 wrong releases, the one-sided 95% upper bound on the true wrong-release rate is about 3/n (the "rule of three"). So 0 wrong in 300 released documents supports "below about 1%", not "zero". Wording must say this.

## 4. Contamination and self-reporting

- Self-reported contamination checks are usually internal and opaque (https://aclanthology.org/2024.findings-emnlp.30.pdf, VERIFIED from snippet; general claim about LLM developers).
- Performance-based contamination detection: CONSTAT defines contamination as inflated, non-generalising scores and reports it in several open models (https://arxiv.org/html/2510.07575v1 or the CONSTAT paper it cites; VERIFIED from snippet only).
- Proposed defence: publish a lower accuracy ceiling for a benchmark so impossible scores signal leakage (https://arxiv.org/html/2505.18102v4, VERIFIED from snippet).
- Document-specific risk: public bank-statement PDFs (Agami set, Bankstatemently challenge) may already be in the training data of cloud OCR and VLM providers. Any public set can be contaminated for vendors we test. Hypothesis: a sealed set created by us from synthetic or approved statements is the only clean test. Our own repo already lists public candidates (`docs/DATASETS.md`), so they are dev-only.
- Reproducibility critique: heterogeneous custom scorers across repositories make results hard to reproduce (https://arxiv.org/html/2510.07575v1, VERIFIED from snippet).

Confidence: HIGH for the existence of these critiques; MEDIUM for their application to bank statements (HYPOTHESIS).

## 5. Publishing reproducibly

Required artefacts for any published number:
- Pinned versions: Tesseract, EasyOCR, PaddleOCR, Python, every cloud SDK, provider model IDs and API version strings, and the date of each run.
- Seeds and repeats: `--repeats 5` already planned in `docs/harness/PLAN.md`. Report mean and range, not best run.
- Raw provider outputs (words and boxes, redacted of keys) so a third party can rescore without calling the API again.
- Scorer repo with a version hash, and the exact gate thresholds (`OCR_MIN_DATE_CONF = 0.50` from the plan).
- Dataset manifest: file SHA-256, labels SHA-256, licence per file, and the split a file belongs to.
- Third-party rerun: a one-command script that takes the released dataset (synthetic, public or approved) and reproduces the table. Invite a rerun from someone outside the project and publish their result unedited.
- Negative results: publish refusals and failures, not just released figures.

Cloud-provider runs send document images to external services. Only synthetic or approved documents may be used for these runs (repo rule). The public release set must therefore be synthetic or licence-cleared, and this must be stated in the report.

## 6. Benchmark spec for Open Books

All sizes are proposals. Counts assume synthetic generation is feasible; real counts depend on how many approved statements exist (UNVERIFIED availability).

### Datasets
- **Dev set (public, may be contaminated, used for tuning):** public candidates from `docs/DATASETS.md`, e.g. Agami PDFs. Size: whatever exists; 20 to 50 documents. Never reported as a headline.
- **Synthetic set (generated):** 300 statements across 5 bank layouts (text-layer PDF, scanned at 150, 200 and 300 dpi, phone photo, skewed, multi-page). Known ground truth by construction.
- **Sealed hold-out:** 150 documents, generated with a different seed and layout list from the dev and synthetic sets. Hash committed before any provider run. Opened once per release.
- **Approved real set (if licence allows):** 30 to 60 scanned statements, labelled by two annotators, disagreements adjudicated. Report inter-annotator agreement.

### Splits
- Dev / synthetic / sealed hold-out, disjoint by document and by layout template. No layout appears in both dev and sealed sets.
- Within sealed, stratify by scan quality and page count.

### Adversarial and tamper cases (each must be refused or caught, never released wrong)
- Digit confusion: 0/8, 1/7, 5/6, comma vs period decimals.
- Dropped decimal point and merged columns (failure modes listed in the plan, R4).
- Negative balances shown in brackets or with CR/DR suffix.
- Row swapped between pages; page missing; duplicate page.
- Opening balance altered by one unit with transactions unchanged (balance gate must refuse).
- Visually plausible but internally inconsistent statement (totals unchanged, rows edited).
- Multi-currency statement and currency symbol missing.
- Handwritten annotation over totals (existing handwriting-must-refuse tasks).
- Blank or near-blank page and rotated page.
- Truncated PDF.

Tamper cases are generated by a script with recorded edits, so ground truth is exact.

### Metrics (report all, headline first)
1. Wrong-release count and rate, with 95% upper bound.
2. Coverage at zero wrong releases.
3. Risk-coverage curve per provider and per gate threshold.
4. Field F1 on released documents, per field.
5. Refusal count by reason.
6. Latency and cost per document (from `--prices`).
7. Diagnostics: edit distance and TEDS, not in headline.

### Report format
A single `REPORT.md` per run, containing:
- Header: date, git commit of scorer, provider versions, dataset hashes, repeats.
- Headline table: provider, coverage at 0 wrong, wrong-release count, upper bound, refusal count.
- Risk-coverage plot data (CSV).
- Per-field F1 table.
- Failure list: each wrong release listed with document ID and the figure that differed.
- Limitations section: sample size, synthetic share, licence status, which providers were not run.
- Raw outputs path and rerun command.

### Claim ladder (exact wording allowed at each evidence level)

Level 0, dev run only (no sealed set run):
- "Open Books runs a balance gate on OCR output. Dev-set results are internal and not a benchmark."

Level 1, sealed set run once by us, wrong-release count reported:
- "On our sealed set of N synthetic statements, Open Books released M documents with 0 wrong releases. The 95% upper bound on the wrong-release rate is about 3/M. Results are not third-party verified."

Level 2, pinned rerun script published, no outside rerun:
- "The benchmark, scorer and raw outputs are published with pinned versions. An outside rerun has not yet been performed."

Level 3, independent third-party rerun reproduces the headline:
- "An independent party reproduced the headline wrong-release count on the published sealed-set release, run [date] by [party]."

Forbidden at every level without the corresponding evidence:
- "Better than [named vendor]" (needs a Level 3 run of that vendor under identical conditions).
- "Zero errors" or "never releases a wrong figure" (use the upper-bound wording above).
- "Accurate" without a stated rate and sample size.
- Any figure from a vendor's own marketing used as a comparison (VENDOR label only).
- Any statement that a cloud provider was tested on real customer documents.

Vendor comparisons: state the provider, model or API version, date, and whether fallback was disabled (plan R7).

## 7. Differentiator: selective prediction versus extraction-only tools

Hypothesis: extraction-only tools (LlamaParse, Unstructured, Textract, Document AI, Mistral OCR and similar) return a figure for every input. Their benchmarks report accuracy on the set, which mixes wrong figures into one number. Open Books can report the converse: at zero wrong releases, what fraction of documents it is willing to release. This is a different, comparable quantity that the extraction tools do not publish.

Evidence: risk-coverage is an established framing (Geifman and El-Yaniv, arXiv 1705.08500). The claim that extraction-only tools do not publish a comparable metric is UNVERIFIED and should be checked against each vendor's docs before it is written.

Limits:
- Coverage is only meaningful alongside wrong-release rate. A tool that refuses everything has 0 wrong releases and 0 coverage.
- Score must be computed on the same sealed set for every compared engine.
- A balance gate can only catch errors that break a balance equation. Errors in descriptions, dates that still sum, or currency labels pass the gate. Those must be scored separately (field F1), and the claim must say so.

Verdict: experiment. Adopt the metric in our own report now; do not use it in a comparison claim until a third-party rerun exists.

## 8. Proposed benchmark experiments (for RESEARCH_BACKLOG use)

| ID | Hypothesis | Benchmark | Adopt, experiment or reject |
|---|---|---|---|
| B1 | Balance gate keeps wrong-release count at 0 across tamper cases | Adversarial set, section 6 | Adopt (cheap, direct) |
| B2 | Risk-coverage reveals a usable operating point (e.g. coverage >= 60% at 0 wrong) for scanned statements | Sealed set, all providers | Experiment |
| B3 | Field F1 and wrong-release rate disagree enough that F1 alone would mislead | Released documents | Experiment |
| B4 | Binary unit tests (presence and balance checks) catch the same errors as the gate at lower cost | Synthetic set | Experiment |
| B5 | An outside party can rerun the published suite within one day | Rerun kit | Experiment |
| B6 | TEDS or edit distance correlate poorly with wrong-release rate | Synthetic set | Reject as headline; keep as diagnostic |

## 9. Gaps and what was not verified

- Full primary text of ParseBench, OmniDocBench limitations, and DocILE baselines was not read (snippets only).
- CORD annotation quality: UNVERIFIED.
- Whether the Agami and Bankstatemently data are licensed for redistribution: UNVERIFIED. Check before any public release.
- Whether cloud providers train on submitted documents (affects contamination and privacy): UNVERIFIED; check each provider's data-use terms before sending any document.
- "Rule of three" and F1 definition are standard statistics, not sourced here.

## Sources

- https://arxiv.org/abs/2604.08538
- https://huggingface.co/datasets/llamaindex/ParseBench
- https://github.com/run-llama/ParseBench
- https://www.llamaindex.ai/files/parsebench-v2-severity-aware-evaluation-of-document-parsing.pdf
- https://arxiv.org/html/2412.07626v2
- https://openaccess.thecvf.com/content/CVPR2025/papers/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.pdf
- https://www.llamaindex.ai/blog/omnidocbench-is-saturated-what-s-next-for-ocr-benchmarks
- https://engrxiv.org/preprint/download/7558/12334/10627
- https://arxiv.org/pdf/2603.27365
- https://arxiv.org/html/2502.18443v2
- https://huggingface.co/datasets/allenai/olmOCR-bench
- https://www.llamaindex.ai/blog/olmocr-bench-review-insights-and-pitfalls-on-an-ocr-benchmark
- https://arxiv.org/html/2510.19817v1
- https://arxiv.org/pdf/2302.05658
- https://arxiv.org/pdf/2103.10213
- https://github.com/zzzDavid/ICDAR-2019-SROIE
- https://arxiv.org/pdf/2304.14936
- https://arxiv.org/abs/1705.08500
- https://proceedings.mlr.press/v97/geifman19a.html
- https://aclanthology.org/2024.findings-emnlp.30.pdf
- https://arxiv.org/html/2510.07575v1
- https://arxiv.org/html/2505.18102v4
- Repo: `docs/harness/PLAN.md` (sections 4 and risks R2, R3, R4, R7); `docs/DATASETS.md`
