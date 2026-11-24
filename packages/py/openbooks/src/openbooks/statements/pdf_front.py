"""PDF and scan front end for bank statements.

Words with boxes come from the PDF text layer, or from OCR when a page has none. Rows are rebuilt from column
geometry and handed to the same statement builder and balance gate as CSV, so a misread number refuses
(BALANCE_MISMATCH) instead of being released. The optional typed-head model (roles.py) can only add refusals
(LOW_CONFIDENCE), except in the header-less fallback, where it assigns columns and the gate still decides.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

from openbooks.core.builders import statement_doc
from openbooks.core.errors import EngineFault, Refusal
from openbooks.core.normalise import date_order, to_date, to_dec
from openbooks.core.params import Params
from openbooks.statements.ocr_providers import OcrRun, OcrSession, PageInput, ProviderSettings, load_settings, select_engine
from openbooks.statements.pdf_words import _EU, _MONEY, Word, _date_spans, _lines
from openbooks.statements.scan_decimals import _OCR_COMMA_DECIMAL, _repair_scan_decimal_commas  # noqa: F401
from openbooks.statements.table_header import HEADER, _IND, _header_cols, _near, find_header  # noqa: F401

MAX_PAGES, MAX_WORDS_PER_PAGE = 60, 20_000
OCR_DPI, OCR_MAX_PX = 200, 3200
OCR_MIN_DATE_CONF = 0.50
TEXT_LAYER_MIN_WORDS = 5
KNOWN_CCY = {"INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD", "CAD", "JPY"}
_OPEN_CLOSE = re.compile(r"opening balance|closing balance", re.I)



def _text(ln: list[Word]) -> str:
    return " ".join(w.text for w in ln)


def _loc(ws: list[Word]) -> tuple[int, list[float], float | None]:
    confs = [w.conf for w in ws if w.conf is not None]
    box = [round(min(w.x0 for w in ws), 1), round(min(w.y0 for w in ws), 1),
           round(max(w.x1 for w in ws), 1), round(max(w.y1 for w in ws), 1)]
    return ws[0].page, box, (min(confs) if confs else None)


_READER = None
_DOCUMENT_LOCK = threading.Lock()
_RUNS = threading.local()


def ocr_runtime():
    try:
        import easyocr
        import torch
    except (ImportError, OSError, RuntimeError) as e:
        raise EngineFault("Cannot load OCR. Install or repair 'openbooks[scan]' in the engine's Python environment.") from e
    return easyocr, torch


def last_ocr_run() -> OcrRun | None:
    session = getattr(_RUNS, "session", None)
    return session.run if session is not None else None


def last_ocr_session() -> OcrSession | None:
    return getattr(_RUNS, "session", None)


def last_ocr_engines() -> tuple[str, ...]:
    session = getattr(_RUNS, "session", None)
    return session.engine_ids if session is not None else ()


def _ocr_page(page, number: int, session: OcrSession, dpi: float) -> list[Word]:
    with _DOCUMENT_LOCK:
        pw, ph = page.width, page.height
        scale = min(dpi / 72, OCR_MAX_PX / max(pw, ph))
        image = page.render_rgb(scale)
    return _join_split_amounts(session.read_page(PageInput(image, scale, number, (pw, ph))))


_DIGITS_COMMAS = re.compile(r"^[\d,]+$")
_AMOUNT_BODY = re.compile(r"^(?:[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*|0)$")
_JOIN_GAP = 1.5


def _join_split_amounts(ws: list[Word]) -> list[Word]:
    """Fonts like Courier make OCR drop the decimal point: '764.72' -> '764' '72', '10,034.14' -> '10' ',' '034' '14'.
    Adjacent digit/comma pieces ending in exactly two digits are rejoined. A wrong join can only add a refusal:
    the balance gate still has to prove every amount."""
    lines: list[list[Word]] = []
    for w in sorted(ws, key=lambda w: w.cy):
        if lines and abs(w.cy - sum(x.cy for x in lines[-1]) / len(lines[-1])) < 0.6 * w.h:
            lines[-1].append(w)
        else:
            lines.append([w])
    out: list[Word] = []
    for ln in lines:
        ln.sort(key=lambda w: w.x0)
        i = 0
        while i < len(ln):
            j = i
            while j < len(ln) and _DIGITS_COMMAS.match(ln[j].text) and (j == i or ln[j].x0 - ln[j - 1].x1 <= _JOIN_GAP * ln[j].h):
                j += 1
            run = ln[i:j]
            body = "".join(w.text for w in run[:-1]).rstrip(",") if len(run) > 1 else ""
            grouped = len(run) == 2 or re.fullmatch(r"[1-9]\d{0,2}(?:,\d{3})+", body)
            if len(run) > 1 and re.fullmatch(r"\d{2}", run[-1].text) and grouped and _AMOUNT_BODY.match(body):
                w = run[0]
                for nxt in run[1:]:
                    w = _join(w, nxt, "")
                out.append(Word(f"{body}.{run[-1].text}", w.x0, w.y0, w.x1, w.y1, w.page, w.conf, w.pw, w.ph, w.orig))
                i = j
            else:
                out.append(ln[i])
                i += 1
    return out


_OCR_AMOUNT = re.compile(r"^\d[\d.,]*[.,]?[.,]\d{2}$")
_VALID_AMOUNT = re.compile(r"^(\d+|\d{1,3}(,\d{2,3})*)\.\d{2}$")


def _ocr_fix(s: str) -> str:
    """OCR often turns a thousands comma into a period ('2.133.64', '5.,217.37'). Only a malformed token that ends in
    '.dd' is repaired; a valid '1,234.50' and a European '1.000,50' are left alone. The balance gate checks the result."""
    if _OCR_AMOUNT.match(s) and not _VALID_AMOUNT.match(s) and s[-3] == "." and re.search(r"[.,]", s[:-3]):
        return re.sub(r"[.,]", "", s[:-3]) + s[-3:]
    return s


def read_words(path: Path | bytes, p: Params) -> tuple[list[list[Word]], str]:
    _RUNS.session = None
    settings = load_settings()
    session = OcrSession(settings)
    _RUNS.session = session
    return _read_words(path, p, session, settings)


def _locked_pages(doc):
    with _DOCUMENT_LOCK:
        pages = iter(doc.pages())
    while True:
        with _DOCUMENT_LOCK:
            page = next(pages, None)
        if page is None:
            return
        yield page


def _read_words(path: Path | bytes, p: Params, session: OcrSession, settings: ProviderSettings) -> tuple[list[list[Word]], str]:
    from .pdf_backend import open_document

    is_image = isinstance(path, Path) and path.suffix.lower() in (".png", ".jpg", ".jpeg")
    with _DOCUMENT_LOCK:
        doc = open_document(path, image=is_image)
    try:
        with _DOCUMENT_LOCK:
            page_count = doc.page_count
        if page_count > MAX_PAGES:
            raise Refusal("UNSUPPORTED_INPUT", f"more than {MAX_PAGES} pages")
        pages, method = [], "pdf_text"
        ocr_dpi: float | None = None
        for i, page in enumerate(_locked_pages(doc), 1):
            with _DOCUMENT_LOCK:
                pw, ph = page.width, page.height
                ws = [Word(t, x0, y0, x1, y1, i, None, pw, ph) for t, x0, y0, x1, y1 in page.words()]
            if len(ws) < TEXT_LAYER_MIN_WORDS:
                if not p.ocr:
                    raise Refusal("UNSUPPORTED_INPUT", f"page {i} has no text layer and OCR is off")
                if ocr_dpi is None:
                    ocr_dpi = select_engine(settings).preferred_dpi
                ws, method = _repair_scan_decimal_commas(_ocr_page(page, i, session, ocr_dpi)), "ocr"
            if len(ws) > MAX_WORDS_PER_PAGE:
                raise Refusal("UNSUPPORTED_INPUT", f"page {i} has more than {MAX_WORDS_PER_PAGE} words")
            pages.append(ws)
        return pages, method
    finally:
        with _DOCUMENT_LOCK:
            doc.close()




_CCY_PREFIX = re.compile(r"^(?:Rs\.?|INR|₹)\s*(\d[\d,]*\.\d{2})$")


def _join(a: Word, b: Word, text: str) -> Word:
    confs = [c for c in (a.conf, b.conf) if c is not None]
    return Word(text, min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1), a.page, min(confs) if confs else None,
                a.pw, a.ph, f"{a.orig or a.text} {b.orig or b.text}")


def _merge_drcr(line: list[Word]) -> list[Word]:
    """Fold 'Rs.' / 'INR' prefixes and 'Cr' / 'Dr' suffixes into the amount they belong to ('Rs. 935.48', '5,211.10 Cr')."""
    out: list[Word] = []
    for w in line:
        m = _CCY_PREFIX.match(w.text)
        if m:
            w = Word(m.group(1), w.x0, w.y0, w.x1, w.y1, w.page, w.conf, w.pw, w.ph, w.text)
        if out and w.text in ("Dr", "Cr", "DR", "CR") and _MONEY.match(out[-1].text):
            a = out.pop()
            w = _join(a, w, a.text + w.text)
        elif out and out[-1].text in ("Rs", "Rs.", "INR", "₹") and _MONEY.match(w.text):
            a = out.pop()
            w = _join(a, w, w.text)
        out.append(w)
    return out




def _dates(line: list[Word], order: str = "dmy") -> list[tuple[int, int, str, str]]:
    """Every date in a line as (first word, word count, ISO date, raw text), numeric dates read in `order`.
    Impossible dates (31/02, or 15/01 read month-first) raise PARSE_ERROR."""
    return [(i, n, to_date(raw, f"page {line[0].page}", order), raw) for i, n, raw in _date_spans(line)]


def _date_order(all_lines, p: Params) -> str:
    """One day/month order for the whole document, by the bank CSV rule: --date-order wins, a field above 12 proves it,
    otherwise day-first (Indian layouts)."""
    raws = [raw for lines in all_lines for ln in lines for _, _, raw in _date_spans(ln)]
    return date_order(raws, p.date_order, default="dmy", where="statement dates")


def _money_tokens(line: list[Word]) -> list[Word]:
    out = []
    for w in line:
        if _EU.match(w.text):
            raise Refusal("PARSE_ERROR", f"page {w.page}: European number format {w.text!r}")
        if _MONEY.match(w.text):
            out.append(w)
    return out


def _direction(line: list[Word], aw: Word, cols) -> str:
    sfx = re.search(r"(Dr|Cr)$", aw.text, re.I)
    if sfx:
        return _IND[sfx.group(1).lower()]
    near = [w for w in line if w.text.lower() in _IND and abs(w.cx - (cols["ind"].cx if "ind" in cols else aw.cx)) < 60]
    kinds = {_IND[w.text.lower()] for w in near}
    if len(kinds) != 1:
        raise Refusal("PARSE_ERROR", f"page {aw.page}: the debit/credit marker next to {aw.text!r} is missing or ambiguous")
    return kinds.pop()


def _desc_window(cols):
    """x-range of the description column: right of the last header cell before it, left of the first amount/marker cell."""
    if not cols or "desc" not in cols:
        return (-1e9, 1e9)
    right = [cols[r].x0 for r in ("debit", "credit", "amount", "ind") if r in cols]
    left = [w.x1 for r, w in cols.items() if r not in ("desc", "debit", "credit", "amount", "ind", "balance") and w.x1 < cols["desc"].x0]
    return (max(left, default=cols["desc"].x0 - 80) - 2, min(right, default=1e9) - 3)


def _row(line, pick, mode, cols, role_fn, no):
    """pick = the chosen (first word, count, iso, raw) date. Returns (rec, assigned); rec['noop'] marks a no-movement row."""
    start, n_words, iso, raw = pick
    date_ws = line[start:start + n_words]
    money = _money_tokens(line)
    page = line[0].page
    roles = ("debit", "credit", "balance") if mode == "split" else ("amount", "balance")
    by_role: dict[str, list[Word]] = {}
    for w in money:
        by_role.setdefault(role_fn(w), []).append(w)
    amts = [w for r in roles if r != "balance" for w in by_role.get(r, [])]
    if len(by_role.get("balance", [])) != 1 or len(amts) > 1:
        raise Refusal("PARSE_ERROR", f"page {page}: could not read one amount and one balance on the row dated {raw}")
    lo, hi = _desc_window(cols)
    desc = [w for w in line if w not in money and w not in date_ws and lo <= w.cx <= hi and w.text.lower() not in _IND]
    bw = by_role["balance"][0]
    bal, bal_raw = to_dec(bw.text, f"page {page} balance", dr_cr=True), bw.orig or bw.text
    if not amts:
        return {"noop": True, "bal": bal, "bal_raw": bal_raw, "loc": {"balance": _loc([bw])}, "desc_words": desc,
                "cy": bw.cy, "h": bw.h, "page": page}, [(w, "date") for w in date_ws] + [(bw, "balance")] + [(w, "desc") for w in desc]
    aw = amts[0]
    direction = _direction(line, aw, cols or {}) if mode == "single" else ("debit" if aw in by_role.get("debit", []) else "credit")
    amt = abs(to_dec(aw.text, f"page {page} amount", dr_cr=True))
    if amt <= 0:
        raise Refusal("PARSE_ERROR", f"page {page}: amount must be positive")
    rec = {"row": no, "date": iso, "date_raw": raw, "dir": direction, "amt": amt, "amt_raw": aw.orig or aw.text, "bal": bal,
           "bal_raw": bal_raw, "desc_words": desc, "ref": None, "cy": aw.cy, "h": aw.h, "page": page,
           "loc": {"date": _loc(date_ws), "amount": _loc([aw]), "balance": _loc([bw])}}
    return rec, [(w, "date") for w in date_ws] + [(aw, direction), (bw, "balance")] + [(w, "desc") for w in desc]


def _stated(lines: list[list[Word]], label: str):
    found = []
    for ln in lines:
        if re.search(label, _text(ln), re.I) and not _date_spans(ln):
            money = _money_tokens(ln)
            if money:
                w = money[-1]
                found.append((to_dec(w.text, f"stated {label}", dr_cr=True), w.text, _loc([w])))
    return found


def _currency(pages: list[list[Word]], p: Params) -> str:
    seen = {w.text.upper().strip(":.") for pg in pages for w in pg} & KNOWN_CCY
    if any(w.text in ("Rs", "Rs.", "₹") for pg in pages for w in pg):
        seen.add("INR")
    if p.currency:
        cur = p.currency.upper()
        if seen and cur not in seen:
            raise Refusal("PARSE_ERROR", f"document shows {sorted(seen)} but --currency is {cur}")
        return cur
    if len(seen) == 1:
        return next(iter(seen))
    raise Refusal("PARSE_ERROR", "currency not stated in the document; supply --currency")


def _attach_descriptions(page_rows: list[dict], frags: list[tuple[float, float, str]]) -> None:
    """A description fragment printed above or below its row (wrapped text) belongs to the nearest row on the page."""
    for cy, h, text in frags:
        if not page_rows:
            continue
        r = min(page_rows, key=lambda r: abs(r["cy"] - cy))
        if abs(r["cy"] - cy) <= 2.2 * max(h, r["h"]):
            r["frags"].append((cy, text))


def _join_descriptions(rows: list[dict]) -> None:
    """Set each row's description from its own words and its wrapped fragments, in reading order (in place)."""
    for r in rows:
        parts = sorted([(w.cy, w.x0, w.text) for w in r.pop("desc_words")] + [(cy, -1e9, t) for cy, t in r.pop("frags", [])])
        r["desc"] = " ".join(t for _, _, t in parts)


