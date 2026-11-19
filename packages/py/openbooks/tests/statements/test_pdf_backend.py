"""The PDF and image reader (pypdfium2 / Pillow) and the statements the engine builds from it, on hand-made files.

Every file here is built byte by byte (pdfmaker.py), so each expectation is about something the test itself put in the file."""
import importlib.util
import json

import pytest

pytest.importorskip("pypdfium2")

from openbooks.core import Params, process  # noqa: E402
from openbooks.core.errors import Refusal  # noqa: E402
from openbooks.statements.pdf_backend import open_document  # noqa: E402
from pdfmaker import ROWS, pdf_bytes, statement_page, statement_pdf, text  # noqa: E402

INR = Params(currency="INR")


def words_of(pdf: bytes, tmp_path, page=0):
    f = tmp_path / "w.pdf"
    f.write_bytes(pdf)
    doc = open_document(f)
    try:
        for i, pg in enumerate(doc.pages()):  # a page is only valid while the generator is on it
            if i == page:
                return pg.words()
    finally:
        doc.close()


def run(pdf: bytes, tmp_path, params=INR):
    f = tmp_path / "in.pdf"
    f.write_bytes(pdf)
    return process(f, params)


# ---- words: what the engine is given ------------------------------------------------------------------------------------

def test_words_come_back_with_top_left_coordinates_in_points(tmp_path):
    (hello, world) = words_of(pdf_bytes([text(72, 700, "Hello world", 12)]), tmp_path)
    assert (hello[0], world[0]) == ("Hello", "world")
    _, x0, y0, x1, y1 = hello
    assert 71 <= x0 <= 73 and x1 > x0
    assert y0 < 792 - 700 < y1  # the baseline is 92pt from the top of a 792pt page, inside the word's box
    assert world[1] > hello[3] - 1  # the second word starts to the right of the first


def test_page_size_follows_the_media_box(tmp_path):
    f = tmp_path / "a4.pdf"
    f.write_bytes(pdf_bytes([text(10, 10, "x")], media_box=b"[0 0 595 842]"))
    doc = open_document(f)
    try:
        page = next(iter(doc.pages()))
        assert (round(page.width), round(page.height)) == (595, 842)
    finally:
        doc.close()


def test_a_media_box_that_does_not_start_at_the_origin_is_measured_from_its_own_corner(tmp_path):
    (w,) = words_of(pdf_bytes([text(150, 250, "Hi")], media_box=b"[100 200 400 500]"), tmp_path)
    assert 49 <= w[1] <= 51 and 0 <= w[2] <= 300 and w[3] < 300  # 150-100 from the left; inside the 300-wide page


def test_words_break_at_whitespace_and_where_one_text_object_ends(tmp_path):
    pdf = pdf_bytes([text(36, 700, "AB") + text(50, 700, "CD") + text(100, 700, "one   two\tthree")])
    assert [w[0] for w in words_of(pdf, tmp_path)] == ["AB", "CD", "one", "two", "three"]


def test_text_that_is_not_horizontal_is_ignored(tmp_path):
    rotated = b"BT /F1 20 Tf 0 1 -1 0 300 300 Tm (WATERMARK) Tj ET\n"  # 90 degrees
    slanted = b"BT /F1 20 Tf 0.707 0.707 -0.707 0.707 100 100 Tm (DIAGONAL) Tj ET\n"
    assert [w[0] for w in words_of(pdf_bytes([rotated + slanted + text(36, 700, "kept")]), tmp_path)] == ["kept"]


def test_a_page_with_no_text_has_no_words(tmp_path):
    assert words_of(pdf_bytes([b""]), tmp_path) == []
    assert words_of(pdf_bytes([b""], omit_contents=True), tmp_path) == []


def test_text_outside_the_page_does_not_break_reading(tmp_path):
    ws = words_of(pdf_bytes([text(-500, -500, "off") + text(9000, 9000, "far") + text(36, 700, "in")]), tmp_path)
    assert {"in"} <= {w[0] for w in ws}


