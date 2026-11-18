"""Built-wheel checks: what ships, what it depends on, what it must never contain, and that clean environments behave.
Slow (builds wheels; the install tests need the network for third-party dependencies), so they run when OB_PACKAGING=1."""
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("OB_PACKAGING") != "1", reason="set OB_PACKAGING=1 to build and inspect wheels")

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ("openbooks-core", "openbooks-gateways", "openbooks-tax", "openbooks-statements", "openbooks-doctor", "openbooks")
CORE_FILES = {"__init__.py", "__main__.py", "_version.py", "builders.py", "cli.py", "errors.py", "evidence.py", "frontends/__init__.py",
              "frontends/xlsx.py", "gates.py", "grade.py", "guard.py", "normalise.py", "output.py", "params.py", "process.py",
              "py.typed", "registry.py", "report.py", "schema.py", "schema/openbooks.v1.refusal.schema.json",
              "schema/openbooks.v1.schema.json"}
GATEWAYS_FILES = {"__init__.py", "_version.py", "parsers.py", "py.typed"}
TAX_FILES = GATEWAYS_FILES | {"gates.py"}
STATEMENTS_FILES = {"__init__.py", "_version.py", "assets.py", "calibration.py", "encoder.py", "frontend.py", "gates.py", "labels.py",
                    "parsers.py", "pdf_backend.py", "pdf_front.py", "roles.py", "py.typed", "data/roles_head.pt", "data/roles_calibration.json",
                    "data/roles_model_card.json"}
DOCTOR_FILES = {"__init__.py", "__main__.py", "_version.py", "checks.py", "cli.py", "py.typed"}
META_FILES = {"pipeline.py"}
PRIVATE_NAMES = (b"openbooks_lab", b"lumeo_", b"lumeo-openbooks", b"jepa_encoder")