def _rows(all_lines, preds, prev=None, order: str = "dmy"):
    """Walk every page; returns (recs, noops, assigned, model_used). prev = opening balance if known: the
    header-less model path uses the running balance to resolve rows whose column sets are not a single role.
    order = day/month order of numeric dates for the whole document."""
    recs, noops, assigned, hdr, model_used = [], [], [], None, False
    for lines in all_lines:
        found = find_header(lines)
        if found:
            hdr = found[1]
        elif hdr is None and preds is None:
            continue
        mode, cols = hdr if hdr else ("split", None)
        if cols is not None:
            roles = ("debit", "credit", "balance") if mode == "split" else ("amount", "balance")
            role_fn = lambda w, c=cols, r=roles: _near(w, c, r)  # noqa: E731
        else:
            model_used = True
        lo, hi = _desc_window(cols)
        page_rows, frags = [], []
        for ln in lines[found[0] + 1 if found else 0:]:
            ln = _merge_drcr(ln)
            text = _text(ln)
            if _OPEN_CLOSE.search(text) or re.search(r"\bpage \d+ of \d+\b", text, re.I):
                continue
            dates, money = _dates(ln, order), _money_tokens(ln)
            if dates and money:
                pick = min(dates, key=lambda d: abs(ln[d[0]].cx - cols["date"].cx)) if cols else dates[0]
                if cols is None:
                    fixed = preds.resolve(money, prev, lambda w: to_dec(w.text, "model", dr_cr=True))
                    role_fn = fixed.__getitem__
                rec, got = _row(ln, pick, mode, cols, role_fn, len(recs) + 1)
                prev = rec["bal"]
                rec["frags"] = []
                page_rows.append(rec)
                if rec.get("noop"):
                    noops.append({"pos": len(recs), **rec})
                else:
                    recs.append(rec)
                assigned += got
            elif money:
                if not re.match(r"\s*(total|brought forward|carried forward|b/f|c/f)\b", text, re.I):
                    raise Refusal("PARSE_ERROR", f"page {ln[0].page}: a line with amounts is not a transaction row")
            else:
                words = [w for w in ln if lo <= w.cx <= hi]
                if words:
                    frags.append((sum(w.cy for w in words) / len(words), words[0].h, _text(words)))
        _attach_descriptions(page_rows, frags)
    _join_descriptions(recs + noops)
    return recs, noops, assigned, model_used


