"""The checks. Each returns a Check(id, status, detail, fix). Statuses: pass, warn (works, but worth knowing), fail (broken),
skip (not applicable). Doctor never opens a user's documents; its self-test uses small built-in fixtures only."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from decimal import Decimal
from importlib import metadata
from pathlib import Path

PASS, WARN, FAIL, SKIP = "pass", "warn", "fail", "skip"
MIN_PYTHON = (3, 11)
MIN_FREE_BYTES = 200 * 1024 * 1024


@dataclass
class Check:
    id: str
    status: str
    detail: str
    fix: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        if not d["fix"]:
            del d["fix"]
        return d


def _dist_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def check_python() -> Check:
    v = sys.version_info[:3]
    ok = v >= MIN_PYTHON
    return Check("python.version", PASS if ok else FAIL, f"Python {'.'.join(map(str, v))}",
                 "" if ok else f"Open Books needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer")


def check_core() -> list[Check]:
    try:
        import openbooks_core as core
    except Exception as e:  # noqa: BLE001
        return [Check("core.import", FAIL, f"{type(e).__name__}: {e}", "pip install openbooks-core")]
    out = [Check("core.import", PASS, f"openbooks-core {core.__version__}, contract {core.SCHEMA_VERSION}, layout API {core.LAYOUT_API_VERSION}")]
    try:
        from openbooks_core import load_schema

        load_schema("output"), load_schema("refusal")
        out.append(Check("core.schema", PASS, "output and refusal schemas load"))
    except Exception as e:  # noqa: BLE001
        out.append(Check("core.schema", FAIL, f"{type(e).__name__}: {e}", "reinstall openbooks-core"))
    return out


def check_versions() -> Check:
    core = _dist_version("openbooks-core")
    if core is None:
        return Check("versions.lockstep", SKIP, "openbooks-core is not installed")
    minor = ".".join(core.split(".")[:2])
    others = {n: _dist_version(n) for n in ("openbooks-gateways", "openbooks-tax", "openbooks-statements", "openbooks-doctor", "openbooks")}
    skewed = {n: v for n, v in others.items() if v and ".".join(v.split(".")[:2]) != minor}
    if skewed:
        return Check("versions.lockstep", WARN, f"core is {core} but {', '.join(f'{n} {v}' for n, v in skewed.items())}",
                     f"install matching versions: pip install 'openbooks-core=={core}' and the same release of the others")
    return Check("versions.lockstep", PASS, f"core {core}; installed providers: " + (", ".join(f"{n} {v}" for n, v in others.items() if v) or "none"))


def check_registry(registry=None) -> tuple[list[Check], object | None]:
    """Discovery plus actually importing every installed provider, so a broken one is found here and not in the middle of a run."""
    from openbooks_core.errors import EngineFault
    from openbooks_core.registry import KNOWN_LAYOUTS, KNOWN_SNIFFERS, Registry

    try:
        reg = registry or Registry.discover()
        problems = []
        for lid in sorted(reg.installed_layouts()):
            try:
                (reg.sniffer_parser if lid in {s.id for s in KNOWN_SNIFFERS} else reg.layout_parser)(lid)
            except EngineFault as e:
                problems.append(str(e))
        try:
            reg.gates()
        except EngineFault as e:
            problems.append(str(e))
        for name in ("document",):
            try:
                reg.frontend(name)
            except EngineFault as e:
                problems.append(str(e))
            except Exception:  # noqa: BLE001 - a missing frontend is not a fault; the coverage check reports it
                pass
    except EngineFault as e:
        return [Check("registry.load", FAIL, str(e), "pip install --force-reinstall the package that registers it (or uninstall it)")], None
    if problems:
        return [Check("registry.load", FAIL, "; ".join(problems), "reinstall the provider named above, or uninstall it")], reg
    out = [Check("registry.load", PASS, f"{len(reg.installed_layouts())} layouts load")]
    missing = [(s.id, s.distribution) for s in [*KNOWN_LAYOUTS, *KNOWN_SNIFFERS] if s.id not in reg.installed_layouts()]
    if missing:
        dists = sorted({d for _, d in missing})
        out.append(Check("registry.coverage", WARN, f"{len(missing)} known layouts have no provider: " + ", ".join(i for i, _ in missing),
                         "pip install " + " ".join(dists) + " (files of these layouts are refused until then; they are never guessed)"))
    else:
        out.append(Check("registry.coverage", PASS, "every known layout has a provider"))
    return out, reg


def check_pdf() -> Check:
    if _dist_version("openbooks-statements") is None:
        return Check("pdf.pymupdf", SKIP, "openbooks-statements is not installed")
    if importlib.util.find_spec("fitz") is None:
        return Check("pdf.pymupdf", WARN, "PyMuPDF is not installed: PDF and image statements cannot be read",
                     "pip install 'openbooks-statements[pdf]'")
    try:
        import fitz  # noqa: F401
    except Exception as e:  # noqa: BLE001 - installed but its native library cannot load (e.g. blocked by a security policy)
        return Check("pdf.pymupdf", FAIL, f"PyMuPDF is installed but does not load: {type(e).__name__}: {e}",
                     "reinstall PyMuPDF; if a security policy blocks it, PDF statements cannot be read here")
    return Check("pdf.pymupdf", PASS, "PyMuPDF imports")


def check_scan(deep: bool) -> list[Check]:
    if _dist_version("openbooks-statements") is None:
        return [Check("scan.dependencies", SKIP, "openbooks-statements is not installed")]
    have = {m: importlib.util.find_spec(m) is not None for m in ("torch", "easyocr", "PIL", "numpy")}
    miss = [m for m, ok in have.items() if not ok]
    out = [Check("scan.dependencies", PASS if not miss else WARN,
                 "OCR and typed-head dependencies present" if not miss else "missing: " + ", ".join(miss),
                 "" if not miss else "pip install 'openbooks-statements[scan]' (only needed for scans and --model)")]
    if have["torch"] and deep:
        import torch

        v = tuple(int(x) for x in torch.__version__.split("+")[0].split(".")[:2])
        out.append(Check("scan.torch", PASS if v >= (2, 6) else FAIL, f"PyTorch {torch.__version__}; CUDA {'available' if torch.cuda.is_available() else 'not available (CPU)'}",
                         "" if v >= (2, 6) else "weights_only loading needs PyTorch 2.6 or newer: pip install -U torch"))
    return out


def check_model(deep: bool) -> list[Check]:
    if _dist_version("openbooks-statements") is None:
        return [Check("model.assets", SKIP, "openbooks-statements is not installed")]
    from openbooks_statements.assets import CALIBRATION_NAME, MODELS_DIR, WEIGHTS_NAME

    w, c = MODELS_DIR / WEIGHTS_NAME, MODELS_DIR / CALIBRATION_NAME
    if not w.exists() or not c.exists():
        return [Check("model.assets", WARN, f"no model assets in {MODELS_DIR}: --model is refused", "reinstall openbooks-statements, or set OPENBOOKS_MODELS_DIR")]
    try:
        fitted = json.loads(c.read_text(encoding="utf-8")).get("weights_sha256")
    except (OSError, ValueError) as e:
        return [Check("model.integrity", FAIL, f"calibration unreadable: {e}", "reinstall openbooks-statements")]
    actual = hashlib.sha256(w.read_bytes()).hexdigest()
    if fitted != actual:
        return [Check("model.integrity", FAIL, f"calibration was fitted for weights {str(fitted)[:12]}, but the weights are {actual[:12]}",
                      "the weights or the calibration was replaced or corrupted: reinstall openbooks-statements")]
    out = [Check("model.integrity", PASS, f"weights {actual[:12]} match their calibration")]
    card = MODELS_DIR / "roles_model_card.json"
    if card.exists():
        try:
            ok = json.loads(card.read_text(encoding="utf-8")).get("weights_sha256") == actual
        except (OSError, ValueError):
            ok = False
        out.append(Check("model.card", PASS if ok else WARN, "model card matches the weights" if ok else "model card does not match the weights",
                         "" if ok else "reinstall openbooks-statements"))
    if deep:
        if importlib.util.find_spec("torch") is None:
            out.append(Check("model.load", SKIP, "PyTorch is not installed"))
        else:
            try:
                from openbooks_statements.roles import RoleModel

                RoleModel._loaded.clear()
                ident = RoleModel.load().identity
                out.append(Check("model.load", PASS, f"loads with weights_only=True; identity {ident['weights_sha256'][:12]}"))
            except Exception as e:  # noqa: BLE001
                out.append(Check("model.load", FAIL, f"{type(e).__name__}: {e}", "reinstall openbooks-statements and PyTorch >= 2.6"))
    return out


BANK = "Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n01/01/2026,Salary,,500.00,1500.00\n02/01/2026,Rent,200.50,,1299.50\n"
STRIPE = "balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n"
TDS = ("Deductor Name,TAN,Section,Transaction Date,Amount Paid/Credited,Tax Deducted,TDS Deposited\n"
       "Acme Ltd,MUMA12345B,194C,15/04/2025,100000.00,2000.00,2000.00\nTotal,,,,100000.00,2000.00,2000.00\n")
MT940 = ":20:S1\n:25:123\n:60F:C260101INR1000,00\n:61:2601050105C500,00NTRFNONREF//B1\n:86:Salary\n:62F:C260105INR1500,00\n"
# (layout the case needs, file extension, good text, tampered text, params)
SELF_TEST = [
    ("bank_csv.v1", "csv", BANK, BANK.replace("1299.50", "1299.51"), {"currency": "INR", "opening": Decimal("1000.00")}),
    ("mt940.v1", "sta", MT940, MT940.replace("1500,00", "1500,01"), {}),
    ("stripe_balance.v1", "csv", STRIPE, STRIPE.replace("96.80", "96.81"), {}),
    ("tds_26as.v1", "csv", TDS, TDS.replace("2000.00,2000.00\nTotal", "2000.00,2000.00\nTotal").replace("Total,,,,100000.00,2000.00,2000.00", "Total,,,,100000.00,2000.01,2000.00"), {}),
]


def check_self_test(reg) -> list[Check]:
    """Balanced built-in documents must release and their tampered twins must refuse, for every layout that is installed."""
    from openbooks_core import Params, process

    if reg is None:
        return [Check("selftest", SKIP, "the registry did not load")]
    out, ran = [], 0
    with tempfile.TemporaryDirectory(prefix="openbooks-doctor-") as tmp:
        for layout, ext, good, bad, params in SELF_TEST:
            if layout not in reg.installed_layouts():
                continue
            ran += 1
            p = Params(**params)
            for label, text, want in (("balanced", good, "ok"), ("tampered", bad, "refused")):
                f = Path(tmp) / f"{layout}-{label}.{ext}"
                f.write_text(text, encoding="utf-8")
                doc = process(f, p, registry=reg)
                if doc["status"] != want:
                    sev = "FALSE ACCEPT: a tampered document was released" if want == "refused" else "a balanced document was not released"
                    out.append(Check(f"selftest.{layout}", FAIL, f"{label}: {sev} ({doc.get('error', {}).get('code') or doc['status']})",
                                     "this installation does not satisfy the proven-or-refused guarantee; reinstall and report it"))
                    break
            else:
                out.append(Check(f"selftest.{layout}", PASS, "balanced document released, tampered twin refused"))
    return out or [Check("selftest", SKIP, "no layout with a built-in self-test is installed")]


def check_environment() -> list[Check]:
    out = []
    try:
        with tempfile.TemporaryDirectory(prefix="openbooks-doctor-") as tmp:
            Path(tmp, "w").write_text("x")
            free = shutil.disk_usage(tmp).free
        out.append(Check("env.tempdir", PASS if free >= MIN_FREE_BYTES else WARN,
                         f"temp directory writable, {free // (1024 * 1024)} MB free",
                         "" if free >= MIN_FREE_BYTES else "less than 200 MB free: large PDFs and OCR may fail"))
    except OSError as e:
        out.append(Check("env.tempdir", FAIL, f"cannot write to the temp directory: {e}", "set TMPDIR/TEMP to a writable directory"))
    return out


def run_checks(*, deep: bool = False, registry=None) -> list[Check]:
    checks = [check_python(), *check_core()]
    if any(c.id == "core.import" and c.status == FAIL for c in checks):
        return checks
    checks.append(check_versions())
    reg_checks, reg = check_registry(registry)
    checks += reg_checks
    checks += [check_pdf(), *check_scan(deep), *check_model(deep), *check_self_test(reg), *check_environment()]
    return checks
