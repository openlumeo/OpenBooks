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
# Modules that must not reach a public distribution. Until the provider packages are split out, openbooks still carries them.
PRIVATE_MODULES = {"synth.py", "golden.py", "golden_docs.py", "bitenc.py", "link.py"}


@pytest.fixture(scope="session")
def wheels(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    for pkg in ("openbooks-core", "openbooks"):
        subprocess.run([sys.executable, "-m", "build", "-q", "--wheel", "--outdir", str(out), str(ROOT / "packages" / "py" / pkg)], check=True)
    return {"core": next(out.glob("openbooks_core-*.whl")), "meta": next(out.glob("openbooks-*.whl")), "dir": out}


def names(wheel: Path, prefix: str) -> set[str]:
    return {n[len(prefix):] for n in zipfile.ZipFile(wheel).namelist() if n.startswith(prefix)}


def metadata(wheel: Path) -> str:
    z = zipfile.ZipFile(wheel)
    return z.read(next(n for n in z.namelist() if n.endswith("METADATA"))).decode()


def test_core_wheel_contains_exactly_the_allowed_files(wheels):
    assert names(wheels["core"], "openbooks_core/") == CORE_FILES


def test_core_depends_only_on_jsonschema(wheels):
    reqs = [l.split(": ", 1)[1] for l in metadata(wheels["core"]).splitlines() if l.startswith("Requires-Dist")]
    assert len(reqs) == 1 and reqs[0].startswith("jsonschema")


def test_no_wheel_ships_tests_scripts_or_model_files(wheels):
    for w in (wheels["core"], wheels["meta"]):
        for n in zipfile.ZipFile(w).namelist():
            assert not n.startswith(("tests/", "scripts/", "models/", "docs/")) and not n.endswith((".pt", ".pkl")), n


@pytest.mark.xfail(reason="interim: the training/matching modules leave the openbooks distribution when the provider packages are split out",
                   strict=True)
def test_the_meta_package_ships_no_private_module(wheels):
    assert not (names(wheels["meta"], "openbooks/") & PRIVATE_MODULES)


def test_the_meta_package_registers_every_known_layout(wheels):
    z = zipfile.ZipFile(wheels["meta"])
    eps = z.read(next(n for n in z.namelist() if n.endswith("entry_points.txt"))).decode()
    from openbooks_core.registry import KNOWN_LAYOUTS, KNOWN_SNIFFERS

    for lid in [s.id for s in KNOWN_LAYOUTS] + [s.id for s in KNOWN_SNIFFERS]:
        assert f"{lid} = " in eps or f'"{lid}" = ' in eps, lid


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
