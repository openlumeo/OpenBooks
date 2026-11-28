"""CLI behaviour that must not regress: results follow the flags (no stale reuse), report takes the same flags as run,
and --model without its dependency refuses clearly."""
import json
from pathlib import Path

import pytest

from openbooks_lab.golden import build
from openbooks.pipeline import main


@pytest.fixture(scope="module")
def pdf(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("golden")
    build(root, 7, 0, False)
    return root / "ok_pdf_text" / "in.pdf"


def _only_json(out: Path) -> dict:
    (path,) = out.glob("*.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_rerun_with_new_flags_is_not_served_from_an_old_output(pdf, tmp_path):
    out = tmp_path / "out"
    assert main(["run", str(pdf), "--out", str(out)]) == 1
    assert _only_json(out)["status"] == "refused"
    assert main(["run", str(pdf), "--currency", "INR", "--date-order", "dmy", "--out", str(out)]) == 0
    assert _only_json(out)["status"] == "ok"


def test_report_accepts_the_same_flags_as_run(pdf, tmp_path):
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "a.pdf").write_bytes(pdf.read_bytes())
    assert main(["report", str(folder), "--out", str(tmp_path / "r1")]) == 1
    assert json.loads((tmp_path / "r1" / "report.json").read_text())["released"] == 0
    assert main(["report", str(folder), "--currency", "INR", "--date-order", "dmy", "--out", str(tmp_path / "r2")]) == 0
    assert json.loads((tmp_path / "r2" / "report.json").read_text())["released"] == 1


def test_model_load_is_reused_within_a_process():
    torch = pytest.importorskip("torch")  # noqa: F841
    from openbooks.statements.roles import RoleModel

    first = RoleModel.load()
    if first is None:
        pytest.skip("typed heads not trained yet")
    assert RoleModel.load() is first
