# Phase 1 audit: pipeline performance (read-only, static)

Source: haiku-scout static read. No profiling was run; hot spots below are candidates, not measured.

## Pipeline (upload to output)

| Stage | Location |
|---|---|
| Upload staging (1 MB chunks to disk) | server/openbooks_server/runs.py:112-125, app.py:139-143, :283-293 |
| Execute (one thread per run) | runs.py:127, app.py:179 |
| Detect and dispatch | packages/py/openbooks/src/openbooks/pipeline.py:33-43, core/process.py:20-42 |
| XLSX (openpyxl read_only) | core/frontends/xlsx.py:49-83 |
| Native PDF | statements/pdf_backend.py:42, :142 |
| OCR (EasyOCR, lazy singleton, per-page render) | statements/pdf_front.py:46-76 |
| Role model inference (batched) | server/openbooks_server/inference.py:52-74, :115 |
| Output | core/output.py:9, core/report.py:17 |

## Memory and limits

- MAX_BYTES is 2 GB (core/guard.py:7). Enforced while streaming at runs.py:118; 413 at app.py:295.
- Admission in-flight budget is 256 MB (admission.py:19); one oversized job is admitted alone.
- Fixed after audit: guard.py whole-file reads (document inputs now pass a Path; NUL check chunked) and admission.py `estimate_ocr_pages` (chunked scan).
- Still whole-file: text inputs (decode and parsers need the buffer), statements/roles.py:109, 142, 153 (weights and calibration), catalog.py:145 (samples.zip), pdf_backend.py:149 (image sources).

## Candidate hot spots (unmeasured)

- pdf_front.py:65-67: synchronous per-page render plus EasyOCR on one global reader, no batching.
- roles.py:142 and app.py:326: weights read per model load unless cached.
- app.py:179: each run holds one worker thread.

## Existing benchmark material

scripts/profile_roles.py, commits 2f771b4 and 90cb182, docs/INFERENCE_ROLLOUT.md, docs/QA_FLOW.md. Results not yet reviewed.

## Next

Phase 3 profiling needs real throughput numbers (pages/s, peak RSS, per-stage time) on representative OCR PDFs.
