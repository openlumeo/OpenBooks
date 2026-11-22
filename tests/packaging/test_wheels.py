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
PUBLIC = ("openbooks",)
CORE_FILES = {"__init__.py", "__main__.py", "builders.py", "cli.py", "errors.py", "evidence.py", "frontends/__init__.py",
              "frontends/xlsx.py", "gates.py", "grade.py", "guard.py", "normalise.py", "output.py", "params.py", "process.py",
              "py.typed", "registry.py", "report.py", "schema.py", "schema/openbooks.v1.refusal.schema.json",
              "schema/openbooks.v1.schema.json"}
GATEWAYS_FILES = {"__init__.py", "parsers.py", "py.typed"}
TAX_FILES = GATEWAYS_FILES | {"gates.py"}
STATEMENTS_FILES = {"__init__.py", "assets.py", "calibration.py", "encoder.py", "frontend.py", "gates.py", "labels.py",
                    "parsers.py", "pdf_backend.py", "pdf_front.py", "pdf_words.py", "scan_decimals.py", "table_header.py", "roles.py", "py.typed", "data/roles_head.pt", "data/roles_calibration.json",
                    "data/roles_model_card.json"}
DOCTOR_FILES = {"__init__.py", "__main__.py", "checks.py", "cli.py", "py.typed"}
TOP_FILES = {"__init__.py", "__main__.py", "_version.py", "pipeline.py"}
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


def test_the_wheel_contains_exactly_the_allowed_files(wheels):
    expected = TOP_FILES | {f"{part}/{f}" for part, files in (("core", CORE_FILES), ("gateways", GATEWAYS_FILES), ("tax", TAX_FILES),
                                                              ("statements", STATEMENTS_FILES), ("doctor", DOCTOR_FILES)) for f in files}
    assert names(wheels["openbooks"], "openbooks/") == expected


def test_the_base_install_reads_every_layout_and_pdfs_and_the_heavy_dependencies_are_an_extra(wheels):
    assert sorted(r.split(">")[0].split("=")[0] for r in requires(wheels["openbooks"])) == ["jsonschema", "openpyxl", "pypdfium2"]
    md = metadata(wheels["openbooks"])
    assert {l.split(": ")[1] for l in md if l.startswith("Provides-Extra")} == {"scan"}
    scan = [l for l in md if "extra == 'scan'" in l]
    assert any("torch>=2.6" in l for l in scan), "PyTorch must be pinned to a release where weights_only loading is the default"


def test_the_weights_and_their_calibration_travel_together_and_match(wheels):
    z = zipfile.ZipFile(wheels["openbooks"])
    weights = z.read("openbooks/statements/data/roles_head.pt")
    cal = json.loads(z.read("openbooks/statements/data/roles_calibration.json"))
    assert cal["weights_sha256"] == hashlib.sha256(weights).hexdigest()
    assert len(weights) < 25 * 1024 * 1024


def test_the_wheel_ships_no_tests_scripts_training_data_or_private_code(wheels):
    for dist in PUBLIC:
        z = zipfile.ZipFile(wheels[dist])
        for n in z.namelist():
            assert not n.startswith(("tests/", "scripts/", "models/", "docs/")) and not n.endswith(".pkl"), n
            if n.endswith(".pt"):
                assert n == "openbooks/statements/data/roles_head.pt", n
            if n.endswith((".py", ".toml", ".txt", ".json")):
                body = z.read(n)
                for banned in PRIVATE_NAMES:
                    assert banned not in body, f"{dist}: {n} mentions {banned!r}"


def test_every_known_layout_is_registered_once_by_the_provider_that_owns_it(wheels):
    from openbooks.core.registry import KNOWN_LAYOUTS, KNOWN_SNIFFERS

    lines = [l.strip() for l in entry_points_text(wheels["openbooks"]).splitlines()]
    for spec in [*KNOWN_LAYOUTS, *KNOWN_SNIFFERS]:
        found = [l for l in lines if l.startswith((f"{spec.id} = ", f'"{spec.id}" = '))]
        assert len(found) == 1 and found[0].split(" = ")[1].startswith(spec.distribution + "."), (spec.id, found)


def test_a_clean_environment_releases_every_family_and_runs_doctor(wheels, tmp_path):
    py = new_venv(tmp_path / "env")
    pip(py, wheels["openbooks"])
    assert installed(py).isdisjoint({"pymupdf", "torch", "easyocr", "numpy", "scipy", "openbooks-core"}), installed(py)
    info = json.loads(subprocess.run([py, "-m", "openbooks", "engine-info"], capture_output=True, text=True, check=True).stdout)
    assert info["name"] == "openbooks" and info["schema_version"] == "openbooks.v1" and len(info["layouts"]) == 12
    r = run_machine(py, tmp_path, "b.csv", BANK, "s.csv", STRIPE)
    rows = [json.loads(x) for x in r.stdout.splitlines()]
    assert [(x["status"], x["code"]) for x in rows[:2]] == [("ok", None), ("ok", None)] and r.returncode == 0, r.stderr
    d = subprocess.run([py, "-m", "openbooks", "doctor", "--json"], capture_output=True, text=True)
    checks = {c["id"]: c["status"] for c in json.loads(d.stdout)["checks"]}
    assert checks["registry.coverage"] == "pass" and checks["pdf.backend"] == "pass" and checks["install.retired"] == "pass", d.stdout


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
    return subprocess.run([py, "-m", "openbooks", "run", *paths, "--out", str(tmp / "o"), "--currency", "INR", "--opening", "1000",
                           "--machine"], capture_output=True, text=True)


def test_every_public_wheel_ships_the_apache_licence_and_declares_it(wheels):
    here = ROOT / "tools" / "public" / "LICENSE"
    master = (here if here.exists() else ROOT / "LICENSE").read_text(encoding="utf-8").splitlines()
    for dist in PUBLIC:
        z = zipfile.ZipFile(wheels[dist])
        lic = [n for n in z.namelist() if n.endswith("LICENSE") and ".dist-info/" in n]
        assert lic and z.read(lic[0]).decode("utf-8").splitlines() == master, dist
        assert "License-Expression: Apache-2.0" in metadata(wheels[dist]), dist
