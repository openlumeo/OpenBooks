"""Frozen-behaviour check for the package split. See run.py. Re-record only on a commit whose behaviour change is intended."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as char  # noqa: E402
from corpus import have_fitz  # noqa: E402


def _baseline(section: str) -> dict:
    return json.loads(char.baseline_path(section).read_text(encoding="utf-8"))


def test_main_corpus_is_unchanged():
    problems = char.diff(_baseline("main"), char.collect("main"))
    assert not problems, "\n".join(problems[:20])


def test_baseline_is_not_trivially_small():
    base = _baseline("main")
    assert len(base) > 500
    assert {v["status"] for v in base.values()} == {"ok", "refused"}


def test_harness_detects_a_behaviour_change(monkeypatch):
    from openbooks import pipeline

    monkeypatch.setitem(pipeline.EXPONENT, "INR", 0)
    assert char.diff(_baseline("main"), char.collect("main"))


@pytest.mark.skipif(not have_fitz() or not char.baseline_path("pdf").exists(), reason="pdf section is recorded and run in CI")
def test_pdf_corpus_is_unchanged():
    problems = char.diff(_baseline("pdf"), char.collect("pdf"))
    assert not problems, "\n".join(problems[:20])
