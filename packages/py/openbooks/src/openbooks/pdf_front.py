"""PDF and scan front end for bank statements.

Words with boxes come from the PDF text layer, or from OCR when a page has none. Rows are rebuilt from column
geometry and handed to the same statement builder and balance gate as CSV, so a misread number refuses
(BALANCE_MISMATCH) instead of being released. The optional typed-head model (roles.py) can only add refusals
(LOW_CONFIDENCE), except in the header-less fallback, where it assigns columns and the gate still decides.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openbooks_core.builders import statement_doc
from openbooks_core.errors import Refusal
from openbooks_core.normalise import date_order, to_date, to_dec
from openbooks_core.params import Params

MAX_PAGES, MAX_WORDS_PER_PAGE = 60, 20_000
OCR_DPI, OCR_MAX_PX = 200, 3200
OCR_MIN_DATE_CONF = 0.50
TEXT_LAYER_MIN_WORDS = 5
KNOWN_CCY = {"INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD", "CAD", "JPY"}
_MONEY = re.compile(r"^\(?-?\d[\d,]*\.\d{2}\)?(?:Dr|Cr|DR|CR)?$")
_EU = re.compile(r"^\d{1,3}(\.\d{3})+,\d{2}$")
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE_LIKE = re.compile(rf"^(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[ -][A-Za-z]{{3}}[ -]\d{{2,4}}"
                        rf"|\d{{1,2}}[ -](?:{_MONTHS})[ -]\d{{4}})$")
_OPEN_CLOSE = re.compile(r"opening balance|closing balance", re.I)


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    conf: float | None = None
    pw: float = 1.0
    ph: float = 1.0
    orig: str | None = None

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return max(self.y1 - self.y0, 1.0)


def _text(ln: list[Word]) -> str:
    return " ".join(w.text for w in ln)


def _loc(ws: list[Word]) -> tuple[int, list[float], float | None]:
    confs = [w.conf for w in ws if w.conf is not None]
    box = [round(min(w.x0 for w in ws), 1), round(min(w.y0 for w in ws), 1),
           round(max(w.x1 for w in ws), 1), round(max(w.y1 for w in ws), 1)]
    return ws[0].page, box, (min(confs) if confs else None)


_READER = None


def _ocr_page(page, number: int) -> list[Word]:
    import fitz
    import numpy as np

    global _READER
    if _READER is None:
        import easyocr
        import torch

        _READER = easyocr.Reader(["en"], gpu=torch.cuda.is_available(), verbose=False)
    pw, ph = page.rect.width, page.rect.height
    scale = min(OCR_DPI / 72, OCR_MAX_PX / max(pw, ph))
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    out = []
    for poly, text, conf in _READER.readtext(img, paragraph=False):
        xs, ys = [q[0] / scale for q in poly], [q[1] / scale for q in poly]
        compact = text.replace(" ", "")
        parts = [compact] if _OCR_AMOUNT.match(compact) else text.split()
        total = sum(len(s) for s in parts) or 1
        x, span = min(xs), max(xs) - min(xs)
        for s in parts:
            w = span * len(s) / total
            fixed = _ocr_fix(s)
            out.append(Word(fixed, x, min(ys), x + w, max(ys), number, float(conf), pw, ph, s if fixed != s else None))
            x += w
    return _join_split_amounts(out)


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


def _text_words(page, number: int, pw: float, ph: float) -> list[Word]:
    """Words from the text layer, skipping rotated text (watermarks) and breaking at span boundaries."""
    out: list[Word] = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            dx, dy = line["dir"]
            if dx < 0.9 or abs(dy) > 0.05:
                continue
            for span in line["spans"]:
                cur: list[dict] = []
                for ch in span["chars"] + [{"c": " "}]:
                    if ch["c"].isspace():
                        if cur:
                            x0, y0 = min(c["bbox"][0] for c in cur), min(c["bbox"][1] for c in cur)
                            x1, y1 = max(c["bbox"][2] for c in cur), max(c["bbox"][3] for c in cur)
                            out.append(Word("".join(c["c"] for c in cur), x0, y0, x1, y1, number, None, pw, ph))
                        cur = []
                    else:
                        cur.append(ch)
    return out


def read_words(path: Path | bytes, p: Params) -> tuple[list[list[Word]], str]:
    import fitz

    try:
        doc = fitz.open(stream=path, filetype="pdf") if isinstance(path, (bytes, bytearray)) else fitz.open(path)
    except Exception:
        raise Refusal("UNSUPPORTED_INPUT", "unreadable document") from None
    if doc.needs_pass:
        raise Refusal("UNSUPPORTED_INPUT", "encrypted document")
    if doc.page_count > MAX_PAGES:
        raise Refusal("UNSUPPORTED_INPUT", f"more than {MAX_PAGES} pages")
    pages, method = [], "pdf_text"
    for i, page in enumerate(doc, 1):
        pw, ph = page.rect.width, page.rect.height
        ws = _text_words(page, i, pw, ph)
        if len(ws) > MAX_WORDS_PER_PAGE:
            raise Refusal("UNSUPPORTED_INPUT", f"page {i} has more than {MAX_WORDS_PER_PAGE} words")
        if len(ws) < TEXT_LAYER_MIN_WORDS:
            if not p.ocr:
                raise Refusal("UNSUPPORTED_INPUT", f"page {i} has no text layer and OCR is off")
            ws, method = _ocr_page(page, i), "ocr"
        pages.append(ws)
    return pages, method


def _lines(words: list[Word]) -> list[list[Word]]:
    if not words:
        return []
    heights = sorted(w.h for w in words)
    tol = 0.5 * heights[len(heights) // 2]
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.cy, w.x0)):
        if lines and abs(w.cy - sum(x.cy for x in lines[-1]) / len(lines[-1])) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w.x0) for ln in lines]


HEADER = {"date": {"date"}, "desc": {"description", "narration", "particulars", "details", "remarks"},
          "debit": {"debit", "debits", "withdrawal", "withdrawals", "dr"},
          "credit": {"credit", "credits", "deposit", "deposits", "cr"}, "balance": {"balance"},
          "amount": {"amount", "amt"}, "ind": {"crdr", "drcr", "dc", "cd", "type"}}
_IND = {"cr": "credit", "credit": "credit", "dr": "debit", "debit": "debit"}


def _header_cols(line: list[Word]):
    """(mode, {role: Word}) for a header line. mode 'split' = Debit and Credit columns; 'single' = one Amount column
    plus a Cr/Dr marker. None if the line is not a header."""
    if any(_MONEY.match(w.text) for w in line):
        return None
    found: dict[str, list[tuple[int, Word]]] = {}
    for i, w in enumerate(line):
        t = re.sub(r"[^a-z]", "", w.text.lower())
        for role, names in HEADER.items():
            if t in names:
                found.setdefault(role, []).append((i, w))
    split = {"date", "debit", "credit", "balance"} <= found.keys()
    single = {"date", "amount", "balance"} <= found.keys() and not ({"debit", "credit"} & found.keys())
    if not (split or single):
        return None
    cols = {}
    for role, hits in found.items():
        pick = hits[0][1]
        if role == "date":
            pick = next((w for i, w in hits if not (i and line[i - 1].text.lower() == "value")), pick)
        cols[role] = pick
    return ("split" if split else "single"), cols


def _near(w: Word, cols: dict[str, Word], roles: tuple[str, ...]) -> str:
    return min(roles, key=lambda r: min(abs(w.cx - cols[r].cx), abs(w.x1 - cols[r].x1)))


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


def _date_spans(line: list[Word]) -> list[tuple[int, int, str]]:
    """Every date-like span in a line as (first word, word count, raw text)."""
    out, i = [], 0
    while i < len(line):
        for n in (3, 2, 1):
            raw = " ".join(w.text for w in line[i:i + n])
            if i + n <= len(line) and _DATE_LIKE.match(raw):
                out.append((i, n, raw))
                i += n - 1
                break
        i += 1
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


def _rows(all_lines, preds, prev=None, order: str = "dmy"):
    """Walk every page; returns (recs, noops, assigned, model_used). prev = opening balance if known: the
    header-less model path uses the running balance to resolve rows whose column sets are not a single role.
    order = day/month order of numeric dates for the whole document."""
    recs, noops, assigned, hdr, model_used = [], [], [], None, False
    for lines in all_lines:
        found = next(((i, h) for i, ln in enumerate(lines) if (h := _header_cols(ln))), None)
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
    for r in recs + noops:
        parts = sorted([(w.cy, w.x0, w.text) for w in r.pop("desc_words")] + [(cy, -1e9, t) for cy, t in r.pop("frags", [])])
        r["desc"] = " ".join(t for _, _, t in parts)
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
        except ImportError as e:
            raise Refusal("UNSUPPORTED_INPUT", f"--model needs PyTorch ({e.name or 'torch'} is missing): "
                                               'pip install "openbooks[scan]"') from e
        model = RoleModel.load()
        if model is None:
            raise Refusal("UNSUPPORTED_INPUT", "--model needs models/roles_head.pt (run scripts/train_roles.py)")
        preds = model.predict(pages)
    data, ev, assigned, full_method = extract_statement(pages, p, method, preds)
    if preds is not None:
        from .roles import crosscheck

        crosscheck(assigned, preds)
    return data, ev, ("pdf" if path.suffix.lower() == ".pdf" else "image"), "bank_statement_pdf.v1", full_method
