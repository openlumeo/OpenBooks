import pytest
from jsonschema import ValidationError, validate

from openbooks_core import SCHEMA_VERSION, Refusal, load_schema, validate_output
from openbooks_core.schema import refusal_doc

SHA = "a" * 64


def test_schema_files_load_and_are_versioned():
    out, ref = load_schema("output"), load_schema("refusal")
    assert SCHEMA_VERSION == "openbooks.v1" == out["properties"]["schema_version"]["const"]
    assert out["$id"] != ref["$id"]


def test_refusal_documents_validate_against_the_refusal_schema():
    validate(refusal_doc("PARSE_ERROR", "x", SHA), load_schema("refusal"))
    with pytest.raises(ValidationError):
        validate({**refusal_doc("PARSE_ERROR", "x", SHA), "data": {}}, load_schema("refusal"))  # a refusal carries no data
    with pytest.raises(ValidationError):
        validate(refusal_doc("PARSE_ERROR", "x", "short"), load_schema("refusal"))


def test_an_empty_document_is_not_valid_output():
    with pytest.raises(Refusal) as e:
        validate_output({"schema_version": "openbooks.v1", "status": "ok"})
    assert e.value.code == "OUTPUT_INVALID"


def doc(**tx):
    m = {"amount": "5.00", "currency": "INR"}
    return {"schema_version": "openbooks.v1", "status": "ok",
            "file": {"sha256": SHA, "name": "in.csv", "detected_format": "csv", "layout_version": "bank_csv.v1", "method": "parser"},
            "data": {"accounts": [{"id": "acct-1", "number": None, "currency": "INR"}], "parties": [], "claims": [],
                     "batches": [{"id": "batch-1", "kind": "statement", "account_id": "acct-1", "currency": "INR", "period_start": "2026-01-01",
                                  "period_end": "2026-01-01", "opening": m, "closing": m, "opening_derived": False}],
                     "transactions": [{"id": "txn-00001", "batch_id": "batch-1", "account_id": "acct-1", "date": "2026-01-01",
                                       "direction": "credit", "amount": m, "balance_after": m, **tx}]},
            "evidence": {f"{r}.{f}": {"page": None, "bbox": None, "row": 2, "raw_text": "x", "method": "parser"}
                         for r, f in [("batch-1", "opening"), ("batch-1", "closing"), ("batch-1", "period_start"), ("batch-1", "period_end"),
                                      ("txn-00001", "date"), ("txn-00001", "amount"), ("txn-00001", "balance_after")]},
            "assertions": [{"id": "A1", "rule": "r", "expected": "e", "computed": "e", "passed": True, "independent": True}]}


def test_the_record_definitions_accept_a_well_formed_document():
    validate_output(doc())


@pytest.mark.parametrize("bad", [{"date": "01/02/2026"}, {"direction": "sideways"}, {"amount": {"amount": "5,00", "currency": "INR"}},
                                 {"amount": {"amount": "5.00", "currency": "inr"}}, {"id": 7}])
def test_the_record_definitions_reject_malformed_transactions(bad):
    with pytest.raises(Refusal) as e:
        validate_output(doc(**bad))
    assert e.value.code == "OUTPUT_INVALID"
