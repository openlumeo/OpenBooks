"""Output contract: evidence carries page/bbox/method; assertions carry `independent`; refusals stay typed."""
import copy

import pytest

from openbooks.pipeline import Refusal, validate_output

SHA = "a" * 64
DOC = {
    "schema_version": "openbooks.v1", "status": "ok",
    "file": {"sha256": SHA, "name": "in.pdf", "detected_format": "pdf", "layout_version": "x", "method": "pdf_text"},
    "data": {"accounts": [], "parties": [], "claims": [],
             "batches": [{"id": "batch-1", "kind": "statement"}],
             "transactions": [{"id": "txn-00001", "batch_id": "batch-1"}]},
    "evidence": {"txn-00001.x": {"page": 1, "bbox": [0, 0, 1, 1], "row": 1, "raw_text": "1", "method": "pdf_text"}},
    "assertions": [{"id": "A1", "rule": "r", "expected": "1", "computed": "1", "passed": True, "independent": True}],
}


def _bad(mutate):
    doc = copy.deepcopy(DOC)
    mutate(doc)
    with pytest.raises(Refusal) as e:
        validate_output(doc)
    assert e.value.code == "OUTPUT_INVALID"


def test_valid_doc_passes():
    validate_output(copy.deepcopy(DOC))


def test_assertion_without_independent_is_refused_not_parse_error():
    _bad(lambda d: d["assertions"][0].pop("independent"))


def test_located_evidence_needs_page_and_bbox():
    _bad(lambda d: d["evidence"]["txn-00001.x"].update(bbox=None))


def test_unknown_method_is_refused():
    _bad(lambda d: d["evidence"]["txn-00001.x"].update(method="guess"))
