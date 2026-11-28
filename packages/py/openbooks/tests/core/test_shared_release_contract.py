import json
from decimal import Decimal
from pathlib import Path

import pytest

from openbooks.core import Params, process

SHARED = Path(__file__).resolve().parents[1] / "fixtures" / "shared"
CASES = json.loads((SHARED / "release_contract.json").read_text(encoding="utf-8"))["cases"]


def _params(raw: dict) -> Params:
    kwargs = dict(raw)
    if "opening" in kwargs:
        kwargs["opening"] = Decimal(kwargs["opening"])
    return Params(**kwargs)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_shared_release_contract(case):
    doc = process(SHARED / case["file"], _params(case["params"]))
    assert doc["status"] == case["status"]
    assert (doc.get("error") or {}).get("code") == case["code"]
    if case["status"] != "ok":
        return
    assert doc["file"]["layout_version"] == case["layout_version"]
    assert [a["independent"] for a in doc["assertions"]] == case["assertion_independent"]
    assert doc["coverage"] == case["coverage"]
