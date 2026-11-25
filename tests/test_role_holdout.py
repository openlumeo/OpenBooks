import json
import subprocess
import sys

import pytest

from scripts.freeze_role_holdout import build_manifest


@pytest.fixture
def roster(tmp_path):
    entries = []
    for name, split, source, layout in (
        ("dev", "development", "issuer/1", "template-a"),
        ("digital", "holdout", "issuer/2", "template-b"),
        ("scan", "holdout", "issuer/2", "template-b"),
    ):
        (tmp_path / f"{name}.pdf").write_bytes(f"%PDF test fixture {name}".encode())
        entries.append(dict(id=name, split=split, source_document=source, layout=layout,
                            pdf=f"{name}.pdf", truth="truth.json"))
    (tmp_path / "truth.json").write_text(json.dumps({
        "outcome": "released", "adjudication": "review-1",
        "transactions": [{"date": "2025-02-01", "direction": "debit", "amount": "2.00", "balance": "-1.00"}],
    }), encoding="utf-8")
    path = tmp_path / "roster.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path, entries


@pytest.mark.parametrize("key, value, error", [
    ("source_document", "issuer/1", "overlapping source_document"),
    ("layout", " Template-A ", "overlapping layout"),
    ("pdf", "dev.pdf", "duplicate PDF bytes"),
    ("truth", "missing.json", "invalid .json asset"),
    ("currency", "inr", "invalid currency"),
])
def test_invalid_holdout(roster, key, value, error):
    path, entries = roster
    entries[-1][key] = value
    path.write_text(json.dumps(entries), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        build_manifest(path)


def test_freeze_and_verify(roster):
    path, _ = roster
    manifest = path.with_name("frozen.json")
    command = [sys.executable, "-m", "scripts.freeze_role_holdout", str(path), str(manifest)]
    subprocess.run(command, check=True, capture_output=True)
    subprocess.run([*command, "--verify"], check=True, capture_output=True)
    frozen = json.loads(manifest.read_bytes())["documents"]
    assert frozen["digital"]["source_document"] == frozen["scan"]["source_document"]
    assert frozen["digital"]["pdf_sha256"] != frozen["scan"]["pdf_sha256"]
    assert subprocess.run(command, capture_output=True).returncode == 1

    truth = path.with_name("truth.json")
    truth.write_bytes(truth.read_bytes() + b"\n")
    changed = subprocess.run([*command, "--verify"], capture_output=True, text=True)
    assert changed.returncode == 1
    assert "differs from the frozen manifest" in changed.stderr


def test_holdout_requires_release_labels(roster):
    path, _ = roster
    truth = path.with_name("truth.json")
    truth.write_text(json.dumps({"outcome": "released", "adjudication": "review-1", "transactions": None}),
                     encoding="utf-8")
    with pytest.raises(ValueError, match="expected reference transactions"):
        build_manifest(path)
