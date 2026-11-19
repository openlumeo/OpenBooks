"""What the engine can read, whether it is healthy, and the synthetic sample files.

FORMATS is the human-readable grouping shown in the web app. It is written by hand, so
tests/test_server.py checks it against every layout id the engine source can emit: adding a
parser without listing it here (or listing one that does not exist) fails the build.
"""
from __future__ import annotations

import importlib.util
import io
import json
from functools import cached_property
from importlib import resources
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from zipfile import ZipFile

from openbooks.pipeline import ALLOWED_EXT, MAX_BYTES, SCHEMA_VERSION
from openbooks.core.errors import PluginLoadError
from openbooks.core.registry import default_registry
from openbooks.statements.assets import CALIBRATION_NAME, MODELS_DIR, WEIGHTS_NAME, ModelUnavailable

WEIGHTS = MODELS_DIR / WEIGHTS_NAME
CALIBRATION = MODELS_DIR / CALIBRATION_NAME


def load_model(weights: Path = WEIGHTS, calibration: Path = CALIBRATION):
    try:
        if not weights.is_file():
            raise ModelUnavailable(f"Missing model weights ({WEIGHTS_NAME}). Check OPENBOOKS_MODELS_DIR.")
        if not calibration.is_file():
            raise ModelUnavailable(f"Missing model calibration ({CALIBRATION_NAME}). Check OPENBOOKS_MODELS_DIR.")
        from openbooks.statements.roles import RoleModel
    except (ImportError, OSError, RuntimeError) as e:
        raise ModelUnavailable('Cannot import the model runtime. Install or repair "openbooks[scan]".') from e
    model = RoleModel.load(weights, calibration)
    if model is None:
        raise ModelUnavailable("The model assets disappeared during loading. Check OPENBOOKS_MODELS_DIR.")
    return model


def model_status() -> dict:
    try:
        model = load_model()
    except ModelUnavailable as e:
        return {"model_ready": False, "model_issue": e.message, "model_identity": None}
    return {"model_ready": True, "model_issue": None, "model_identity": model.identity}


def installed_linker():
    try:
        return default_registry().linker()
    except PluginLoadError:
        return None

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
    model = model_status()
    return {
        "status": "ok",
        "engine_version": engine_version(),
        "schema_version": SCHEMA_VERSION,
        "ocr_available": importlib.util.find_spec("easyocr") is not None,
        **model,
        "model_weights_present": model["model_ready"],  # compatibility with older clients
        "link_available": installed_linker() is not None,
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
    """The synthetic corpus packaged with the server."""

    @cached_property
    def _archive(self) -> bytes:
        return resources.files("openbooks_server").joinpath("samples.zip").read_bytes()

    @cached_property
    def _cases(self) -> dict[str, dict]:
        cases = {}
        labels = dict(FEATURED)
        order = {cid: i for i, (cid, _) in enumerate(FEATURED)}
        with ZipFile(io.BytesIO(self._archive)) as archive:
            for name in archive.namelist():
                case_id, filename = name.split("/")
                if filename == "expected.json":
                    continue
                exp = json.loads(archive.read(f"{case_id}/expected.json"))
                code = exp.get("code")
                cases[case_id] = {
                    "id": case_id,
                    "filename": f"{case_id}{Path(filename).suffix}",
                    "label": labels.get(case_id, case_id.replace("_", " ")),
                    "featured": case_id in labels,
                    "rank": order.get(case_id, len(order)),
                    "expect_status": exp["status"],
                    "expect_code": code[0] if isinstance(code, list) else code,
                    "params": exp.get("params", {}),
                    "_path": name,
                }
        return cases

    def list(self) -> list[dict]:
        cases = sorted(self._cases.values(), key=lambda c: (c["rank"], c["id"]))
        return [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases]

    def get(self, case_id: str) -> tuple[str, bytes] | None:
        c = self._cases.get(case_id)
        if c is None:
            return None
        with ZipFile(io.BytesIO(self._archive)) as archive:
            return c["filename"], archive.read(c["_path"])
