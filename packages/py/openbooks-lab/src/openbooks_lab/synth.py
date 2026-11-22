"""Synthetic bank-statement renderer: PDF text layer or scan, with a role label for every word.

Used for golden PDF/scan cases and for training and calibrating the typed heads (roles.py). Layouts vary in
column order, fonts, alignment, header wording, date and number formats, wrapped descriptions and page breaks.
rich=True adds what real Indian statements do: a single Amount column with a Cr/Dr marker, 'Rs.' prefixes,
serial/ID and value-date columns, descriptions wrapped above the row, rotated watermarks and failed rows.
"""
from __future__ import annotations

import io
import random
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import fitz

from openbooks.statements.labels import ROLES  # noqa: E402,F401
FONTS = ["helv", "tiro", "cour"]
HEAD_WORDS = {"date": ["Date", "Txn Date", "Transaction Date"], "desc": ["Description", "Narration", "Particulars", "Transaction Details"],
              "debit": ["Debit", "Withdrawal", "Withdrawals", "Debit Amount", "Withdrawal Amt."],
              "credit": ["Credit", "Deposit", "Deposits", "Credit Amount", "Deposit Amt."], "balance": ["Balance", "Running Balance"],
              "ref": ["Ref No", "Chq/Ref No", "Reference"]}
HEAD_EXTRA = {"amount": ["Amount", "Txn Amount", "Transaction Amount"], "ind": ["Cr/Dr", "Dr/Cr", "Type"],
              "serial": ["No.", "S.No."], "tid": ["Txn ID", "Transaction ID"], "vdate": ["Value Date"]}
SHIFT_HEAD = {"date": ["Posting Date", "Booking Date"], "desc": ["Memo", "Payee / Details"], "debit": ["Payments", "Money Out"],
              "credit": ["Receipts", "Money In"], "balance": ["Bal.", "Closing Bal"], "ref": ["Cheque", "Instrument"]}
DATE_FMTS = ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y"]
WIDE_HEAD = {"date": ["Tran Date", "Entry Date"], "desc": ["Narrative", "Remarks"], "debit": ["Dr Amount", "Outflow"],
             "credit": ["Cr Amount", "Inflow"], "balance": ["Avail Balance", "Ledger Balance"], "ref": ["Doc No", "Voucher"]}
WIDE_EXTRA = {"amount": ["Net Amount", "Value (INR)"], "ind": ["D/C", "Sign"], "serial": ["Sl", "#"], "tid": ["UTR", "Ref ID"],
              "vdate": ["Val Dt"]}
WIDE_SIZES = [7, 8.5, 9.5, 10.5, 11.5, 13]
WIDE_DATE_FMTS = ["%d/%m/%y", "%d-%m-%y"]
MERCHANTS = ["UPI/{n}/Amazon Pay", "NEFT-{n}-ACME LTD", "ATM WDL {n} MUMBAI", "IMPS/{n}/Rent March", "POS {n} BIG BAZAAR",
             "ACH D- {n}-LIC PREMIUM", "CHQ DEP {n}", "INT.PD {n}", "SALARY {n} GLOBEX", "UPI/{n}/Swiggy Order"]
FAMILIES = ("sign", "branch", "skew")
SKEW_HEAD = {"date": ["Trans Date"], "desc": ["Trans. Particulars"], "debit": ["With. Amt.", "Dr"], "credit": ["Dep. Amt.", "Cr"],
             "balance": ["Balance (Dr/Cr)", "Book Balance"], "tid": ["UTR Number"], "vdate": ["Value Date"]}
SKEW_MERCHANTS = ["NEFT CR-{n}-ACME LTD", "BY TRANSFER-{n}", "TO TRANSFER-{n}", "NEFT DR-{n}-GLOBEX", "BY CLEARING {n}"]
NOISY_SCAN = {"dpi": 150, "blur": 1.0, "noise": 18.0}
PAGE_W, PAGE_H = 595, 842
AMT_COLS = ("debit", "credit", "balance", "amount")


@dataclass
class Layout:
    order: list[str]
    font: str
    size: float
    right_amounts: bool
    head: dict[str, str]
    date_fmt: str
    grouping: str
    drcr_balance: bool
    has_header: bool
    widths: dict[str, float]
    line_h: float
    single: bool = False
    ccy_prefix: bool = False
    wrap_above: bool = False
    watermark: bool = False
    extra: dict = field(default_factory=dict)


def _min_widths(cols, widths, head, size, font) -> dict[str, float]:
    widths = dict(widths)
    for c in cols:
        if c != "desc":
            widths[c] = max(widths[c], fitz.get_text_length(head[c], fontname="helv", fontsize=size) + 12)
            if c in AMT_COLS:
                widths[c] = max(widths[c], fitz.get_text_length("Rs. 12,345,678.90 Cr", fontname=font, fontsize=size) + 6)
    return widths


