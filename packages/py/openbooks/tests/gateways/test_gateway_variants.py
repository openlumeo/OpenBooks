"""Every gateway layout written the ways exports really arrive: BOM, Windows and old-Mac line endings, blank lines, no final newline,
upper-case extension. The released data must be identical to the plain file's."""
import pytest
from test_gateways import PAYPAL, RAZORPAY, STRIPE, WISE

from openbooks.core import Params, process

CASES = {"stripe": (STRIPE, {}), "razorpay": (RAZORPAY, {}), "paypal": (PAYPAL, {}), "wise": (WISE, {"allow_derived_opening": True})}
CR, LF = chr(13), chr(10)
VARIANTS = {
    "bom": lambda t: ("\ufeff" + t).encode("utf-8"),
    "crlf": lambda t: t.replace(LF, CR + LF).encode("utf-8"),
    "cr_only": lambda t: t.replace(LF, CR).encode("utf-8"),
    "no_final_newline": lambda t: t.rstrip(LF).encode("utf-8"),
    "trailing_blank_lines": lambda t: (t + LF * 5).encode("utf-8"),
    "cp1252": lambda t: t.replace("Acme", "Acm\u00e9").encode("cp1252"),
}


def run(tmp_path, content, params, name="in.csv"):
    f = tmp_path / name
    f.write_bytes(content)
    return process(f, Params(**params))


@pytest.mark.parametrize("variant", sorted(VARIANTS))
@pytest.mark.parametrize("layout", sorted(CASES))
def test_a_spelling_variant_releases_the_same_data(tmp_path, layout, variant):
    text, params = CASES[layout]
    base = run(tmp_path, text.encode("utf-8"), params)
    assert base["status"] == "ok", base.get("error")
    doc = run(tmp_path, VARIANTS[variant](text), params)
    assert doc["status"] == "ok", f"{layout}/{variant}: {doc.get('error')}"
    if variant == "cp1252":
        assert [t["amount"] if "amount" in t else t["net"] for t in doc["data"]["transactions"]] == \
               [t["amount"] if "amount" in t else t["net"] for t in base["data"]["transactions"]]
    else:
        assert doc["data"] == base["data"]


@pytest.mark.parametrize("layout", sorted(CASES))
def test_an_upper_case_extension_makes_no_difference(tmp_path, layout):
    text, params = CASES[layout]
    assert run(tmp_path, text.encode("utf-8"), params, "IN.CSV")["status"] == "ok"


def money_key(t):
    """A row's date and every amount in it: what must never differ between a cut-off export and the whole one."""
    return (t.get("date"), tuple(sorted((k, v["amount"], v["currency"]) for k, v in t.items() if isinstance(v, dict) and "amount" in v)))


@pytest.mark.parametrize("layout", sorted(CASES))
def test_a_cut_off_export_never_releases_a_row_whose_numbers_are_not_in_the_whole_one(tmp_path, layout):
    """Cutting an export at a row boundary leaves a valid shorter export (the engine cannot know rows are missing; that is the
    known limit of any file without a printed total). What must never happen is a wrong number: every released row, whatever the
    cut, must have exactly the date and amounts of a row in the full file."""
    text, params = CASES[layout]
    full = {money_key(t) for t in run(tmp_path, text.encode("utf-8"), params)["data"]["transactions"]}
    for cut in range(0, len(text), 5):
        doc = run(tmp_path, text[:cut].encode("utf-8"), params)
        assert not doc.get("error", {}).get("internal"), (layout, cut)
        if doc["status"] == "ok" and (cut == 0 or text[cut - 1] == chr(10)):
            assert {money_key(t) for t in doc["data"]["transactions"]} <= full, (layout, cut, text[:cut][-30:])


@pytest.mark.parametrize("layout", sorted(CASES))
def test_a_nul_byte_anywhere_is_refused_as_binary(tmp_path, layout):
    text, params = CASES[layout]
    doc = run(tmp_path, (text[:30] + chr(0) + text[30:]).encode("utf-8"), params)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT"


def test_a_gateway_file_with_a_second_currency_is_refused_or_kept_separate(tmp_path):
    mixed = STRIPE.replace("txn_2,2026-01-06 11:00:00,usd", "txn_2,2026-01-06 11:00:00,eur")
    doc = run(tmp_path, mixed.encode("utf-8"), {})
    if doc["status"] == "ok":
        assert {b["currency"] for b in doc["data"]["batches"]} == {"USD", "EUR"}
    else:
        assert doc["error"]["code"] in {"PARSE_ERROR", "BALANCE_MISMATCH"} and not doc["error"].get("internal")


def test_refund_signs_are_not_reversed_by_any_spelling(tmp_path):
    for variant in VARIANTS.values():
        doc = run(tmp_path, variant(STRIPE), {})
        assert doc["status"] == "ok"
        refund = next(t for t in doc["data"]["transactions"] if t["gross"]["amount"].startswith("-"))
        assert refund["net"]["amount"] == "-20.00"
