"""Model integrity: the calibration is bound to its weights, and a --model release names the model that checked it."""
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("torch")

from openbooks_lab.golden import build  # noqa: E402
from openbooks.pipeline import Params, Refusal, process, validate_output  # noqa: E402
from openbooks_statements.roles import CALIBRATION, WEIGHTS, RoleModel  # noqa: E402

pytestmark = pytest.mark.skipif(not (WEIGHTS.exists() and CALIBRATION.exists()), reason="typed heads not trained yet")


def _copy(tmp_path: Path, calibration: dict | None = None) -> tuple[Path, Path]:
    w, c = tmp_path / "w.pt", tmp_path / "c.json"
    shutil.copy(WEIGHTS, w)
    c.write_text(json.dumps(calibration if calibration is not None else json.loads(CALIBRATION.read_text())), encoding="utf-8")
    return w, c


def test_shipped_calibration_is_bound_to_the_shipped_weights():
    assert RoleModel.load().identity["weights_sha256"] == json.loads(CALIBRATION.read_text())["weights_sha256"]


def test_calibration_for_other_weights_is_refused(tmp_path):
    cal = json.loads(CALIBRATION.read_text())
    cal["weights_sha256"] = "0" * 64
    w, c = _copy(tmp_path, cal)
    with pytest.raises(Refusal, match="refit the calibration"):
        RoleModel.load(w, c)


def test_calibration_without_a_weights_hash_is_refused(tmp_path):
    cal = json.loads(CALIBRATION.read_text())
    del cal["weights_sha256"]
    w, c = _copy(tmp_path, cal)
    with pytest.raises(Refusal, match="no weights hash"):
        RoleModel.load(w, c)


def test_a_model_release_records_the_model_that_checked_it(tmp_path):
    build(tmp_path, 7, 0, False)
    doc = process(tmp_path / "ok_pdf_text" / "in.pdf", Params(currency="INR", model=True))
    assert doc["status"] == "ok"
    assert doc["file"]["model"] == RoleModel.load().identity
    plain = process(tmp_path / "ok_pdf_text" / "in.pdf", Params(currency="INR"))
    assert "model" not in plain["file"]


def test_schema_rejects_a_malformed_model_field(tmp_path):
    build(tmp_path, 7, 0, False)
    doc = process(tmp_path / "ok_pdf_text" / "in.pdf", Params(currency="INR", model=True))
    doc["file"]["model"] = {"weights_sha256": "abc", "calibration_sha256": "def"}
    with pytest.raises(Exception):
        validate_output(doc)