def _fit(cols: list[str], widths: dict[str, float], head: dict[str, str], size: float, font: str = "helv") -> dict[str, float]:
    """No column narrower than its own header or its widest amount (text must not overprint); everything stays on the page."""
    widths = _min_widths(cols, widths, head, size, font)
    widths["desc"] = max(70, widths["desc"] - max(0, sum(widths[c] for c in cols) - 515))
    squeeze = min(1.0, 515 / sum(widths[c] for c in cols))
    return {c: w * squeeze for c, w in widths.items()}


def random_layout(rng: random.Random, shifted: bool = False, rich: bool = False, *, wide: bool = False,
                  family: str | None = None) -> Layout:
    """shifted=True draws sizes, header wording and date formats the training layouts never use (distribution-shift test).
    wide=True does the same with a different vocabulary: extra training/calibration variety that leaves the shifted test unseen.
    family in FAMILIES builds a rich layout of that named family (see _family); the default None draws exactly what it always did."""
    if family is not None and family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}; choose from {FAMILIES}")
    cols = ["date", "desc"] + (["ref"] if rng.random() < 0.3 else [])
    cols += ["debit", "credit"] if rng.random() < 0.65 else ["credit", "debit"]
    cols.append("balance")
    size = rng.choice([6.5, 11, 12] if shifted else WIDE_SIZES if wide else [7.5, 8, 9, 10])
    head = {c: rng.choice(SHIFT_HEAD[c] if shifted else WIDE_HEAD[c] if wide else v) for c, v in HEAD_WORDS.items()}
    widths = {"date": rng.choice([58, 66, 74]), "desc": rng.choice([150, 170, 200]), "ref": 62,
              "debit": rng.choice([66, 72, 80]), "credit": rng.choice([66, 72, 80]), "balance": rng.choice([72, 80, 88])}
    lay = Layout(cols, rng.choice(FONTS), size, rng.random() < 0.8, head, rng.choice(["%Y-%m-%d", "%d %B %Y"] if shifted else WIDE_DATE_FMTS if wide else DATE_FMTS),
                 rng.choice(["western", "western", "indian", "plain"]), rng.random() < 0.2, rng.random() < 0.9, {},
                 size * rng.choice([1.5, 1.7, 2.0]))
    if rich or family:
        _enrich(lay, widths, rng, shifted, wide, single=None if family is None else family == "sign")
        if family:
            _family(lay, widths, rng, family)
            size = lay.size
        while lay.size > 6.5 and 100 + sum(v for c, v in _min_widths(lay.order, widths, lay.head, lay.size, lay.font).items()
                                          if c in lay.order and c != "desc") > 515:
            lay.line_h *= (lay.size - 0.5) / lay.size
            lay.size -= 0.5
    lay.widths = _fit(lay.order, widths, lay.head, size, lay.font)
    return lay


def _enrich(lay: Layout, widths: dict[str, float], rng: random.Random, shifted: bool, wide: bool = False,
            single: bool | None = None) -> None:
    lay.ccy_prefix, lay.wrap_above, lay.watermark = rng.random() < 0.3, rng.random() < 0.3, rng.random() < 0.3
    extra = WIDE_EXTRA if wide else HEAD_EXTRA
    pick = (lambda k: rng.choice(["Value"] if shifted and k == "amount" else extra[k]))
    if rng.random() < 0.35 if single is None else single:
        lay.single = True
        lo = min(lay.order.index("debit"), lay.order.index("credit"))
        lay.order = [c for c in lay.order if c not in ("debit", "credit")]
        lay.order[lo:lo] = ["ind", "amount"]
        lay.head.update({"amount": pick("amount"), "ind": pick("ind")})
        widths.update({"ind": 34, "amount": 84})
    if rng.random() < 0.3:
        lay.order = ["serial", "tid"] + lay.order
        lay.head.update({"serial": pick("serial"), "tid": pick("tid")})
        widths.update({"serial": 24, "tid": 62})
    if rng.random() < 0.25:
        lay.order.insert(lay.order.index("date") + 1, "vdate")
        lay.head["vdate"] = pick("vdate")
        widths["vdate"] = 58


