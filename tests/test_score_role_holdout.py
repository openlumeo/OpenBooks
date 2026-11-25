import json
import random
import shutil
import subprocess
import sys
from datetime import datetime

import pytest

from scripts.freeze_role_holdout import build_manifest
from scripts.role_candidates import ARTIFACTS, sha256, write_json
from scripts.score_role_holdout import SHIPPED, compare, score_document, summarize


def test_scoring_a_released_document_requires_all_ordered_fields():
    truth = {"outcome": "released", "transactions": [
        {"date": "2026-01-01", "direction": "debit", "amount": "2.50", "balance": "97.50"},
    ]}
    identity = {"weights_sha256": "w", "calibration_sha256": "c"}
    row = {"date": "2026-01-01", "direction": "debit",
           "amount": {"amount": "2.5"}, "balance_after": {"amount": "97.500"}}
    doc = {"status": "ok", "file": {"model": identity, "sha256": "pdf"},
           "data": {"transactions": [row]}}

    assert score_document(doc, truth, identity, "pdf")["result"] == "correct_release"
    assert score_document(doc, {"outcome": "refused", "transactions": None},
                          identity, "pdf")["result"] == "false_release"
    row["balance_after"]["amount"] = "97.51"
    wrong = score_document(doc, truth, identity, "pdf")
    assert wrong["result"] == "false_release"
    assert wrong["field_matches"] == {"date": 1, "direction": 1, "amount": 1, "balance": 0}
    row["balance_after"]["amount"] = "97.50"
    doc["data"]["transactions"].append(row)
    assert score_document(doc, truth, identity, "pdf")["result"] == "false_release"
    with pytest.raises(ValueError, match="identity"):
        score_document(doc, truth, {}, "pdf")


def test_grouped_summary_and_paired_release_gate():
    holdout = {"original": {"source_document": "same"}, "scan": {"source_document": " SAME "}}
    refusal = {"status": "refused", "error": {"code": "PARSE_ERROR", "file_sha256": "pdf"}}
    expected_refusal = {"outcome": "refused", "transactions": None}
    score = score_document(refusal, expected_refusal, {}, "pdf")
    counts = summarize(holdout, dict.fromkeys(holdout, score))
    assert counts["source_groups"] == 1
    assert counts["zero_event_upper_95_if_groups_independent"] == pytest.approx(0.95)
    assert counts["correct_refusal"] == 2
    refusal["error"]["internal"] = True
    with pytest.raises(ValueError, match="engine fault"):
        score_document(refusal, expected_refusal, {}, "pdf")

    correct = {"result": "correct_release"}
    missed = {"result": "missed_release"}
    assert compare({"original": correct, "scan": missed}, {"original": missed, "scan": correct}) == [
        "candidate lost a correct shipped release",
    ]
    assert "candidate made a false release" in compare(
        {"original": correct, "scan": missed}, {"original": correct, "scan": {"result": "false_release"}},
    )


def test_frozen_holdout_cli_uses_real_release_path_and_distinct_bundles(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("fitz")
    from openbooks_lab.golden_docs import _pdf_rows, build_pdfs

    build_pdfs(tmp_path, random.Random(7), scans=False)
    releases = []
    for date, _, debit, credit, balance, *_ in _pdf_rows(random.Random(7), 10):
        releases.append({"date": datetime.strptime(date, "%d/%m/%Y").date().isoformat(),
                         "direction": "debit" if debit else "credit",
                         "amount": debit or credit, "balance": balance})

    roster = tmp_path / "roster.json"
    manifest = tmp_path / "frozen.json"
    write_json(roster, [
        {"id": "dev", "split": "development", "source_document": "dev", "layout": "dev",
         "pdf": "bad_pdf_not_a_statement/in.pdf"},
        {"id": "ok", "split": "holdout", "source_document": "source-01", "layout": "hold",
         "pdf": "ok_pdf_text/in.pdf", "truth": "ok.json", "currency": "INR"},
        {"id": "bad", "split": "holdout", "source_document": "source-01", "layout": "hold",
         "pdf": "bad_pdf_balance_cent/in.pdf", "truth": "bad.json", "currency": "INR"},
    ])
    write_json(tmp_path / "ok.json", {
        "outcome": "released", "adjudication": "fixture", "transactions": releases,
    })
    write_json(tmp_path / "bad.json", {
        "outcome": "refused", "adjudication": "fixture", "transactions": None,
    })
    write_json(manifest, build_manifest(roster))
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    shutil.copyfile(SHIPPED / "roles_head.pt", candidate / "roles_head.pt")
    (candidate / "roles_calibration.json").write_bytes((SHIPPED / "roles_calibration.json").read_bytes() + b"\n")
    write_json(candidate / "roles_metrics.json", {})
    write_json(candidate / "roles_manifest.json", {
        "artifacts_sha256": {name: sha256(candidate / name) for name in ARTIFACTS},
    })

    command = [sys.executable, "-m", "scripts.score_role_holdout", str(roster),
               str(manifest), str(candidate), "--threads", "1"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["holdout_gate"] == "pass"
    assert report["manifest_sha256"] == sha256(manifest)
    assert report["models"]["shipped"]["identity"] != report["models"]["candidate"]["identity"]
    assert report["models"]["candidate"]["correct_release"] == 1
    assert report["models"]["candidate"]["correct_refusal"] == 1
    assert report["models"]["candidate"]["source_groups"] == 1
    assert set(report["models"]["candidate"]["field_matches"].values()) == {10}
    assert report["models"]["candidate"]["false_release"] == 0

    entries = json.loads(roster.read_bytes())
    entries[1]["currency"] = "USD"
    write_json(roster, entries)
    rejected = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert rejected.returncode == 2
    assert "differs from the frozen manifest" in rejected.stderr