@pytest.fixture(scope="session")
def wheels(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    for pkg in PUBLIC:
        subprocess.run([sys.executable, "-m", "build", "-q", "--wheel", "--outdir", str(out), str(ROOT / "packages" / "py" / pkg)], check=True)
    found = {p.name.split("-")[0].replace("_", "-"): p for p in out.glob("*.whl")}
    assert set(found) == set(PUBLIC), found
    return {**found, "dir": out}


def names(wheel: Path, prefix: str) -> set[str]:
    return {n[len(prefix):] for n in zipfile.ZipFile(wheel).namelist() if n.startswith(prefix)}


def metadata(wheel: Path) -> list[str]:
    z = zipfile.ZipFile(wheel)
    return z.read(next(n for n in z.namelist() if n.endswith("METADATA"))).decode().splitlines()


def requires(wheel: Path) -> list[str]:
    return [l.split(": ", 1)[1] for l in metadata(wheel) if l.startswith("Requires-Dist") and "extra ==" not in l]


def entry_points_text(wheel: Path) -> str:
    z = zipfile.ZipFile(wheel)
    return z.read(next(n for n in z.namelist() if n.endswith("entry_points.txt"))).decode()


@pytest.mark.parametrize("dist,module,files", [("openbooks-core", "openbooks_core", CORE_FILES),
                                               ("openbooks-gateways", "openbooks_gateways", GATEWAYS_FILES),
                                               ("openbooks-tax", "openbooks_tax", TAX_FILES),
                                               ("openbooks-statements", "openbooks_statements", STATEMENTS_FILES),
                                               ("openbooks-doctor", "openbooks_doctor", DOCTOR_FILES),
                                               ("openbooks", "openbooks", META_FILES)])
def test_each_wheel_contains_exactly_the_allowed_files(wheels, dist, module, files):
    assert names(wheels[dist], module + "/") == files


def test_dependency_direction(wheels):
    assert [r.split(">")[0] for r in requires(wheels["openbooks-core"])] == ["jsonschema"]
    for dist in ("openbooks-gateways", "openbooks-tax", "openbooks-statements"):
        assert len(requires(wheels[dist])) == 1 and requires(wheels[dist])[0].startswith("openbooks-core[xlsx]"), dist
    assert len(requires(wheels["openbooks-doctor"])) == 1 and requires(wheels["openbooks-doctor"])[0].startswith("openbooks-core")
    meta = " ".join(requires(wheels["openbooks"]))
    for dep in ("openbooks-core", "openbooks-gateways", "openbooks-tax", "openbooks-statements", "openbooks-doctor"):
        assert dep in meta


def test_the_statements_base_install_is_pure_python_and_the_heavy_dependencies_are_extras(wheels):
    md = metadata(wheels["openbooks-statements"])
    extras = {l.split(": ")[1] for l in md if l.startswith("Provides-Extra")}
    assert extras == {"pdf", "scan"}
    scan = [l for l in md if "extra == 'scan'" in l]
    assert any("torch>=2.6" in l for l in scan), "PyTorch must be pinned to a release where weights_only loading is the default"


def test_the_weights_and_their_calibration_travel_together_and_match(wheels):
    z = zipfile.ZipFile(wheels["openbooks-statements"])
    weights = z.read("openbooks_statements/data/roles_head.pt")
    cal = json.loads(z.read("openbooks_statements/data/roles_calibration.json"))
    assert cal["weights_sha256"] == hashlib.sha256(weights).hexdigest()
    assert len(weights) < 25 * 1024 * 1024


def test_no_public_wheel_ships_tests_scripts_training_data_or_private_code(wheels):
    for dist in PUBLIC:
        z = zipfile.ZipFile(wheels[dist])
        for n in z.namelist():
            assert not n.startswith(("tests/", "scripts/", "models/", "docs/")) and not n.endswith(".pkl"), n
            if n.endswith(".pt"):
                assert n == "openbooks_statements/data/roles_head.pt", n
            if n.endswith((".py", ".toml", ".txt", ".json")):
                body = z.read(n)
                for banned in PRIVATE_NAMES:
                    assert banned not in body, f"{dist}: {n} mentions {banned!r}"


def test_every_known_layout_is_registered_by_exactly_one_wheel_and_its_owner(wheels):
    from openbooks_core.registry import KNOWN_LAYOUTS, KNOWN_SNIFFERS

    owners = {"openbooks-gateways": "openbooks-gateways", "openbooks-tax": "openbooks-tax", "openbooks-statements": "openbooks-statements"}
    texts = {d: entry_points_text(wheels[d]) for d in owners}
    for spec in [*KNOWN_LAYOUTS, *KNOWN_SNIFFERS]:
        found = [d for d, t in texts.items() if f"{spec.id} = " in t or f'"{spec.id}" = ' in t]
        assert found == [spec.distribution], (spec.id, found)
    assert "openbooks.layouts" not in zipfile.ZipFile(wheels["openbooks"]).read(
        next(n for n in zipfile.ZipFile(wheels["openbooks"]).namelist() if n.endswith("METADATA"))).decode()


def test_a_clean_environment_with_only_core_installs_one_dependency_and_refuses_everything(wheels, tmp_path):
    py = new_venv(tmp_path / "core")
    pip(py, wheels["openbooks-core"])
    assert installed(py) <= {"openbooks-core", "jsonschema", "jsonschema-specifications", "referencing", "rpds-py", "attrs", "typing-extensions"}
    info = json.loads(subprocess.run([py, "-m", "openbooks_core", "engine-info"], capture_output=True, text=True, check=True).stdout)
    assert info["layouts"] == [] and info["schema_version"] == "openbooks.v1"
    r = run_machine(py, tmp_path, "b.csv", BANK)
    assert r.returncode == 1 and json.loads(r.stdout.splitlines()[0])["code"] == "UNKNOWN_LAYOUT"


def test_statements_alone_release_a_bank_csv_without_pymupdf_or_torch_and_refuse_a_stripe_file(wheels, tmp_path):
    py = new_venv(tmp_path / "stm")
    pip(py, wheels["openbooks-statements"], find=wheels["dir"])
    assert installed(py).isdisjoint({"pymupdf", "torch", "easyocr", "numpy", "scipy"}), installed(py)
    r = run_machine(py, tmp_path, "b.csv", BANK, "s.csv", STRIPE)
    rows = [json.loads(x) for x in r.stdout.splitlines()]
    assert [(x["status"], x["code"]) for x in rows[:2]] == [("ok", None), ("refused", "UNKNOWN_LAYOUT")], r.stderr
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    p = subprocess.run([py, "-m", "openbooks_core", "run", str(pdf), "--out", str(tmp_path / "o2")], capture_output=True, text=True)
    assert p.returncode == 3 and "openbooks-statements[pdf]" in p.stderr


def test_core_plus_gateways_releases_a_stripe_file_and_refuses_a_bank_statement(wheels, tmp_path):
    py = new_venv(tmp_path / "gw")
    pip(py, wheels["openbooks-gateways"], find=wheels["dir"])
    r = run_machine(py, tmp_path, "s.csv", STRIPE, "b.csv", BANK)
    rows = [json.loads(x) for x in r.stdout.splitlines()]
    assert [(x["status"], x["code"]) for x in rows[:2]] == [("ok", None), ("refused", "UNKNOWN_LAYOUT")] and r.returncode == 1
    assert "stripe_balance.v1" in rows[-1]["engine"]["layouts"] and "bank_csv.v1" not in rows[-1]["engine"]["layouts"]


BANK = "Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,x,,5.00,1005.00\n"
STRIPE = "balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n"


def new_venv(path: Path) -> str:
    subprocess.run([sys.executable, "-m", "venv", str(path)], check=True)
    return str(path / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def pip(py: str, wheel: Path, find: Path | None = None) -> None:
    args = [py, "-m", "pip", "install", "-q", *(["--find-links", str(find)] if find else []), str(wheel)]
    subprocess.run(args, check=True)


def installed(py: str) -> set[str]:
    listed = json.loads(subprocess.run([py, "-m", "pip", "list", "--format=json"], capture_output=True, text=True, check=True).stdout)
    return {p["name"].lower().replace("_", "-") for p in listed} - {"pip"}


def run_machine(py: str, tmp: Path, *files_and_text: str):
    paths = []
    for name, text in zip(files_and_text[::2], files_and_text[1::2]):
        (tmp / name).write_text(text, encoding="utf-8")
        paths.append(str(tmp / name))
    return subprocess.run([py, "-m", "openbooks_core", "run", *paths, "--out", str(tmp / "o"), "--currency", "INR", "--opening", "1000",
                           "--machine"], capture_output=True, text=True)


def test_every_public_wheel_ships_the_apache_licence_and_declares_it(wheels):
    here = ROOT / "tools" / "public" / "LICENSE"
    master = (here if here.exists() else ROOT / "LICENSE").read_text(encoding="utf-8").splitlines()  # the private repo, or the export
    for dist in PUBLIC:
        z = zipfile.ZipFile(wheels[dist])
        lic = [n for n in z.namelist() if n.endswith("LICENSE") and ".dist-info/" in n]
        assert lic and z.read(lic[0]).decode("utf-8").splitlines() == master, dist
        assert "License-Expression: Apache-2.0" in metadata(wheels[dist]), dist