def _family(lay: Layout, widths: dict[str, float], rng: random.Random, family: str) -> None:
    """Specialise an enriched layout into a named family. Flags live in lay.extra and are read by render()."""
    if family == "sign":
        pm = rng.random() < 0.5
        lay.extra.update(sign="pm" if pm else "drcr", bind=True)
        lay.head.update({"ind": "+/-" if pm else "Type", "bind": "Dr/Cr"})
        lay.order.insert(lay.order.index("balance") + 1, "bind")
        widths["bind"] = 30
        lay.drcr_balance = False
    elif family == "branch":
        lay.font, lay.size = "cour", rng.choice([7.5, 8, 9])
        lay.line_h = lay.size * rng.choice([1.5, 1.7])
        lay.head.update({"date": "Date", "desc": "Particulars", "debit": "Debit", "credit": "Credit", "balance": "Balance"})
        lay.order = [c for c in lay.order if c not in ("ref", "serial", "tid", "vdate")]
        lay.wrap_above = False
        lay.extra.update(trunc=rng.choice([18, 22, 26]), chq_in_desc=True)
    else:
        lay.date_fmt = rng.choice(WIDE_DATE_FMTS)
        for c in ("vdate", "tid"):
            if c not in lay.order:
                lay.order.insert(lay.order.index("date") + 1 if c == "vdate" else 0, c)
        widths.update({"tid": 62, "vdate": 58})
        lay.head.update({c: rng.choice(v) for c, v in SKEW_HEAD.items()})
        lay.head["credit"] = SKEW_HEAD["credit"][SKEW_HEAD["debit"].index(lay.head["debit"])]
        lay.drcr_balance = lay.head["balance"].startswith("Balance (")
        lay.extra.update(skew=True)
    for c in ("date", "vdate"):
        if c in widths:
            widths[c] = max(widths[c], fitz.get_text_length("30-Sep-2026", fontname=lay.font, fontsize=lay.size) + 8)


def group(amount: str, style: str) -> str:
    whole, frac = amount.split(".")
    if style == "plain" or len(whole) <= 3:
        return f"{whole}.{frac}"
    if style == "western":
        return f"{int(whole):,}.{frac}"
    head, tail = whole[:-3], whole[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + parts + [tail]) + f".{frac}"


def merchant_rows(rows: list[list[str]], rng: random.Random, pool: list[str] = MERCHANTS) -> list[list[str]]:
    return [[r[0], rng.choice(pool).format(n=rng.randint(100000, 999999))] + r[2:] for r in rows]


def with_failed_rows(rows: list[list[str]], rng: random.Random, k: int) -> list[list[str]]:
    """Insert k failed-transaction rows: no debit or credit, balance equal to the row before (the gate must prove that)."""
    out = [r[:] for r in rows]
    for _ in range(k):
        i = rng.randrange(1, len(out))
        out.insert(i, [out[i - 1][0], "FAILED-INSUFFICIENT FUNDS-UPI/DR/" + str(rng.randint(10**11, 10**12)), "", "", out[i - 1][4]])
    return out


