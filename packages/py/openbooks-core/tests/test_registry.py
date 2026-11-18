"""Registry guarantees. These run with only openbooks-core installed (no provider packages)."""
import subprocess
import sys

import pytest

from openbooks_core import Params, ProviderMissing, Refusal, process
from openbooks_core import registry as R
from openbooks_core.errors import PluginLoadError
from openbooks_core.gates import run_gate

ORDER = ["stripe_balance.v1", "razorpay_settlement.v1", "paypal_activity.v1", "wise_statement.v1", "form_1099b.v1",
         "tds_26as.v1", "ais.v1", "fira.v1", "bank_csv.v1", "trial_balance.v1"]
BANK = ["date", "narration", "withdrawal_amt", "deposit_amt", "closing_balance"]
HEADERS = {"stripe_balance.v1": sorted(R.STRIPE_REQ), "razorpay_settlement.v1": sorted(R.RAZORPAY_REQ),
           "paypal_activity.v1": sorted(R.PAYPAL_REQ), "wise_statement.v1": sorted(R.WISE_REQ),
           "form_1099b.v1": sorted(R.B1099_REQ), "tds_26as.v1": sorted(R.TDS_REQ), "ais.v1": sorted(R.AIS_REQ),
           "fira.v1": sorted(R.FIRA_REQ), "bank_csv.v1": BANK, "trial_balance.v1": sorted(R.TB_REQ)}


def csv_of(*rows):
    return "\n".join(",".join(r) for r in rows) + "\n"


def test_detection_order_is_the_product_order():
    assert [s.id for s in R.KNOWN_LAYOUTS] == ORDER
    assert [s.rank for s in R.KNOWN_LAYOUTS] == sorted(s.rank for s in R.KNOWN_LAYOUTS)
    assert [s.id for s in R.KNOWN_SNIFFERS] == ["ofx.v1", "mt940.v1"]


@pytest.mark.parametrize("a", ORDER)
@pytest.mark.parametrize("b", ORDER)
def test_combined_headers_resolve_to_the_lowest_rank(a, b):
    union = HEADERS[a] + [h for h in HEADERS[b] if h not in HEADERS[a]]
    matching = [lid for lid in ORDER if R.LAYOUT_BY_ID[lid].matches(union, frozenset(union))]
    got = R.detect(csv_of(union, ["1"] * len(union)))
    assert got.layout == matching[0]  # first in order among everything the headers satisfy


def test_an_earlier_row_beats_a_higher_ranked_layout_on_a_later_row():
    text = csv_of(BANK, ["1"] * 5, [], sorted(R.STRIPE_REQ), ["1"] * 6)
    assert R.detect(text).layout == "bank_csv.v1"
    text = csv_of(sorted(R.STRIPE_REQ), ["1"] * 6, [], BANK, ["1"] * 5)
    assert R.detect(text).layout == "stripe_balance.v1"


def test_header_beyond_the_scan_window_is_unknown():
    with pytest.raises(Refusal) as e:
        R.detect("\n" * (R.HEADER_SCAN_ROWS + 5) + csv_of(BANK))
    assert e.value.code == "UNKNOWN_LAYOUT"


def test_ofx_and_mt940_are_recognised_before_csv():
    assert R.detect("OFXHEADER:100\n<OFX>").layout == "ofx.v1"
    mt = ":20:X\n:60F:C260101INR1,00\n:62F:C260101INR1,00\n"
    assert R.detect(mt).layout == "mt940.v1"
    assert R.detect("<OFX>\n" + csv_of(BANK)).layout == "ofx.v1"


