"""Reading PDFs and images with permissively licensed libraries: pypdfium2 (Apache-2.0 / BSD-3, wrapping Google's PDFium) for
PDFs and Pillow for images. Nothing here is AGPL.

The rest of the engine sees only two things per page: its words as (text, x0, y0, x1, y1) in points with the origin at the
top-left (y grows downward), and an RGB render for OCR. The word rules are the ones the engine was built and measured with:
words break at whitespace and wherever one text object ends and the next begins (a table cell is its own text object), and text
that is not horizontal (watermarks, rotated stamps) is ignored.
"""
from __future__ import annotations

import ctypes
import io
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from openbooks.core.errors import EngineFault, Refusal

HORIZONTAL_COS, HORIZONTAL_SIN = 0.9, 0.05  # a line within ~2.9 degrees of horizontal counts as horizontal


def _pdfium():
    try:
        import pypdfium2 as pdfium
    except ImportError as e:
        raise EngineFault("PDF and image statements need pypdfium2: pip install openbooks") from e
    return pdfium


def _upright(angle: float) -> bool:
    """True for a character whose baseline runs left to right (neither rotated nor vertical)."""
    return not (math.cos(angle) < HORIZONTAL_COS or abs(math.sin(angle)) > HORIZONTAL_SIN)


def _char_extent(tp, i: int, left: float, top: float) -> tuple[float, float, float, float]:
    """Character i's loose box in page coordinates with a top-left origin, as (x0, y0, x1, y1)."""
    x_left, y_bottom, x_right, y_top = tp.get_charbox(i, loose=True)
    return x_left - left, top - y_top, x_right - left, top - y_bottom


class PdfPage:
    def __init__(self, page: Any, pdfium: Any) -> None:
        self._page, self._pdfium = page, pdfium
        l, b, r, t = page.get_bbox()
        self._left, self._top = l, t
        self.width, self.height = r - l, t - b
        self.rotation = page.get_rotation()

    def words(self) -> list[tuple[str, float, float, float, float]]:
        if self.rotation:
            raise Refusal("UNSUPPORTED_INPUT", "a page with a rotated text layer is not supported; export it upright or scan it")
        raw = self._pdfium.raw
        tp = self._page.get_textpage()
        try:
            n = tp.count_chars()
            ptr = tp.raw
            out: list[tuple[str, float, float, float, float]] = []
            cur: list[str] = []
            box: list[float] = []
            obj = None

            def flush() -> None:
                if cur:
                    out.append(("".join(cur), *box))
                cur.clear()
                box.clear()

            high = 0  # pdfium reports UTF-16 code units: a character outside the BMP (an emoji in a payee name) is two of them
            for i in range(n):
                code = raw.FPDFText_GetUnicode(ptr, i)
                if 0xDC00 <= code <= 0xDFFF and high:
                    code, high = 0x10000 + ((high - 0xD800) << 10) + (code - 0xDC00), 0
                    if cur:
                        cur[-1] = chr(code)  # replaces the high half appended at the previous index
                        x0, y0, x1, y1 = _char_extent(tp, i, self._left, self._top)
                        box[0], box[1] = min(box[0], x0), min(box[1], y0)
                        box[2], box[3] = max(box[2], x1), max(box[3], y1)
                    continue
                high = 0
                if 0xD800 <= code <= 0xDBFF:
                    high = code
                if 0xD800 <= code <= 0xDFFF:
                    code = 0xFFFD  # kept only if a low half follows; a lone half is never passed on (it cannot be encoded)
                ch = chr(code) if code else " "
                if ch.isspace() or code == 0:
                    flush()
                    continue
                if not _upright(raw.FPDFText_GetCharAngle(ptr, i)):
                    flush()
                    continue
                this_obj = ctypes.cast(raw.FPDFText_GetTextObject(ptr, i), ctypes.c_void_p).value
                if cur and this_obj != obj:
                    flush()
                obj = this_obj
                x0, y0, x1, y1 = _char_extent(tp, i, self._left, self._top)
                if not cur:
                    box.extend([x0, y0, x1, y1])
                else:
                    box[0], box[1], box[2], box[3] = min(box[0], x0), min(box[1], y0), max(box[2], x1), max(box[3], y1)
                cur.append(ch)
            flush()
            return out
        finally:
            tp.close()

    def render_rgb(self, scale: float):
        bitmap = self._page.render(scale=scale, rev_byteorder=True)
        return bitmap.to_numpy()[:, :, :3].copy()


class ImagePage:
    """A photo or scan as a one-page document. Its size in points follows the image's own DPI (72 if it states none)."""

    def __init__(self, image: Any) -> None:
        dpi = image.info.get("dpi", (72, 72))[0] or 72
        self._image = image.convert("RGB")
        self.width, self.height = image.width * 72 / dpi, image.height * 72 / dpi

    def words(self) -> list[tuple[str, float, float, float, float]]:
        return []  # an image has no text layer

    def render_rgb(self, scale: float):
        import numpy as np

        w, h = max(1, round(self.width * scale)), max(1, round(self.height * scale))
        img = self._image if (w, h) == self._image.size else self._image.resize((w, h))
        return np.asarray(img, dtype=np.uint8).copy()


class Document:
    def __init__(self, pages: Iterator[Any], count: int, close) -> None:
        self._pages, self.page_count, self._close = pages, count, close

    def pages(self) -> Iterator[Any]:
        return self._pages

    def close(self) -> None:
        self._close()


def open_document(source: Path | bytes, *, image: bool = False) -> Document:
    if image:
        try:
            from PIL import Image
        except ImportError as e:
            raise EngineFault("images need Pillow: pip install 'openbooks[scan]'") from e
        try:
            img = Image.open(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
            img.load()
        except Exception:
            raise Refusal("UNSUPPORTED_INPUT", "unreadable document") from None
        return Document(iter([ImagePage(img)]), 1, img.close)
    pdfium = _pdfium()
    try:
        pdf = pdfium.PdfDocument(bytes(source) if isinstance(source, (bytes, bytearray)) else str(source))
    except pdfium.PdfiumError as e:
        if getattr(e, "err_code", None) == pdfium.raw.FPDF_ERR_PASSWORD:
            raise Refusal("UNSUPPORTED_INPUT", "encrypted document") from None
        raise Refusal("UNSUPPORTED_INPUT", "unreadable document") from None
    except Exception:
        raise Refusal("UNSUPPORTED_INPUT", "unreadable document") from None

    def pages() -> Iterator[PdfPage]:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                yield PdfPage(page, pdfium)
            finally:
                page.close()

    return Document(pages(), len(pdf), pdf.close)
