import pytest

from openbooks.pipeline import Params, process


@pytest.mark.parametrize("first_balance", ["110.00", "110.01"])
def test_separate_glyph_objects_and_balance_cards(tmp_path, first_balance):
    import pymupdf

    pdf = tmp_path / "statement.pdf"
    with pymupdf.open() as document:
        page = document.new_page()

        def text(x, y, words):
            for char in words:
                if char != " ":
                    page.insert_text((x, y), char, fontsize=10)
                x += pymupdf.get_text_length(char, fontsize=10)

        text(48, 68, "OPENING BALANCE")
        text(220, 68, "CLOSING BALANCE")
        text(48, 85, "INR 100.00")
        text(220, 85, "INR 105.00")
        text(48, 120, "DATE")
        text(135, 120, "DESCRIPTION")
        text(300, 120, "WITHDRAWAL")
        text(390, 120, "DEPOSIT")
        text(475, 120, "BALANCE")
        text(48, 147, "13-01-2026")
        text(135, 147, "FIRST TRANSFER")
        text(390, 147, "10.00")
        text(475, 147, first_balance)
        text(48, 165, "14-01-2026")
        text(135, 165, "SECOND TRANSFER")
        text(300, 165, "5.00")
        text(475, 165, "105.00")
        document.save(pdf)

    report = process(pdf, Params(ocr=False), strict=True)
    if first_balance == "110.00":
        assert report["status"] == "ok", report
        assert report["file"]["method"] == "pdf_text"
        assert [(row["date"], row["direction"], row["balance_after"]["amount"])
                for row in report["data"]["transactions"]] == [
            ("2026-01-13", "credit", "110.00"), ("2026-01-14", "debit", "105.00"),
        ]
    else:
        assert report["status"] == "refused", report
        assert report["error"]["code"] == "BALANCE_MISMATCH"
