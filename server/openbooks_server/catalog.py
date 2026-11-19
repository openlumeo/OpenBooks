"""What the engine can read, whether it is healthy, and the synthetic sample files.

FORMATS is the human-readable grouping shown in the web app. It is written by hand, so
tests/test_server.py checks it against every layout id the engine source can emit: adding a
parser without listing it here (or listing one that does not exist) fails the build.
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
from openbooks.statements.assets import MODELS_DIR
from openbooks.pipeline import ALLOWED_EXT, MAX_BYTES, SCHEMA_VERSION

# Same location openbooks.roles uses. openbooks.paths has no torch import, so the service starts without the [scan] extra.
WEIGHTS = MODELS_DIR / "roles_head.pt"
CALIBRATION = WEIGHTS.with_name("roles_calibration.json")

_status_cache: dict = {}


def model_status(weights: Path = WEIGHTS, calibration: Path = CALIBRATION) -> tuple[bool, str | None]:
    """Whether --model can run, by the engine's own rule (roles.RoleModel._build): the calibration names the sha256 of
    the weights it was fitted on, and a mismatch refuses. Cached by modification time so the health poll stays cheap."""
    if not weights.exists():
        return False, "no model weights (models/roles_head.pt)"
    if not calibration.exists():
        return False, "no calibration (models/roles_calibration.json)"
    import hashlib

    # The calibration is small, so its content is part of the key; the weights are large, so their size and mtime are.
    # (Keying both on mtime alone served a stale answer when a file was rewritten within one timestamp tick.)
    cal_bytes = calibration.read_bytes()
    st = weights.stat()
    key = (str(weights), str(calibration), st.st_size, st.st_mtime_ns, hashlib.sha256(cal_bytes).hexdigest())
    if key not in _status_cache:
        _status_cache.clear()
        try:
            fitted = json.loads(cal_bytes.decode("utf-8")).get("weights_sha256")
        except (OSError, ValueError):
            fitted = None
        actual = hashlib.sha256(weights.read_bytes()).hexdigest()
        _status_cache[key] = (True, None) if fitted == actual else (
            False, f"calibration was fitted for other weights ({(fitted or 'none')[:12]}, not {actual[:12]}): refit it")
    return _status_cache[key]

FORMATS = [
    {
        "id": "statements",
        "title": "Bank statements",
        "inputs": ["CSV", "OFX / QFX", "MT940", "PDF (text layer)", "Scans (OCR)", "Wise statement"],
        "layouts": ["bank_csv.v1", "ofx.v1", "mt940.v1", "bank_statement_pdf.v1", "wise_statement.v1"],
        "extensions": [".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".xlsx"],
    },
    {
        "id": "gateways",
        "title": "Gateway settlements",
        "inputs": ["Stripe balance export", "Razorpay settlement", "PayPal activity"],
        "layouts": ["stripe_balance.v1", "razorpay_settlement.v1", "paypal_activity.v1"],
        "extensions": [".csv", ".xlsx"],
    },
    {
        "id": "tax",
        "title": "Tax documents",
        "inputs": ["Form 26AS (TDS)", "AIS", "FIRA", "Form 1099-B"],
        "layouts": ["tds_26as.v1", "ais.v1", "fira.v1", "form_1099b.v1"],
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
    ready, issue = model_status()
    if ready and importlib.util.find_spec("torch") is None:
        ready, issue = False, 'PyTorch is not installed (pip install "openbooks[scan]")'
    return {
        "status": "ok",
        "engine_version": engine_version(),
        "schema_version": SCHEMA_VERSION,
        "ocr_available": importlib.util.find_spec("easyocr") is not None,
        # true only when a --model run would load: weights, matching calibration and PyTorch all present
        "model_weights_present": ready,
        "model_issue": issue,
        "max_bytes": MAX_BYTES,
        "allowed_extensions": sorted(ALLOWED_EXT),
    }


# Layouts built from public descriptions of an export, with no real redacted sample tested yet (parsers_more.py).
UNVERIFIED = [
    {"layout": "paypal_activity.v1", "name": "PayPal activity"},
    {"layout": "wise_statement.v1", "name": "Wise statement"},
    {"layout": "form_1099b.v1", "name": "Form 1099-B"},
]


def formats() -> dict:
    return {"groups": FORMATS, "unverified": UNVERIFIED, "allowed_extensions": sorted(ALLOWED_EXT), "max_bytes": MAX_BYTES}


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
            from openbooks_lab.golden import build

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
            self._root, self._cases = None, {}  # a later lifespan (tests, reload) rebuilds instead of serving deleted paths
