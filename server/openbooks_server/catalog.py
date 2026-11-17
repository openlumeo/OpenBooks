"""What the engine can read, whether it is healthy, and the synthetic sample files.

Everything here is derived from the engine itself so the web app can never claim
a format the engine does not parse (PayPal, Wise and 1099 are not built).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import threading
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from openbooks import pipeline
from openbooks.pipeline import ALLOWED_EXT, MAX_BYTES, SCHEMA_VERSION

# Same location openbooks.roles uses (repo/models). Not imported from there: that module needs torch at
# import time, and the service must start without the optional [scan] extra.
WEIGHTS = Path(pipeline.__file__).resolve().parents[2] / "models" / "roles_head.pt"

FORMATS = [
    {
        "id": "statements",
        "title": "Bank statements",
        "inputs": ["CSV", "OFX / QFX", "MT940", "PDF (text layer)", "Scans (OCR)"],
        "layouts": ["bank_csv.v1", "ofx.v1", "mt940.v1", "bank_statement_pdf.v1"],
        "extensions": [".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt", ".pdf", ".png", ".jpg", ".jpeg"],
    },
    {
        "id": "gateways",
        "title": "Gateway settlements",
        "inputs": ["Stripe balance export", "Razorpay settlement"],
        "layouts": ["stripe_balance.v1", "razorpay_settlement.v1"],
        "extensions": [".csv", ".xlsx"],
    },
    {
        "id": "tax",
        "title": "Tax documents",
        "inputs": ["Form 26AS (TDS)", "AIS", "FIRA"],
        "layouts": ["tds_26as.v1", "ais.v1", "fira.v1"],
        "extensions": [".csv", ".xlsx"],
    },
    {
        "id": "workpapers",
        "title": "Excel workpapers",
        "inputs": ["Trial balance", "Any layout above, as .xlsx"],
        "layouts": ["trial_balance.v1"],
        "extensions": [".csv", ".xlsx"],
    },
]

# Samples worth showing first, in order. Every other golden case stays reachable through /v1/samples.
FEATURED = [
    ("ok_bank_csv", "Bank statement CSV"),
    ("bad_bank_balance_break", "Bank CSV with a tampered balance"),
    ("bad_bank_no_opening", "Bank CSV without an opening balance"),
    ("ok_pdf_text", "Bank statement PDF"),
    ("ok_razorpay", "Razorpay settlement"),
    ("bad_stripe_payout", "Stripe export, payout off by 0.01"),
    ("ok_tds", "Form 26AS (TDS)"),
    ("ok_fira", "FIRA remittances"),
    ("ok_mt940", "MT940 statement"),
    ("ok_tb_xlsx", "Trial balance workbook"),
]


def engine_version() -> str:
    try:
        return version("openbooks")
    except PackageNotFoundError:
        return "unknown"


def health() -> dict:
    return {
        "status": "ok",
        "engine_version": engine_version(),
        "schema_version": SCHEMA_VERSION,
        "ocr_available": importlib.util.find_spec("easyocr") is not None,
        "model_weights_present": WEIGHTS.exists() and importlib.util.find_spec("torch") is not None,
        "max_bytes": MAX_BYTES,
        "allowed_extensions": sorted(ALLOWED_EXT),
    }


def formats() -> dict:
    return {"groups": FORMATS, "allowed_extensions": sorted(ALLOWED_EXT), "max_bytes": MAX_BYTES}


class Samples:
    """Golden cases, built once per process into a temp dir on first use."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._root: Path | None = None
        self._cases: dict[str, dict] = {}

    def _ensure(self) -> None:
        with self._lock:
            if self._root is not None:
                return
            from openbooks.golden import build

            root = Path(tempfile.mkdtemp(prefix="openbooks-samples-"))
            build(root)
            labels = dict(FEATURED)
            order = {cid: i for i, (cid, _) in enumerate(FEATURED)}
            for case in sorted(root.iterdir()):
                src = next(f for f in case.iterdir() if f.name != "expected.json")
                exp = json.loads((case / "expected.json").read_text(encoding="utf-8"))
                code = exp.get("code")
                self._cases[case.name] = {
                    "id": case.name,
                    "filename": f"{case.name}{src.suffix}",
                    "label": labels.get(case.name, case.name.replace("_", " ")),
                    "featured": case.name in labels,
                    "rank": order.get(case.name, len(order)),
                    "expect_status": exp["status"],
                    "expect_code": code[0] if isinstance(code, list) else code,
                    "params": exp.get("params", {}),
                    "_path": src,
                }
            self._root = root

    def list(self) -> list[dict]:
        self._ensure()
        cases = sorted(self._cases.values(), key=lambda c: (c["rank"], c["id"]))
        return [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases]

    def get(self, case_id: str) -> tuple[str, Path] | None:
        self._ensure()
        c = self._cases.get(case_id)
        return (c["filename"], c["_path"]) if c else None

    def close(self) -> None:
        if self._root is not None:
            shutil.rmtree(self._root, ignore_errors=True)