def test_a_character_outside_the_basic_plane_is_one_character_not_two_lone_halves(tmp_path):
    cmap = (b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /X def /CMapType 2 def "
            b"1 begincodespacerange <0000> <FFFF> endcodespacerange 3 beginbfchar <0001> <0041> <0002> <D83DDE00> <0003> <D83D> endbfchar "
            b"endcmap CMapName currentdict /CMap defineresource pop end end")
    extra = {6: b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream",
             7: b"<< /Type /Font /Subtype /Type0 /BaseFont /Helvetica /Encoding /Identity-H /DescendantFonts [8 0 R] /ToUnicode 6 0 R >>",
             8: b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Helvetica /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
                b"/Supplement 0 >> /DW 600 >>"}
    pdf = pdf_bytes([b"BT /F2 12 Tf 72 700 Td <00010002> Tj ET BT /F2 12 Tf 72 650 Td <00010003> Tj ET"],
                    extra_objs=extra, fonts=b"/F1 5 0 R /F2 7 0 R")
    ws = [w[0] for w in words_of(pdf, tmp_path)]
    assert ws[0] == "A\U0001f600"
    assert not any(0xD800 <= ord(c) <= 0xDFFF for w in ws for c in w), "a lone surrogate cannot be written as UTF-8"
    json.dumps(ws, ensure_ascii=False).encode("utf-8")  # what writing the output would do
    assert ws[1] == "A�"  # an unpaired half becomes the replacement character


# ---- whole statements ---------------------------------------------------------------------------------------------------

def test_a_text_pdf_statement_is_released_with_page_and_box_evidence(tmp_path):
    doc = run(statement_pdf(closing="1295.00"), tmp_path)
    assert doc["status"] == "ok", doc.get("error")
    assert [t["amount"]["amount"] for t in doc["data"]["transactions"]] == ["500.00", "200.50", "4.50"]
    ev = doc["evidence"][f"{doc['data']['transactions'][1]['id']}.amount"]
    assert ev["raw_text"] == "200.50" and ev["page"] == 1
    x0, y0, x1, y1 = ev["bbox"]
    assert 0 <= x0 < x1 <= 612 and 0 <= y0 < y1 <= 792


@pytest.mark.parametrize("old,new", [("1500.00", "1500.01"), ("200.50", "200.51"), ("1295.00", "1295.10"), ("500.00", "400.00")])
def test_a_tampered_text_pdf_is_refused(tmp_path, old, new):
    pdf = statement_pdf(closing=None).replace(old.encode(), new.encode())
    doc = run(pdf, tmp_path)
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH", doc.get("data")


def test_a_statement_that_continues_over_several_pages_is_one_document(tmp_path):
    rows = [(f"{d:02d}/01/2026", f"Item {d}", "10.00", "", f"{1000 - 10 * d}.00") for d in range(1, 31)]
    pages = [statement_page(rows[:10]), statement_page(rows[10:20], opening=None, title="Statement (continued)"),
             statement_page(rows[20:], opening=None, title="Statement (continued)")]
    doc = run(pdf_bytes(pages), tmp_path, Params(currency="INR", opening=None))
    assert doc["status"] == "ok", doc.get("error")
    assert len(doc["data"]["transactions"]) == 30
    pages_seen = {doc["evidence"][f"{t['id']}.amount"]["page"] for t in doc["data"]["transactions"]}
    assert pages_seen == {1, 2, 3}


def test_the_same_statement_gives_the_same_result_every_time(tmp_path):
    pdf = statement_pdf(closing="1295.00")
    first = run(pdf, tmp_path)
    assert all(run(pdf, tmp_path) == first for _ in range(3))


def test_a_statement_that_does_not_state_its_currency_is_refused_not_guessed(tmp_path):
    doc = run(statement_pdf(title="Statement of Account"), tmp_path, Params())
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


