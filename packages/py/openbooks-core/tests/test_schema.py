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
