"""The public export must stay free of private material, and must not be possible without a licence."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_public as ex  # noqa: E402


def test_the_public_set_has_no_private_material():
    assert ex.scan_tree(ex.build(None)) == []


def test_every_included_path_exists_and_nothing_private_is_included():
    files = ex.selected()
    assert files, "the include list matched nothing"
    private_prefixes = ("server/", "web/", "scripts/", "docs/", "packages/py/openbooks-lab/", "tests/characterise/", ".github/")
    assert not [f for f in files if f.startswith(private_prefixes)]
    assert "models/roles_manifest.json" not in files and not [f for f in files if "jepa" in f]


def test_the_scanner_catches_what_it_is_for():
    leaks = {"a.py": b"from openbooks_lab import synth", "b.md": b"see docs/evidence", "c.json": b'{"x": "pretrained on CORD"}',
             "d.py": b"path = 'C:\\\\Users\\\\someone'", "e.bin": b"\x00\x01"}
    hits = ex.scan_tree(leaks)
    for needle in ("a.py", "b.md", "c.json", "d.py", "e.bin"):
        assert any(h.startswith(needle) for h in hits), needle


def test_a_real_export_refuses_to_run_without_a_licence(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_public.py"), str(tmp_path / "out"), "--licence-file", str(tmp_path / "none")],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "licence" in r.stderr and not (tmp_path / "out").exists()


def test_the_weights_file_carries_no_private_strings():
    import zipfile

    z = zipfile.ZipFile(ROOT / "models" / "roles_head.pt")
    for info in z.infolist():
        if info.file_size > 1_000_000:
            continue  # tensor data
        data = z.read(info)
        for needle in (b"openbooks", b"lumeo", b"jepa", b"CORD", b"Users", b"train_roles"):
            assert needle not in data, (info.filename, needle)


def test_every_open_package_carries_the_same_apache_licence_text():
    master = (ROOT / "tools" / "public" / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in master and "Version 2.0, January 2004" in master and "END OF TERMS AND CONDITIONS" in master
    dirs = [d for d in (ROOT / "packages" / "py").iterdir() if d.is_dir() and d.name != "openbooks-lab"]
    dirs += [d for d in (ROOT / "packages" / "js").iterdir() if (d / "package.json").exists()]
    assert len(dirs) == 7  # the one Python package and the six npm packages
    for d in dirs:
        assert (d / "LICENSE").read_text(encoding="utf-8") == master, d.name


def test_open_packages_declare_apache_and_the_lab_stays_proprietary():
    import json
    import tomllib

    for d in (ROOT / "packages" / "py").iterdir():
        meta = tomllib.loads((d / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if d.name == "openbooks-lab":
            assert meta["license"] == "LicenseRef-Lumeo-Proprietary" and "Private :: Do Not Upload" in meta["classifiers"]
        else:
            assert meta["license"] == "Apache-2.0" and meta["license-files"] == ["LICENSE"], d.name
    for d in (ROOT / "packages" / "js").iterdir():
        if (d / "package.json").exists():
            assert json.loads((d / "package.json").read_text(encoding="utf-8"))["license"] == "Apache-2.0", d.name


def test_the_export_ships_the_licence_and_notice_at_the_root():
    files = ex.build((ROOT / "tools" / "public" / "LICENSE").read_bytes())
    assert b"Apache License" in files["LICENSE"][:200] and b"Lumeo" in files["NOTICE"]
    assert "LICENSE.md" not in files  # the private repository's scope note must not be exported