# ---- things a PDF reader must refuse, never crash on --------------------------------------------------------------------

@pytest.mark.parametrize("rotate", [90, 180, 270])
def test_a_rotated_page_is_refused_with_a_reason(tmp_path, rotate):
    doc = run(statement_pdf(rotate=rotate), tmp_path)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and "rotated" in doc["error"]["message"]


def test_more_pages_than_the_limit_is_refused(tmp_path):
    doc = run(pdf_bytes([text(36, 700, "page")] * 61), tmp_path)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and "pages" in doc["error"]["message"]


def test_more_words_than_the_limit_on_one_page_is_refused(tmp_path):
    body = b"".join(b"BT /F1 1 Tf %d %d Td (w) Tj ET\n" % (i % 600, i // 600 + 10) for i in range(20_001))
    doc = run(pdf_bytes([body]), tmp_path)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and "words" in doc["error"]["message"]


def test_a_page_with_no_text_layer_is_refused_when_ocr_is_off(tmp_path):
    doc = run(pdf_bytes([text(36, 700, "just three words")]), tmp_path, Params(currency="INR", ocr=False))
    assert doc["status"] == "refused" and "OCR is off" in doc["error"]["message"]


@pytest.mark.parametrize("payload", [b"", b"%PDF-1.4", b"%PDF-1.4\n%%EOF", b"\x00" * 2000, b"not a pdf at all", b"%PDF-" + b"A" * 5000])
def test_unreadable_pdfs_are_refused_as_unsupported_input(tmp_path, payload):
    doc = run(payload, tmp_path)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and not doc["error"].get("internal")


def test_a_truncated_pdf_never_releases_something_different_from_the_whole(tmp_path):
    whole = statement_pdf(closing="1295.00")
    expected = run(whole, tmp_path)
    assert expected["status"] == "ok"
    for cut in range(0, len(whole), max(1, len(whole) // 40)):
        doc = run(whole[:cut], tmp_path, Params(currency="INR", ocr=False))
        assert not doc["error"].get("internal") if doc["status"] == "refused" else doc["data"]["transactions"] == expected["data"]["transactions"], cut


@pytest.mark.parametrize("media_box", [b"[0 0 0 0]", b"[0 0 -5 -5]", b"[0 0 1 1]", b"[0 0 14400 14400]", b"[612 792 0 0]"])
def test_odd_page_sizes_never_crash_the_engine(tmp_path, media_box):
    doc = run(statement_pdf(media_box=media_box), tmp_path, Params(currency="INR", ocr=False))
    assert doc["status"] in ("ok", "refused") and not doc.get("error", {}).get("internal"), doc.get("error")


@pytest.mark.parametrize("content", [b"BT /F9 12 Tf (x) Tj ET", b"q q q q q q q q q q Q", b"BT (unterminated Tj ET", b"1 0 0 RG 0 0 m", b"BT /F1 0 Tf 0 0 Td (zero size) Tj ET"])
def test_hostile_content_streams_never_crash_the_engine(tmp_path, content):
    doc = run(pdf_bytes([content]), tmp_path, Params(currency="INR", ocr=False))
    assert doc["status"] == "refused" and not doc["error"].get("internal"), doc["error"]


def test_a_pdf_with_a_damaged_cross_reference_table_is_still_read_or_refused_cleanly(tmp_path):
    pdf = statement_pdf(closing="1295.00").replace(b"startxref", b"startxref\n999999")
    doc = run(pdf, tmp_path)
    assert doc["status"] in ("ok", "refused") and not doc.get("error", {}).get("internal")


def test_the_input_file_is_never_modified(tmp_path):
    f = tmp_path / "in.pdf"
    f.write_bytes(statement_pdf(closing="1295.00"))
    before = (f.read_bytes(), f.stat().st_mtime_ns)
    process(f, INR)
    assert (f.read_bytes(), f.stat().st_mtime_ns) == before


# ---- images -------------------------------------------------------------------------------------------------------------

needs_pil = pytest.mark.skipif(importlib.util.find_spec("PIL") is None, reason="images need Pillow (openbooks[scan])")


def _png(tmp_path, size=(200, 100), dpi=None, fmt="PNG", name="s.png"):
    f = tmp_path / name
    from PIL import Image

    kw = {"dpi": dpi} if dpi else {}
    Image.new("RGB", size, "white").save(f, fmt, **kw)
    return f


@needs_pil
def test_an_image_is_one_page_with_no_text_layer(tmp_path):
    doc = open_document(_png(tmp_path), image=True)
    try:
        (page,) = list(doc.pages())
        assert doc.page_count == 1 and page.words() == []
        assert (page.width, page.height) == (200, 100)  # no DPI stated: one pixel per point
        assert page.render_rgb(2.0).shape == (200, 400, 3)
    finally:
        doc.close()


@needs_pil
def test_an_images_size_in_points_follows_its_dpi(tmp_path):
    doc = open_document(_png(tmp_path, size=(1200, 1800), dpi=(300, 300)), image=True)
    try:
        (page,) = list(doc.pages())
        assert (round(page.width), round(page.height)) == (288, 432)  # 4 x 6 inches
    finally:
        doc.close()


@needs_pil
@pytest.mark.parametrize("fmt,name", [("PNG", "a.png"), ("JPEG", "a.jpg"), ("JPEG", "a.jpeg")])
def test_png_and_jpeg_are_both_read_and_refused_when_ocr_is_off(tmp_path, fmt, name):
    doc = process(_png(tmp_path, fmt=fmt, name=name), Params(currency="INR", ocr=False))
    assert doc["status"] == "refused" and "OCR is off" in doc["error"]["message"]


@needs_pil
@pytest.mark.parametrize("payload", [b"", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF89a" + b"0" * 100, b"\x00" * 500])
def test_corrupt_images_are_refused_as_unsupported_input(tmp_path, payload):
    f = tmp_path / "bad.png"
    f.write_bytes(payload)
    doc = process(f, Params(currency="INR", ocr=False))
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT" and not doc["error"].get("internal")


@needs_pil
def test_a_truncated_png_is_refused(tmp_path):
    f = _png(tmp_path, size=(400, 400))
    f.write_bytes(f.read_bytes()[:60])
    assert process(f, Params(currency="INR", ocr=False))["error"]["code"] == "UNSUPPORTED_INPUT"


def test_opening_a_missing_dependency_message_names_the_extra(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "PIL", None)
    from openbooks.core.errors import EngineFault

    with pytest.raises(EngineFault, match=r"openbooks\[scan\]"):
        open_document(b"x", image=True)


def test_an_unreadable_source_raises_a_refusal_not_a_library_error(tmp_path):
    f = tmp_path / "x.pdf"
    f.write_bytes(b"garbage")
    with pytest.raises(Refusal) as e:
        open_document(f)
    assert e.value.code == "UNSUPPORTED_INPUT"


def test_rows_fixture_is_the_statement_the_other_tests_assume():
    assert len(ROWS) == 3


def test_a_scan_without_the_ocr_extra_is_an_engine_problem_with_an_install_hint(tmp_path, monkeypatch):
    import sys

    from openbooks.core.errors import EngineFault
    from openbooks.statements import pdf_front

    monkeypatch.setitem(sys.modules, "easyocr", None)
    monkeypatch.setattr(pdf_front, "_READER", None)
    f = tmp_path / "scan.pdf"
    f.write_bytes(pdf_bytes([text(36, 700, "two words")]))
    with pytest.raises(EngineFault, match=r"openbooks\[scan\]"):
        process(f, INR, strict=True)
    doc = process(f, Params(currency="INR", ocr=False), strict=True)  # the caller can ask for a refusal instead
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT"
