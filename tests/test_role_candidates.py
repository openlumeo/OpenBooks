import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from scripts.promote import BASELINE, judge, load
from scripts.role_candidates import ARTIFACTS, sha256, split_sha256, verify_bundle, write_json


def test_candidate_gate_rejects_incomparable_or_invalid_metrics(tmp_path):
    baseline = load(BASELINE)
    assert any("shifted debit" in failure for failure in judge(baseline, baseline))
    candidate = load(BASELINE)
    candidate["test"]["tokens"] += 1
    assert "split counts differ" in judge(candidate, baseline)[0]
    candidate["test"]["tokens"] -= 1
    candidate["shifted"]["role_coverage"] = float("nan")
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"int8_shipped": candidate}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid shifted.role_coverage"):
        load(metrics)


def test_candidate_manifest_detects_changed_metrics(tmp_path):
    for name in ARTIFACTS:
        (tmp_path / name).write_bytes(name.encode())
    hashes = {name: sha256(tmp_path / name) for name in ARTIFACTS}
    write_json(tmp_path / "roles_manifest.json", {"artifacts_sha256": hashes})
    assert verify_bundle(tmp_path) == hashes
    (tmp_path / "roles_metrics.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact changed: roles_metrics.json"):
        verify_bundle(tmp_path)


def test_candidate_gate_requires_exact_split_fingerprints(tmp_path):
    baseline = load(BASELINE)
    candidate = load(BASELINE)
    row = {"w": [1], "s": [1], "b": [[0, 0, 1, 1]], "y": [1], "t": [1]}
    baseline["test"]["split_sha256"] = split_sha256([row])
    candidate["test"]["split_sha256"] = split_sha256([{**row, "y": [2]}])
    assert "split contents differ" in judge(candidate, baseline)[0]
    del baseline["test"]["split_sha256"]
    metrics = tmp_path / "metrics.json"
    write_json(metrics, {"int8_shipped": baseline})
    with pytest.raises(ValueError, match="invalid test split hash"):
        load(metrics)


def test_candidate_gate_requires_both_directions_with_no_more_false_amounts(tmp_path):
    baseline = load(BASELINE)
    candidate = deepcopy(baseline)
    for role in ("debit", "credit"):
        counts = candidate["shifted"]["by_role"][role]
        for key in ("correct_singletons", "predicted_singletons", "singletons_on_true_role"):
            counts[key] = 50
    shifted = candidate["shifted"]
    shifted["predicted_amount_singletons"] += 100
    shifted["amount_abstain_rate"] = round(1 - shifted["predicted_amount_singletons"] / shifted["amount_tokens"], 4)
    metrics = tmp_path / "metrics.json"
    write_json(metrics, {"int8_shipped": candidate})
    assert judge(load(metrics), baseline) == []
    candidate["shifted"]["by_role"]["credit"]["correct_singletons"] = 1
    assert any("shifted credit" in failure for failure in judge(candidate, baseline))
    candidate["test"]["predicted_amount_singletons_wrong"] = 1
    candidate["test"]["non_amount_predicted_as_amount"] = 1
    assert any("test false amount" in failure for failure in judge(candidate, baseline))


def test_candidate_gate_rejects_all_abstaining_and_inconsistent_reports(tmp_path):
    baseline = load(BASELINE)
    metrics = tmp_path / "metrics.json"
    candidate = deepcopy(baseline)
    for split in ("test", "shifted"):
        row = candidate[split]
        for key in ("amount_singleton_wrong", "predicted_amount_singletons", "predicted_amount_singletons_wrong",
                    "non_amount_predicted_as_amount"):
            row[key] = 0
        row["amount_abstain_rate"] = 1.0
        for counts in row["by_role"].values():
            for key in ("correct_singletons", "predicted_singletons", "singletons_on_true_role"):
                counts[key] = 0
    write_json(metrics, {"int8_shipped": candidate})
    assert any("test debit" in failure for failure in judge(load(metrics), baseline))
    candidate["test"]["predicted_amount_singletons"] = 1
    write_json(metrics, {"int8_shipped": candidate})
    with pytest.raises(ValueError, match="inconsistent test commitment counts"):
        load(metrics)


def test_role_report_detects_false_amount_predictions_and_amount_miscoverage(monkeypatch):
    pytest.importorskip("torch")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from train_roles import RID, ROLES, report
    from openbooks.statements.calibration import Calibrator

    other, debit, credit, balance = (RID[role] for role in ("other", "debit", "credit", "balance"))
    labels = np.array([other, debit, credit, balance, debit, debit])
    role_logits = np.zeros((len(labels), len(ROLES)))
    role_logits[[0, 1, 2, 3], [debit, debit, other, debit]] = 10
    role_logits[4, [debit, credit]] = 10
    role_logits[5, [credit, balance]] = 10
    role_cal = Calibrator(qhat=0.6)
    metrics = report(role_logits, np.zeros((len(labels), 1)), labels, np.zeros_like(labels), role_cal, Calibrator())

    assert metrics["amount_singleton_wrong"] == 2
    assert metrics["non_amount_predicted_as_amount"] == 1
    assert metrics["predicted_amount_singletons_wrong"] == 2
    assert metrics["predicted_amount_singletons"] == 3
    assert metrics["amount_role_coverage"] == 0.4
    assert metrics["by_role"]["debit"] == {
        "tokens": 3, "covered": 2, "singletons_on_true_role": 1, "predicted_singletons": 3, "correct_singletons": 1,
    }
