"""Every tax layout written the ways exports arrive: BOM, Windows and old-Mac line endings, blank lines, no final newline, and cut off.
The released data must equal the plain file's; a printed total that is missing or cut off must refuse, never release."""
import json

import pytest
from test_tax import cases

from openbooks_core import Params, process

CR, LF = chr(13), chr(10)
VARIANTS = {
    "bom": lambda t: ("\ufeff" + t).encode("utf-8"),
    "crlf": lambda t: t.replace(LF, CR + LF).encode("utf-8"),
    "cr_only": lambda t: t.replace(LF, CR).encode("utf-8"),
    "no_final_newline": lambda t: t.rstrip(LF).encode("utf-8"),
    "trailing_blank_lines": lambda t: (t + LF * 5).encode("utf-8"),
}
CASES = cases()
IDS = [c[1] for c in CASES]


def run(tmp_path, content, params):
    f = tmp_path / "in.csv"
    f.write_bytes(content)
    return process(f, Params(**params))


@pytest.mark.parametrize("variant", sorted(VARIANTS))
@pytest.mark.parametrize("text,layout,params", CASES, ids=IDS)
def test_a_spelling_variant_releases_the_same_data(tmp_path, text, layout, params, variant):
    base = run(tmp_path, text.encode("utf-8"), params)
    assert base["status"] == "ok", base.get("error")
    doc = run(tmp_path, VARIANTS[variant](text), params)
    assert doc["status"] == "ok", f"{layout}/{variant}: {doc.get('error')}"
    assert doc["data"] == base["data"]


def row_key(t):
    return json.dumps({k: v for k, v in t.items() if k not in ('id', 'batch_id')}, sort_keys=True)


ROW_PROVED = {"fira.v1", "form_1099b.v1"}  # these prove each row on its own (FX x rate = INR; proceeds - cost = gain)


@pytest.mark.parametrize("text,layout,params", CASES, ids=IDS)
def test_a_cut_off_file_is_refused_when_its_printed_total_is_the_proof_and_never_changes_a_row_otherwise(tmp_path, text, layout, params):
    """TDS, AIS and the trial balance are proved by a printed total: cut the file before it and the proof is gone, so refuse.
    FIRA and 1099-B are proved row by row, so a cut at a row boundary is a valid shorter file; what must never happen is a changed row."""
    last_line_start = text.rstrip(LF).rfind(LF) + 1
    whole = {row_key(t) for t in run(tmp_path, text.encode("utf-8"), params)["data"]["transactions"]}
    for cut in range(0, last_line_start, 3):
        doc = run(tmp_path, text[:cut].encode("utf-8"), params)
        assert not doc.get("error", {}).get("internal"), (layout, cut)
        if layout in ROW_PROVED:
            if doc["status"] == "ok" and text[cut - 1] == LF:
                assert {row_key(t) for t in doc["data"]["transactions"]} <= whole, (layout, cut)
        else:
            assert doc["status"] == "refused", (layout, cut, text[:cut][-30:])


@pytest.mark.parametrize("text,layout,params", CASES, ids=IDS)
def test_a_nul_byte_is_refused_as_binary(tmp_path, text, layout, params):
    doc = run(tmp_path, (text[:20] + chr(0) + text[20:]).encode("utf-8"), params)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT"


@pytest.mark.parametrize("text,layout,params", CASES, ids=IDS)
def test_a_file_with_every_data_row_deleted_is_refused(tmp_path, text, layout, params):
    lines = text.splitlines()
    doc = run(tmp_path, (LF.join(lines[:1] + lines[-1:]) + LF).encode("utf-8"), params)
    assert doc["status"] == "refused" and not doc["error"].get("internal")