def render(rows: list[list[str]], opening: str | None, lay: Layout, rng: random.Random, *, closing: str | None = None,
           title: str = "Statement of Account (INR)") -> tuple[bytes, list[tuple[int, tuple, str, str]]]:
    """rows: [date dd/mm/yyyy, description, debit, credit, balance]. Returns (pdf bytes, [(page, bbox, role, text)])."""
    doc, cells = fitz.open(), []
    fs, font = lay.size, lay.font
    xs, x = {}, 36.0
    for c in lay.order:
        xs[c] = x
        x += lay.widths[c]

    def put(page, no, text, x0, y, role, right_edge=None):
        w = fitz.get_text_length(text, fontname=font, fontsize=fs)
        x0 = right_edge - w if right_edge is not None else x0
        page.insert_text((x0, y), text, fontname=font, fontsize=fs)
        cells.append((no, (x0 - 0.5, y - fs, x0 + w + 0.5, y + 0.3 * fs), role, text))

    def new_page(no: int, first: bool):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_text((36, 44), title, fontname="helv", fontsize=12)
        if lay.watermark:
            pt = fitz.Point(110, 620)
            page.insert_text(pt, "SYNTHETIC SAMPLE", fontsize=44, color=(0.86, 0.86, 0.86), morph=(pt, fitz.Matrix(-32)))
        y = 70.0
        if first and opening is not None:
            for t, xx in (("Opening Balance:", 36), (group(opening, lay.grouping), 140)):
                page.insert_text((xx, y), t, fontname=font, fontsize=fs)
            y += lay.line_h * 1.5
        if lay.has_header:
            for c in lay.order:
                hx = xs[c] + 2
                if c in AMT_COLS and lay.right_amounts:
                    hx = xs[c] + lay.widths[c] - 4 - fitz.get_text_length(lay.head[c], fontname="helv", fontsize=fs)
                page.insert_text((hx, y), lay.head[c], fontname="helv", fontsize=fs)
            y += lay.line_h
        return page, y

    page, y = new_page(1, True)
    no, bottom = 1, PAGE_H - 60
    for n, r in enumerate(rows, 1):
        char_w = fitz.get_text_length("0123456789", fontname=font, fontsize=fs) / 10
        text, fit = _narration(r[1], lay, rng), max(int((lay.widths["desc"] - 6) / char_w), 8)
        desc_lines = [text[:fit]] if lay.extra.get("trunc") else textwrap.wrap(text, fit) or [""]
        need = lay.line_h * len(desc_lines)
        if y + need > bottom:
            no += 1
            page, y = new_page(no, False)
        try:
            dt = datetime.strptime(r[0], "%d/%m/%Y")
            d, vd = dt.strftime(lay.date_fmt), (dt + timedelta(days=int(bool(lay.extra.get("skew"))))).strftime(lay.date_fmt)
        except ValueError:
            d = vd = r[0]
        pre = "Rs. " if lay.ccy_prefix else ""
        amount = r[2] or r[3]
        direction = "debit" if r[2] else "credit"
        sign = ("-" if direction == "debit" else "+") if lay.extra.get("sign") == "pm" else ("DR" if direction == "debit" else "CR")
        vals = {"date": d, "vdate": vd, "ref": str(rng.randint(100000, 999999)), "serial": str(n), "tid": f"S{rng.randint(10**7, 10**8 - 1)}",
                "debit": pre + group(r[2], lay.grouping) if r[2] else "", "credit": pre + group(r[3], lay.grouping) if r[3] else "",
                "amount": pre + group(amount, lay.grouping) if amount else "", "ind": sign if amount else "",
                "balance": pre + group(r[4], lay.grouping) + (" Cr" if lay.drcr_balance else ""),
                "bind": "Cr" if lay.extra.get("bind") else ""}
        row_y = y + (len(desc_lines) // 2 if lay.wrap_above else 0) * lay.line_h
        for c in lay.order:
            if c == "desc":
                for k, line in enumerate(desc_lines):
                    put(page, no, line, xs[c] + 2, y + k * lay.line_h, "desc")
            elif vals.get(c):
                role = {"ref": "other", "serial": "other", "tid": "other", "vdate": "other", "ind": "other", "bind": "other",
                        "amount": direction}.get(c, c)
                if c in AMT_COLS and lay.right_amounts:
                    put(page, no, vals[c], 0, row_y, role, xs[c] + lay.widths[c] - 4)
                else:
                    put(page, no, vals[c], xs[c] + 2, row_y, role)
        y += need
    if closing is not None:
        for t, xx in (("Closing Balance:", 36), (group(closing, lay.grouping), 140)):
            page.insert_text((xx, y + lay.line_h), t, fontname=font, fontsize=fs)
    for i, pg in enumerate(doc, 1):
        pg.insert_text((PAGE_W / 2 - 30, PAGE_H - 30), f"Page {i} of {len(doc)}", fontname="helv", fontsize=8)
    return doc.tobytes(), cells


def _narration(text: str, lay: Layout, rng: random.Random) -> str:
    if lay.extra.get("chq_in_desc"):
        text = f"CHQ {rng.randint(100000, 999999)} {text}"
    cut = lay.extra.get("trunc")
    return text[:cut] if cut else text


def label_words(words, cells) -> list[str]:
    """Role of each extracted word = role of the rendered cell containing its centre (else 'other')."""
    out = []
    for w in words:
        c = cell_of(w, cells)
        out.append(c[1] if c else "other")
    return out


def cell_of(w, cells):
    """(index, role, text) of the rendered cell containing word w's centre, or None."""
    for i, (no, (x0, y0, x1, y1), role, text) in enumerate(cells):
        if no == w.page and x0 <= w.cx <= x1 and y0 <= w.cy <= y1:
            return i, role, text
    return None


def to_scan(pdf: bytes, rng: random.Random, dpi: int = 200, *, blur: float = 0.6, noise: float = 6.0) -> bytes:
    """Rasterise to an image-only PDF with mild noise and blur, so the OCR path has to read it."""
    import numpy as np
    from PIL import Image, ImageFilter

    src, out = fitz.open(stream=pdf, filetype="pdf"), fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).filter(ImageFilter.GaussianBlur(blur))
        arr = np.asarray(img).astype("float32") + np.random.default_rng(rng.randrange(1 << 30)).normal(0, noise, (pix.height, pix.width, 3))
        buf = io.BytesIO()
        Image.fromarray(arr.clip(0, 255).astype("uint8")).save(buf, "JPEG", quality=90)
        p2 = out.new_page(width=page.rect.width, height=page.rect.height)
        p2.insert_image(p2.rect, stream=buf.getvalue())
    return out.tobytes()