def extract_statement(pages: list[list[Word]], p: Params, method: str, preds=None):
    """Returns (data, evidence, assigned, model_used). preds is consulted only when no header is found."""
    all_lines = [_lines(pg) for pg in pages]
    flat = [ln for lines in all_lines for ln in lines]
    openings, closings = _stated(flat, r"opening\s+balance"), _stated(flat, r"closing\s+balance")
    order = _date_order(all_lines, p)
    recs, noops, assigned, model_used = _rows(all_lines, preds, p.opening if p.opening is not None else (openings[0][0] if openings else None),
                                              order)
    if not recs:
        raise Refusal("UNKNOWN_LAYOUT", "no statement table found")
    cur = _currency(pages, p)
    if len({o[0] for o in openings}) > 1:
        raise Refusal("PARSE_ERROR", "document states more than one opening balance")
    doc_open = openings[0] if openings else None
    if p.opening is not None and doc_open and doc_open[0] != p.opening:
        raise Refusal("PARSE_ERROR", "supplied opening balance differs from the one printed on the document")
    if p.opening is not None:
        opening = p.opening
    elif doc_open:
        opening = doc_open[0]
    elif p.allow_derived_opening:
        opening = None
    else:
        raise Refusal("PARSE_ERROR", "statement has no stated opening balance; supply --opening")
    if method == "ocr":
        low = [r["row"] for r in recs if (r["loc"]["date"][2] or 1.0) < OCR_MIN_DATE_CONF]
        if low:
            raise Refusal("LOW_CONFIDENCE", f"OCR confidence below {OCR_MIN_DATE_CONF} on dates in rows {low[:10]}")
    full_method = method + ("+model" if model_used else "")
    data, ev = statement_doc(recs, cur, p.account, opening, method=full_method,
                             opening_loc=(doc_open[2], doc_open[1]) if doc_open else None,
                             stated_closing=closings[-1] if closings else None, noops=noops)
    return data, ev, assigned, full_method


def extract_document(path: Path, p: Params):
    pages, method = read_words(path, p)
    preds = None
    if p.model:
        try:
            from .roles import RoleModel
        except (ImportError, OSError, RuntimeError) as e:
            raise Refusal("UNSUPPORTED_INPUT", '--model needs a working PyTorch installation: pip install "openbooks[scan]"') from e
        model = RoleModel.load()
        if model is None:
            raise Refusal("UNSUPPORTED_INPUT", "--model needs the model assets (roles_head.pt and roles_calibration.json): reinstall openbooks, or set OPENBOOKS_MODELS_DIR")
        preds = model.predict(pages)
    data, ev, assigned, full_method = extract_statement(pages, p, method, preds)
    if preds is not None:
        from .roles import crosscheck

        crosscheck(assigned, preds)
    return data, ev, ("pdf" if path.suffix.lower() == ".pdf" else "image"), "bank_statement_pdf.v1", full_method
