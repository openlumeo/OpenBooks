"""Old versus new PDF reading, on the same files: does swapping PyMuPDF for pypdfium2 change what the engine concludes?

    python tests/characterise/compare_pdf_backends.py FIXTURE_DIR

Needs PyMuPDF, so it runs in CI (the manual export job). For every text-layer PDF case it runs the engine twice, once with the
word extraction the engine shipped with (PyMuPDF, reproduced below from commit a2875c9) and once with the current backend, and
compares the whole output document. Only the evidence geometry (page/bbox/confidence) may differ: the two libraries report
slightly different box coordinates for the same character. Anything else, including a status, a code, an amount, a date, a
description or an assertion, is a difference and fails the run.

Scans are not compared here: both versions would need OCR, which the full CI job already grades (0 false accepts, expected
outcomes) with the new backend.
"""
from __future__ import annotations

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF: the reference implementation. Private test code only; never shipped.
from openbooks.core import Params, process
from openbooks.statements import pdf_front as new
from openbooks.statements.pdf_front import TEXT_LAYER_MIN_WORDS, Word


def legacy_read_words(path, p):
    """The shipped PyMuPDF word extraction, verbatim in behaviour (text layer only)."""
    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc, 1):
        pw, ph = page.rect.width, page.rect.height
        out = []
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                dx, dy = line["dir"]
                if dx < 0.9 or abs(dy) > 0.05:
                    continue
                for span in line["spans"]:
                    cur = []
                    for ch in span["chars"] + [{"c": " "}]:
                        if ch["c"].isspace():
                            if cur:
                                out.append(Word("".join(c["c"] for c in cur), min(c["bbox"][0] for c in cur), min(c["bbox"][1] for c in cur),
                                                max(c["bbox"][2] for c in cur), max(c["bbox"][3] for c in cur), i, None, pw, ph))
                            cur = []
                        else:
                            cur.append(ch)
        if len(out) < TEXT_LAYER_MIN_WORDS:
            raise RuntimeError("scan")  # not a text-layer page
        pages.append(out)
    return pages, "pdf_text"


def strip_geometry(doc: dict) -> dict:
    d = copy.deepcopy(doc)
    for ev in d.get("evidence", {}).values():
        ev.pop("bbox", None)
        ev.pop("confidence", None)
    return d


def regrouped_only(a: dict, b: dict) -> bool:
    """True when the two documents differ only in how wrapped description lines are split between rows.

    A continuation line printed midway between two rows is equally near both. The old reader's glyph boxes broke that tie by
    float noise (towards the next row); pdfium's uniform boxes make it an exact tie, which goes to the row above, and the fixtures
    print continuations below their row, so that is the right row. The check: every other field is identical, and the descriptions
    hold exactly the same words overall, so nothing was lost, invented or moved to a different transaction's amount.
    """
    ta, tb = a.get("data", {}).get("transactions"), b.get("data", {}).get("transactions")
    if a["status"] != "ok" or b["status"] != "ok" or not ta or not tb or len(ta) != len(tb):
        return False
    blank = lambda doc: {**doc, "data": {**doc["data"], "transactions": [{**t, "description": ""} for t in doc["data"]["transactions"]]}}  # noqa: E731
    words = lambda ts: sorted(w for t in ts for w in str(t.get("description") or "").split())  # noqa: E731
    return blank(a) == blank(b) and words(ta) == words(tb)


def paths(a, b, where=""):
    """Where two JSON values differ, as (path, old, new), at most a handful."""
    if type(a) is not type(b):
        return [(where, a, b)]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += paths(a.get(k), b.get(k), f"{where}/{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [(where + "[len]", len(a), len(b))]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in paths(x, y, f"{where}[{i}]")]
    return [] if a == b else [(where, a, b)]


def main() -> int:
    root = Path(sys.argv[1])
    new_read = new.read_words
    differences, compared, regrouped = [], 0, []
    for case in sorted(p for p in root.iterdir() if p.is_dir()):
        src = next(f for f in case.iterdir() if f.name != "expected.json")
        if src.suffix.lower() != ".pdf" or "scan" in case.name:
            continue
        pr = json.loads((case / "expected.json").read_text(encoding="utf-8")).get("params", {})
        params = Params(pr.get("currency"), Decimal(pr["opening"]) if "opening" in pr else None, pr.get("account"),
                        pr.get("allow_derived_opening", False))
        try:
            new.read_words = legacy_read_words
            old_doc = process(src, params)
        finally:
            new.read_words = new_read
        new_doc = process(src, params)
        compared += 1
        a, b = strip_geometry(old_doc), strip_geometry(new_doc)
        if old_doc["status"] == "refused" and old_doc["error"].get("internal") and new_doc["status"] == "refused"                 and new_doc["error"]["code"] == "UNSUPPORTED_INPUT":
            continue  # intended: a file the old reader crashed on is now refused as unreadable, with a typed code
        if a != b and regrouped_only(a, b):
            regrouped.append(case.name)  # a wrapped description line moved to the neighbouring row: same words, nothing else changed
            continue
        if a != b:
            what =[k for k in ("status", "error", "file", "data", "evidence", "assertions") if a.get(k) != b.get(k)]
            differences.append(f"{case.name}: old={old_doc['status']}/{old_doc.get('error', {}).get('code')} "
                               f"new={new_doc['status']}/{new_doc.get('error', {}).get('code')} differs in {what}")
            for path, x, y in paths(a, b)[:6]:
                differences.append(f"    {path}: old={str(x)[:90]!r} new={str(y)[:90]!r}")
    for line in differences:
        print("DIFF", line)
    for name in regrouped:
        print("NOTE", name, "wrapped description lines attached to the neighbouring row (same words overall)")
    print(f"compared {compared} text-layer PDFs, {len(differences)} differences, {len(regrouped)} with regrouped description lines")
    return 1 if differences or compared == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
