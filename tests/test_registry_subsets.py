"""Missing-provider guarantee over the real corpus: with any subset of the provider packages installed, every file either
gives exactly the full-install result or a typed missing-provider refusal. It never gives a different release, and never
a release by a layout other than the one the file was recognised as."""
import itertools
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "characterise"))

from corpus import build_corpus  # noqa: E402
from openbooks_core import default_registry  # noqa: E402
from openbooks_core.process import dumps, process  # noqa: E402
from run import _params  # noqa: E402

DISTRIBUTIONS = ("openbooks-statements", "openbooks-gateways", "openbooks-tax")
SUBSETS = [c for n in range(len(DISTRIBUTIONS)) for c in itertools.combinations(DISTRIBUTIONS, n)]  # every proper subset


@pytest.fixture(scope="module")
def cases():
    return [c for c in build_corpus("main") if "mutate/" not in c.id]  # mutations all share one layout; covered by the baseline


@pytest.fixture(scope="module")
def full(cases):
    reg = default_registry()
    return {c.id: dumps(process(c.path, _params(c.params, {}), registry=reg)) for c in cases}


@pytest.mark.parametrize("subset", SUBSETS, ids=lambda s: "+".join(x.split("-")[1] for x in s) or "core-only")
def test_a_subset_gives_the_full_result_or_a_missing_provider_refusal(subset, cases, full):
    reg = default_registry().restricted_to(subset)
    missing = 0
    for c in cases:
        doc = process(c.path, _params(c.params, {}), registry=reg)
        text = dumps(doc)
        if text == full[c.id]:
            continue
        assert doc["status"] == "refused" and doc["error"]["code"] == "UNKNOWN_LAYOUT" and "optional package" in doc["error"]["message"], (
            f"{c.id}: differs from the full install and is not a missing-provider refusal: {doc.get('error') or doc['status']}")
        missing += 1
    assert missing > 0, "a proper subset should leave some corpus files without a provider"


def test_core_only_releases_nothing(cases):
    reg = default_registry().restricted_to(())
    released = [c.id for c in cases if process(c.path, _params(c.params, {}), registry=reg)["status"] == "ok"]
    assert released == []
