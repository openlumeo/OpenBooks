import json
import re

import pytest

from openbooks.core import iso4217
from openbooks.core.iso4217 import PAYLOAD_CHECKSUM_KEY, RegistryIntegrityError, exponent_of, registry_checksum


@pytest.fixture
def registry_at(monkeypatch, tmp_path):
    def use(document):
        path = tmp_path / "iso4217_registry.json"
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(iso4217, "REGISTRY_PATH", path)
        iso4217._document.cache_clear()
        iso4217._indexes.cache_clear()
        return path

    yield use
    monkeypatch.undo()
    iso4217._document.cache_clear()
    iso4217._indexes.cache_clear()


def bundled():
    return json.loads(iso4217.REGISTRY_PATH.read_bytes())


def test_bundled_snapshot_verifies_its_checksum():
    document = bundled()
    assert document[PAYLOAD_CHECKSUM_KEY] == registry_checksum(document)
    assert exponent_of("JPY") == 0


def test_bundled_snapshot_records_source_revision_urls_and_hashes():
    source = bundled()["source"]
    for key in ("list_one", "list_three"):
        assert re.fullmatch(r"[0-9a-f]{64}", source[key]["sha256"])
        assert source[key]["url"].startswith("https://www.six-group.com/")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", source[key]["published"])
    assert source["page"].startswith("https://www.six-group.com/")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", source["retrieved_on"])


def test_bundled_current_codes_are_unique_and_well_formed():
    rows = bundled()["current"]
    codes = [row["code"] for row in rows]
    assert len(codes) == len(set(codes))
    assert all(re.fullmatch(r"[A-Z]{3}", code) for code in codes)
    assert all(re.fullmatch(r"\d{3}", row["number"]) for row in rows)


def test_funds_and_no_minor_unit_entries_are_marked_in_the_snapshot():
    rows = {row["code"]: row for row in bundled()["current"]}
    assert rows["CLF"]["fund"] is True
    assert rows["XAU"]["minor_unit"] is None
    assert rows["XXX"]["minor_unit"] is None


def test_checksum_tamper_is_detected_at_load(registry_at):
    document = bundled()
    for row in document["current"]:
        if row["code"] == "JPY":
            row["minor_unit"] = 2
    registry_at(document)
    with pytest.raises(RegistryIntegrityError):
        exponent_of("JPY")


def test_a_missing_checksum_is_rejected(registry_at):
    document = bundled()
    del document[PAYLOAD_CHECKSUM_KEY]
    registry_at(document)
    with pytest.raises(RegistryIntegrityError):
        exponent_of("USD")


def test_a_source_hash_change_is_detected_at_load(registry_at):
    document = bundled()
    document["source"]["list_one"]["sha256"] = "0" * 64
    registry_at(document)
    with pytest.raises(RegistryIntegrityError):
        exponent_of("USD")


def test_a_wrong_schema_is_rejected(registry_at):
    document = bundled()
    document["schema"] = "something.else"
    registry_at(document)
    with pytest.raises(RegistryIntegrityError):
        exponent_of("USD")
