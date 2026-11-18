"""Gate for statements read by OCR. Lived in extra_gate next to the tax rules; it belongs to the statements family."""
from __future__ import annotations


def ocr_dates(b, tx):
    """Dates must be in order on an OCR'd statement (guards OCR date misreads)."""
    if b.get("source_method") == "ocr":
        ds = [t["date"] for t in tx]
        ok = sum(1 for a, c in zip(ds, ds[1:]) if a <= c)
        yield f"{b['id']}: dates are in order (guards OCR date misreads)", f"{max(len(ds) - 1, 0)} steps", f"{ok} steps", False
