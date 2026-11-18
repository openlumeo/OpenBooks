"""Hand-built PDFs for tests: no PDF-writing library, so the tests exercise the reader on bytes whose every detail is known."""
from __future__ import annotations

COLS = (36, 110, 300, 380, 460)
HEAD = ("Date", "Description", "Debit", "Credit", "Balance")


def pdf_bytes(pages: list[bytes], *, rotate: int = 0, media_box: bytes = b"[0 0 612 792]", extra_objs: dict[int, bytes] | None = None,
              fonts: bytes = b"/F1 5 0 R", omit_contents: bool = False) -> bytes:
    """A valid PDF with one content stream per page, Helvetica as /F1 (objects 1-4 are fixed, 5 is the font, pages start at 100)."""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids = []
    for i, content in enumerate(pages):
        page_no, content_no = 100 + 2 * i, 101 + 2 * i
        kids.append(b"%d 0 R" % page_no)
        contents = b"" if omit_contents else b" /Contents %d 0 R" % content_no
        objs[page_no] = (b"<< /Type /Page /Parent 2 0 R /MediaBox " + media_box + contents + b" /Resources << /Font << " + fonts
                         + b" >> >> /Rotate %d >>" % rotate)
        objs[content_no] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
    objs[2] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count %d >>" % len(pages)
    objs.update(extra_objs or {})
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    size = max(objs) + 1
    xref = len(out)
    out += b"xref\n0 %d\n" % size + b"0000000000 65535 f \n"
    for n in range(1, size):
        out += (b"%010d 00000 n \n" % offsets[n]) if n in offsets else b"0000000000 65535 f \n"
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return bytes(out)


def text(x: float, y: float, s: str, size: int = 10) -> bytes:
    s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return b"BT /F1 %d Tf %g %g Td (%s) Tj ET\n" % (size, x, y, s.encode("latin-1"))


def statement_page(rows, *, opening: str | None = "1000.00", closing: str | None = None, title: str = "Statement of Account (INR)",
                   top: float = 750, header: bool = True) -> bytes:
    c = text(36, top, title)
    y = top - 30
    if opening is not None:
        c += text(36, y, f"Opening Balance: {opening}")
        y -= 30
    if header:
        for x, h in zip(COLS, HEAD):
            c += text(x, y, h)
    for row in rows:
        y -= 16
        for x, v in zip(COLS, row):
            if v:
                c += text(x, y, v)
    if closing is not None:
        c += text(36, y - 30, f"Closing Balance: {closing}")
    return c


ROWS = [("01/01/2026", "Salary", "", "500.00", "1500.00"),
        ("02/01/2026", "Rent", "200.50", "", "1299.50"),
        ("03/01/2026", "Coffee shop", "4.50", "", "1295.00")]


def statement_pdf(rows=ROWS, **kw) -> bytes:
    pdf_kw = {k: kw.pop(k) for k in ("rotate", "media_box") if k in kw}
    return pdf_bytes([statement_page(rows, **kw)], **pdf_kw)