def write(tmp_path, text, name="in.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.mark.parametrize("layout", ORDER)
def test_with_no_provider_installed_nothing_is_released(tmp_path, layout):
    cols = HEADERS[layout]
    doc = process(write(tmp_path, csv_of(cols, ["1"] * len(cols))), Params(currency="INR"), registry=R.Registry())
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNKNOWN_LAYOUT"
    assert R.LAYOUT_BY_ID[layout].distribution in doc["error"]["message"]


def _must_not_run(args, params):
    raise AssertionError("the bank parser must not run for a stripe file")


def test_a_missing_provider_never_falls_through_to_a_looser_layout(tmp_path):
    # Stripe's headers plus bank columns: bank CSV would also match, but Stripe outranks it.
    cols = sorted(R.STRIPE_REQ) + ["description", "debit", "credit", "balance", "date"]
    reg = R.Registry(layouts={"bank_csv.v1": _must_not_run})
    doc = process(write(tmp_path, csv_of(cols, ["1"] * len(cols))), Params(currency="INR"), registry=reg)
    assert doc["status"] == "refused" and "openbooks-gateways" in doc["error"]["message"]


def test_provider_missing_is_a_typed_refusal_with_an_install_hint():
    e = ProviderMissing("paypal_activity.v1", "openbooks-gateways")
    assert isinstance(e, Refusal) and e.code == "UNKNOWN_LAYOUT" and "pip install openbooks-gateways" in e.message


def test_a_batch_kind_nobody_checks_is_refused_not_released():
    data = {"batches": [{"id": "batch-1", "kind": "mystery", "currency": "INR"}], "transactions": []}
    with pytest.raises(Refusal) as e:
        run_gate(data, [])
    assert e.value.code == "OUTPUT_INVALID"
    assert run_gate(data, [("mystery", lambda b, tx: [("r", "1", "1", True)])])[0]["passed"]


def test_registry_rejects_ids_core_does_not_know():
    with pytest.raises(PluginLoadError):
        R.Registry(layouts={"made_up.v1": lambda a, p: None})
    with pytest.raises(PluginLoadError):
        R.Registry(sniffers={"made_up.v1": lambda a, p: None})


def test_duplicate_entry_point_names_are_a_load_error(monkeypatch):
    from importlib.metadata import EntryPoint

    eps = [EntryPoint("bank_csv.v1", "a.b:c", "openbooks.layouts"), EntryPoint("bank_csv.v1", "x.y:z", "openbooks.layouts")]
    monkeypatch.setattr(R, "entry_points", lambda group: eps)
    with pytest.raises(PluginLoadError):
        R._entry_points("layouts")


def test_a_provider_that_fails_to_import_is_a_plugin_error_not_a_verdict():
    from importlib.metadata import EntryPoint

    reg = R.Registry(layouts={"bank_csv.v1": EntryPoint("bank_csv.v1", "no_such_module_xyz:f", "openbooks.layouts")})
    with pytest.raises(PluginLoadError):
        reg.layout_parser("bank_csv.v1")


HEAVY = ("torch", "fitz", "pymupdf", "openpyxl", "easyocr", "numpy", "scipy")


def _heavy_modules_loaded_after(code: str) -> list[str]:
    prog = code + "\nimport sys\nprint(sorted(m for m in " + repr(HEAVY) + " if m in sys.modules))\n"
    out = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True, check=True).stdout
    return eval(out.strip().splitlines()[-1])  # noqa: S307 - our own subprocess printing a list of names


def test_importing_core_and_detecting_imports_no_heavy_module():
    code = ("import openbooks_core\n"
            "from openbooks_core.registry import detect\n"
            "detect('Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\\n1,2,3,4,5\\n')\n")
    assert _heavy_modules_loaded_after(code) == []


def test_processing_a_csv_with_the_installed_providers_imports_no_heavy_module(tmp_path):
    pytest.importorskip("openbooks")
    f = tmp_path / "in.csv"
    f.write_text("Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,x,,5.00,1005.00\n", encoding="utf-8")
    code = ("from decimal import Decimal\n"
            "from openbooks_core import process, Params\n"
            f"doc = process({str(f)!r}, Params(currency='INR', opening=Decimal('1000')))\n"
            "assert doc['status'] == 'ok', doc\n")
    assert _heavy_modules_loaded_after(code) == []
