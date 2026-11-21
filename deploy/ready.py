"""Container readiness: /readyz (model loaded, not draining) plus the OCR runtime. Fails while draining."""
import json
import os
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8765"
with urlopen(f"{BASE}/readyz", timeout=8):  # raises (non-zero exit) on 503
    pass
KEY = os.environ.get("OPENBOOKS_ENGINE_KEY", "")
with urlopen(Request(f"{BASE}/v1/health", headers={"x-openbooks-key": KEY} if KEY else {}), timeout=8) as response:
    health = json.load(response)
if not health["ocr_available"]:
    raise SystemExit(health["ocr_issue"])
