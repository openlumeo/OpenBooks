"""Built-wheel checks: what ships, what it depends on, and that a clean environment behaves. Slow (builds wheels, and the
install test needs the network for jsonschema), so they run when OB_PACKAGING=1 (CI sets it)."""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("OB_PACKAGING") != "1", reason="set OB_PACKAGING=1 to build and inspect wheels")

ROOT = Path(__file__).resolve().parents[2]
CORE_FILES = {"__init__.py", "__main__.py", "_version.py", "builders.py", "cli.py", "errors.py", "evidence.py", "frontends/__init__.py",
              "frontends/xlsx.py", "gates.py", "grade.py", "guard.py", "normalise.py", "output.py", "params.py", "process.py",
              "py.typed", "registry.py", "report.py", "schema.py", "schema/openbooks.v1.refusal.schema.json",
              "schema/openbooks.v1.schema.json"}
GATEWAYS_FILES = {"__init__.py", "_version.py", "parsers.py", "py.typed"}
TAX_FILES = GATEWAYS_FILES | {"gates.py"}
# Modules that must not reach a public distribution. Until the provider packages are split out, openbooks still carries them.
PRIVATE_MODULES = {"synth.py", "golden.py", "golden_docs.py", "bitenc.py", "link.py"}


@pytest.fixture(scope="session")
def wheels(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    for pkg in ("openbooks-core", "openbooks-gateways", "openbooks-tax", "openbooks"):
        subprocess.run([sys.executable, "-m", "build", "-q", "--wheel", "--outdir", str(out), str(ROOT / "packages" / "py" / pkg)], check=True)
    return {"core": next(out.glob("openbooks_core-*.whl")), "gateways": next(out.glob("openbooks_gateways-*.whl")), "tax": next(out.glob("openbooks_tax-*.whl")),
            "meta": next(out.glob("openbooks-0*.whl")), "dir": out}


def names(wheel: Path, prefix: str) -> set[str]:
    return {n[len(prefix):] for n in zipfile.ZipFile(wheel).namelist() if n.startswith(prefix)}


def metadata(wheel: Path) -> str:
    z = zipfile.ZipFile(wheel)
    return z.read(next(n for n in z.namelist() if n.endswith("METADATA"))).decode()


def test_core_wheel_contains_exactly_the_allowed_files(wheels):
    assert names(wheels["core"], "openbooks_core/") == CORE_FILES


def test_gateways_wheel_contains_exactly_the_allowed_files_and_depends_only_on_core(wheels):
    assert names(wheels["gateways"], "openbooks_gateways/") == GATEWAYS_FILES
    reqs = [l.split(": ", 1)[1] for l in metadata(wheels["gateways"]).splitlines() if l.startswith("Requires-Dist")]
    assert len(reqs) == 1 and reqs[0].startswith("openbooks-core")


def test_tax_wheel_contains_exactly_the_allowed_files_and_depends_only_on_core(wheels):
    assert names(wheels["tax"], "openbooks_tax/") == TAX_FILES
    reqs = [l.split(": ", 1)[1] for l in metadata(wheels["tax"]).splitlines() if l.startswith("Requires-Dist")]
    assert len(reqs) == 1 and reqs[0].startswith("openbooks-core")


def test_core_depends_only_on_jsonschema(wheels):
    reqs = [l.split(": ", 1)[1] for l in metadata(wheels["core"]).splitlines() if l.startswith("Requires-Dist")]
    assert len(reqs) == 1 and reqs[0].startswith("jsonschema")


def test_no_wheel_ships_tests_scripts_or_model_files(wheels):
    for w in (wheels["core"], wheels["gateways"], wheels["tax"], wheels["meta"]):
        for n in zipfile.ZipFile(w).namelist():
            assert not n.startswith(("tests/", "scripts/", "models/", "docs/")) and not n.endswith((".pt", ".pkl")), n


@pytest.mark.xfail(reason="interim: the training/matching modules leave the openbooks distribution when the provider packages are split out",
                   strict=True)
def test_the_meta_package_ships_no_private_module(wheels):
    assert not (names(wheels["meta"], "openbooks/") & PRIVATE_MODULES)


def entry_points_text(wheel: Path) -> str:
    z = zipfile.ZipFile(wheel)
    return z.read(next(n for n in z.namelist() if n.endswith("entry_points.txt"))).decode()


def test_every_known_layout_is_registered_by_exactly_one_wheel_and_providers_own_their_layouts(wheels):
    from openbooks_core.registry import KNOWN_LAYOUTS, KNOWN_SNIFFERS

    texts = {k: entry_points_text(wheels[k]) for k in ("gateways", "tax", "meta")}
    for lid in [s.id for s in KNOWN_LAYOUTS] + [s.id for s in KNOWN_SNIFFERS]:
        owners = [k for k, t in texts.items() if f"{lid} = " in t or f'"{lid}" = ' in t]
        assert len(owners) == 1, (lid, owners)
    for spec in KNOWN_LAYOUTS:
        for dist, key in (("openbooks-gateways", "gateways"), ("openbooks-tax", "tax")):
            if spec.distribution == dist:
                assert f"{spec.id} = " in texts[key], spec.id


def test_a_clean_environment_with_only_core_installs_one_dependency_and_refuses_everything(wheels, tmp_path):
    venv = tmp_path / "v"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    py = str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    subprocess.run([py, "-m", "pip", "install", "-q", str(wheels["core"])], check=True)
    listed = json.loads(subprocess.run([py, "-m", "pip", "list", "--format=json"], capture_output=True, text=True, check=True).stdout)
    pkgs = {p["name"].lower().replace("_", "-") for p in listed} - {"pip"}
    assert pkgs <= {"openbooks-core", "jsonschema", "jsonschema-specifications", "referencing", "rpds-py", "attrs", "typing-extensions"}, pkgs
    info = json.loads(subprocess.run([py, "-m", "openbooks_core", "engine-info"], capture_output=True, text=True, check=True).stdout)
    assert info["layouts"] == [] and info["schema_version"] == "openbooks.v1"
    f = tmp_path / "in.csv"
    f.write_text("Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,x,,5.00,1005.00\n", encoding="utf-8")
    r = subprocess.run([py, "-m", "openbooks_core", "run", str(f), "--out", str(tmp_path / "o"), "--currency", "INR", "--opening", "1000", "--machine"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and json.loads(r.stdout.splitlines()[0])["code"] == "UNKNOWN_LAYOUT"


def test_core_plus_gateways_releases_a_stripe_file_and_refuses_a_bank_statement(wheels, tmp_path):
    venv = tmp_path / "v2"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    py = str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    subprocess.run([py, "-m", "pip", "install", "-q", "--find-links", str(wheels["dir"]), str(wheels["gateways"])], check=True)
    stripe = tmp_path / "s.csv"
    stripe.write_text("balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n", encoding="utf-8")
    bank = tmp_path / "b.csv"
    bank.write_text("Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,x,,5.00,1005.00\n", encoding="utf-8")
    r = subprocess.run([py, "-m", "openbooks_core", "run", str(stripe), str(bank), "--out", str(tmp_path / "o"), "--currency", "INR",
                        "--opening", "1000", "--machine"], capture_output=True, text=True)
    rows = [json.loads(x) for x in r.stdout.splitlines()]
    assert [(x["status"], x["code"]) for x in rows[:2]] == [("ok", None), ("refused", "UNKNOWN_LAYOUT")] and r.returncode == 1
    assert "stripe_balance.v1" in rows[-1]["engine"]["layouts"] and "bank_csv.v1" not in rows[-1]["engine"]["layouts"]
