"""Container readiness includes the packaged, calibrated model and OCR runtime."""
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:8765/v1/health", timeout=8) as response:
    health = json.load(response)
if not health["model_ready"] or not health["ocr_available"]:
    raise SystemExit(health["model_issue"] or health["ocr_issue"])
