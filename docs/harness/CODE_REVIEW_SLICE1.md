# Code review slice 1
Verdict: DO NOT DEPLOY until H1 and H2 are fixed.
HIGH
- H1 ocr_providers.py:204-205 empty OCR result raises ProviderError, so a blank or no-text scanned page now faults the whole document (EasyOCR old path returned []).
- H2 ocr_providers.py:217 min(coords)<0 raises; EasyOCR polygons can have negative coordinates at page edges, so valid pages now fault. Clamp to 0 or only reject non-finite.
- H3 ocr_providers.py:496-500 + pdf_front.py:66-71 EasyOCR readtext now runs outside _DOCUMENT_LOCK, slot semaphore = cpu_count, so shared Reader/torch is called concurrently (previously serialised). Use slot size 1 for local engines or a lock in EasyOcrEngine.
MEDIUM
- ocr_providers.py:418-421 semaphore is rebuilt every call and _positive_int ConfigError escapes as non-EngineFault.
- ocr_providers.py:134 shipped toml via parents[6] only works in a source checkout; image gets built-in defaults (fine).
Verified
- select_engine falls back to easyocr when no tesseract binary; dpi 200 and scale unchanged; same word construction. Model/role path untouched.
- Security HIGH-1/2/3 fixed (allowlist :42, google host check ocr_cloud:204, azure https/DNS check :189-196).
- ocr_prep and balance_repair are not imported anywhere in src. boto3 lazy (ocr_cloud:430), PIL lazy, numpy TYPE_CHECKING only; no new hard deps.
- No code comments in new python/bench/test files.
- _RUNS reset per document; engine chosen once per document.
