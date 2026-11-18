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
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_public.py"), str(tmp_path / "out")], capture_output=True, text=True)
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
