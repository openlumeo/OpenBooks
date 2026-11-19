import json

import pytest

from scripts.promote import BASELINE, judge, load
from scripts.role_candidates import ARTIFACTS, sha256, split_sha256, verify_bundle, write_json


def test_candidate_gate_rejects_incomparable_or_invalid_metrics(tmp_path):
    baseline = load(BASELINE)
    assert judge(baseline, baseline) == []
    candidate = load(BASELINE)
    candidate["test"]["tokens"] += 1
    assert "split counts differ" in judge(candidate, baseline)[0]
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


def test_candidate_gate_checks_content_when_baseline_has_a_split_hash():
    baseline = load(BASELINE)
    candidate = load(BASELINE)
    row = {"w": [1], "s": [1], "b": [[0, 0, 1, 1]], "y": [1], "t": [1]}
    baseline["test"]["split_sha256"] = split_sha256([row])
    candidate["test"]["split_sha256"] = split_sha256([{**row, "y": [2]}])
    assert "split contents differ" in judge(candidate, baseline)[0]
