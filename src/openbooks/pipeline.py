"""Open Books deterministic pipeline: guard -> detect -> parse -> normalise -> gate -> validate.

Output contract is openbooks.v1 (see PRD). A file is either proven (every assertion
passes, at least one is independent evidence) or refused with a typed code.
Money is Decimal end to end; nothing is rounded silently.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import jsonschema

SCHEMA_VERSION = "openbooks.v1"
MAX_BYTES = 20 * 1024 * 1024
TEXT_EXT = {".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt"}
DOC_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_EXT = TEXT_EXT | DOC_EXT | {".xlsx"}
# ISO 4217 minor units; every other currency is 2.
EXPONENT = {**dict.fromkeys(("BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI", "VND", "VUV",
                             "XAF", "XOF", "XPF"), 0),
            **dict.fromkeys(("BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"), 3)}
HEADER_SCAN_ROWS = 30
FX_TOLERANCE = Decimal("0.01")


class Refusal(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Params:
    currency: str | None = None
    opening: Decimal | None = None
    account: str | None = None
    allow_derived_opening: bool = False
    ocr: bool = True
    model: bool = False


_PLAIN = re.compile(r"\d+(\.\d+)?")
# Digit grouping must be one consistent system. Mixed or ragged groups (12,345,67  1,23) are a dropped or mistyped digit,
# not a number, so they refuse instead of being read as something else.
_WESTERN = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")
_INDIAN = re.compile(r"\d{1,2}(,\d{2})*,\d{3}(\.\d+)?")


def to_dec(raw: str, where: str, *, blank_zero: bool = False, dr_cr: bool = False) -> Decimal:
    s = raw.strip()
    if not s:
        if blank_zero:
            return Decimal(0)
        raise Refusal("PARSE_ERROR", f"{where}: empty amount")
    sign = 1
    if dr_cr and s.lower().endswith("dr"):
        sign, s = -1, s[:-2].strip()
    elif dr_cr and s.lower().endswith("cr"):
        s = s[:-2].strip()
    if s.startswith("(") and s.endswith(")"):
        sign, s = -sign, s[1:-1].strip()
    if s[:1] == "-":
        sign, s = -sign, s[1:].strip()
    elif s[:1] == "+":
        s = s[1:].strip()
    ok = (_WESTERN.fullmatch(s) or _INDIAN.fullmatch(s)) if "," in s else _PLAIN.fullmatch(s)
    if not ok:
        raise Refusal("PARSE_ERROR", f"{where}: not a number: {raw!r}")
    return Decimal(s.replace(",", "")) * sign


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%d-%B-%Y", "%d/%m/%y", "%d-%m-%y",
                 "%d.%m.%Y", "%d.%m.%y", "%Y/%m/%d", "%Y%m%d", "%d-%b-%y", "%d %b %y", "%d/%b/%Y", "%d/%b/%y",
                 "%b %d, %Y", "%B %d, %Y", "%d %b, %Y")
_TIME_TAIL = re.compile(r"[ T]\d{1,2}:\d{2}(:\d{2})?(\s?[APap][Mm])?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")
YEAR_RANGE = (1970, 2100)  # outside this is an OCR or typing error, not a statement date


def to_date(raw: str, where: str) -> str:
    """Day-first for numeric dates (05/01/2026 is 5 January); a first field above 12 is never read as a month.
    Two-digit years are 20yy. A year outside YEAR_RANGE refuses."""
    s = re.sub(r"\bSept\b", "Sep", _TIME_TAIL.sub("", raw.strip()))
    for fmt_ in _DATE_FORMATS:
        if fmt_ == "%Y%m%d" and not (s.isdigit() and len(s) == 8):
            continue
        try:
            d = datetime.strptime(s, fmt_).date()
        except ValueError:
            continue
        if "%y" in fmt_ and d.year < 2000:
            d = d.replace(year=d.year + 100)
        if not YEAR_RANGE[0] <= d.year <= YEAR_RANGE[1]:
            raise Refusal("PARSE_ERROR", f"{where}: implausible year in date {raw!r}")
        return d.isoformat()
    raise Refusal("PARSE_ERROR", f"{where}: unreadable date {raw!r}")


def fmt(d: Decimal, cur: str) -> str:
    q = Decimal(1).scaleb(-EXPONENT.get(cur, 2))
    if d != d.quantize(q):
        raise Refusal("PARSE_ERROR", f"{d} has more decimals than {cur} allows")
    d = d.quantize(q)
    return format(Decimal(0) if d == 0 else d, "f")


def money(d: Decimal, cur: str) -> dict:
    return {"amount": fmt(d, cur), "currency": cur}


def norm(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_")


def mask(s: str | None) -> str:
    return "" if not s else "****" + s[-4:]


def evidence(ev: dict, rid: str, field: str, row: int | None, raw: str, *, page: int | None = None,
             bbox: list[float] | None = None, method: str = "parser", conf: float | None = None) -> None:
    ev[f"{rid}.{field}"] = {"page": page, "bbox": bbox, "row": row, "raw_text": raw, "method": method}
    if conf is not None:
        ev[f"{rid}.{field}"]["confidence"] = round(conf, 4)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def guard(path: Path) -> bytes:
    if path.suffix.lower() not in ALLOWED_EXT:
        raise Refusal("UNSUPPORTED_INPUT", f"file type {path.suffix!r} is not supported")
    if path.stat().st_size > MAX_BYTES:
        raise Refusal("UNSUPPORTED_INPUT", "file is over the 20 MB limit")
    raw = path.read_bytes()
    if path.suffix.lower() in TEXT_EXT and b"\x00" in raw:
        raise Refusal("UNSUPPORTED_INPUT", "binary content")
    return raw


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise Refusal("UNSUPPORTED_INPUT", "text is neither UTF-8 nor cp1252")


BANK_ROLES = {
    "date": ("txn_date", "transaction_date", "value_date", "posting_date", "date"),
    "desc": ("description", "narration", "particulars", "transaction_remarks", "details"),
    "debit": ("debit", "withdrawal", "withdrawals", "withdrawal_amt", "debit_amount", "dr"),
    "credit": ("credit", "deposit", "deposits", "deposit_amt", "credit_amount", "cr"),
    "balance": ("balance", "closing_balance", "running_balance"),
    "ref": ("ref_no", "reference", "chq_ref_no", "utr", "cheque_no"),
}
STRIPE_REQ = {"balance_transaction_id", "created", "currency", "gross", "fee", "net"}
RAZORPAY_REQ = {"entity_id", "type", "debit", "credit", "amount", "fee", "tax", "settlement_id"}
TDS_REQ = {"deductor_name", "tan", "section", "transaction_date", "amount_paid_credited", "tax_deducted", "tds_deposited"}
AIS_REQ = {"information_category", "information_description", "source", "reported_value"}
FIRA_REQ = {"fira_no", "date", "currency", "foreign_amount", "exchange_rate", "inr_amount"}
TB_REQ = {"account", "debit", "credit"}


def bank_cols(hs: list[str]) -> dict[str, int]:
    return {r: hs.index(next(n for n in names if n in hs)) for r, names in BANK_ROLES.items() if any(n in hs for n in names)}


def find_header(rows: list[list[str]]) -> tuple[int, str, list[str]] | None:
    for i, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        hs = [norm(c) for c in row]
        s = set(hs)
        if STRIPE_REQ <= s:
            return i, "stripe_balance.v1", hs
        if RAZORPAY_REQ <= s:
            return i, "razorpay_settlement.v1", hs
        for req, layout in ((TDS_REQ, "tds_26as.v1"), (AIS_REQ, "ais.v1"), (FIRA_REQ, "fira.v1")):
            if req <= s:
                return i, layout, hs
        if {"date", "desc", "debit", "credit", "balance"} <= set(bank_cols(hs)):
            return i, "bank_csv.v1", hs
        if TB_REQ <= s:
            return i, "trial_balance.v1", hs
    return None


def detect(text: str):
    """Returns (format, layout_version, parser args). Unknown layouts are refused, never guessed."""
    head = text[:400].upper()
    if "<OFX" in head or "OFXHEADER" in head:
        return "ofx", "ofx.v1", None
    if all(re.search(rf"^:{t}:", text, re.M) for t in ("20", "60[FM]", "62[FM]")):
        return "mt940", "mt940.v1", None
    for delim in (",", ";", "\t"):
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        hit = find_header(rows)
        if hit:
            return "csv", hit[1], (rows, hit[0], hit[2])
    raise Refusal("UNKNOWN_LAYOUT", "no known layout matches this file")


def _empty_data() -> dict:
    return {"accounts": [], "parties": [], "batches": [], "transactions": [], "claims": []}


def _currency(hs: list[str], body: list[list[str]], p: Params) -> str:
    if "currency" in hs:
        i = hs.index("currency")
        vals = {r[i].strip().upper() for r in body if len(r) > i and r[i].strip()}
        if len(vals) == 1:
            return vals.pop()
        raise Refusal("PARSE_ERROR", f"expected one currency, found {sorted(vals)}")
    if p.currency:
        return p.currency.upper()
    raise Refusal("PARSE_ERROR", "currency not in file; supply --currency")


def _body(rows, hi, hs):
    out = []
    for n, row in enumerate(rows[hi + 1:], start=hi + 2):
        if not any(c.strip() for c in row):
            continue
        if len(row) < len(hs):
            raise Refusal("PARSE_ERROR", f"row {n}: expected {len(hs)} columns, got {len(row)}")
        out.append((n, row))
    if not out:
        raise Refusal("PARSE_ERROR", "no data rows")
    return out


def parse_bank_csv(args, p: Params):
    rows, hi, hs = args
    idx = bank_cols(hs)
    body = _body(rows, hi, hs)
    cur = _currency(hs, [r for _, r in body], p)
    if p.opening is None and not p.allow_derived_opening:
        raise Refusal("PARSE_ERROR", "statement has no stated opening balance; supply --opening")
    recs = []
    for n, row in body:
        def g(role: str) -> str:
            return row[idx[role]].strip() if role in idx else ""

        deb = to_dec(g("debit"), f"row {n} debit", blank_zero=True)
        cre = to_dec(g("credit"), f"row {n} credit", blank_zero=True)
        if (deb and cre) or not (deb or cre) or deb < 0 or cre < 0:
            raise Refusal("PARSE_ERROR", f"row {n}: need exactly one positive debit or credit")
        recs.append({
            "row": n, "date": to_date(g("date"), f"row {n}"), "dir": "credit" if cre else "debit",
            "amt": cre or deb, "amt_raw": g("credit") if cre else g("debit"), "date_raw": g("date"),
            "bal": to_dec(g("balance"), f"row {n} balance", dr_cr=True), "bal_raw": g("balance"),
            "desc": g("desc"), "ref": g("ref") or None,
        })
    return statement_doc(recs, cur, p.account, p.opening)


def statement_doc(recs, cur, account, opening, *, method="parser", opening_loc=None, stated_closing=None, noops=()):
    """Shared by CSV, PDF and scan paths. Each rec may carry loc={field: (page, bbox, conf)}.
    opening=None means derived from the first row (not independent). stated_closing=(Decimal, raw, loc)."""
    if recs[0]["date"] > recs[-1]["date"]:
        recs.reverse()
        noops = [{**n, "pos": len(recs) - n["pos"]} for n in noops]
    derived = opening is None
    if derived:
        opening = recs[0]["bal"] - (recs[0]["amt"] if recs[0]["dir"] == "credit" else -recs[0]["amt"])
    data, ev = _empty_data(), {}

    def put(rid, field, raw, row=None, loc=None):
        page, bbox, conf = loc or (None, None, None)
        evidence(ev, rid, field, row, raw, page=page, bbox=bbox, method=method if loc else "parser", conf=conf)

    data["accounts"].append({"id": "acct-1", "number": account, "currency": cur})
    batch = {"id": "batch-1", "kind": "statement", "account_id": "acct-1", "currency": cur,
             "period_start": recs[0]["date"], "period_end": recs[-1]["date"],
             "opening": money(opening, cur), "closing": money(recs[-1]["bal"], cur), "opening_derived": derived}
    if method != "parser":
        batch["source_method"] = method
    if stated_closing:
        batch["stated_closing"] = money(stated_closing[0], cur)
    data["batches"].append(batch)
    put("batch-1", "opening", "derived from first row balance" if derived else (
        "supplied by caller" if opening_loc is None else opening_loc[1]), loc=None if opening_loc is None else opening_loc[0])
    first, last = recs[0], recs[-1]
    put("batch-1", "closing", last["bal_raw"], last["row"], last.get("loc", {}).get("balance"))
    put("batch-1", "period_start", first["date_raw"], first["row"], first.get("loc", {}).get("date"))
    put("batch-1", "period_end", last["date_raw"], last["row"], last.get("loc", {}).get("date"))
    if stated_closing:
        put("batch-1", "stated_closing", stated_closing[1], loc=stated_closing[2])
    if noops:
        batch["no_movement"] = [{"after": f"txn-{n['pos']:05d}" if n["pos"] else "opening", "balance": money(n["bal"], cur)} for n in noops]
        for k, n in enumerate(noops):
            put("batch-1", f"no_movement.{k}.balance", n["bal_raw"], None, n["loc"].get("balance"))
    for k, r in enumerate(recs, 1):
        tid = f"txn-{k:05d}"
        data["transactions"].append({
            "id": tid, "batch_id": "batch-1", "account_id": "acct-1", "date": r["date"], "direction": r["dir"],
            "amount": money(r["amt"], cur), "balance_after": money(r["bal"], cur),
            "description": r["desc"], "reference": r["ref"],
        })
        loc = r.get("loc", {})
        put(tid, "date", r["date_raw"], r["row"], loc.get("date"))
        put(tid, "amount", r["amt_raw"], r["row"], loc.get("amount"))
        put(tid, "balance_after", r["bal_raw"], r["row"], loc.get("balance"))
    return data, ev


def _settlement(data, ev, cur, txns, payout, payout_raw):
    dates = [t["date"] for t in txns]
    data["batches"].append({
        "id": "batch-1", "kind": "settlement", "currency": cur, "period_start": min(dates), "period_end": max(dates),
        "payout": None if payout is None else money(payout, cur),
    })
    evidence(ev, "batch-1", "period_start", None, min(dates))
    evidence(ev, "batch-1", "period_end", None, max(dates))
    if payout is not None:
        evidence(ev, "batch-1", "payout", None, payout_raw)
    data["transactions"].extend(txns)


def parse_stripe(args, p: Params):
    rows, hi, hs = args
    body = _body(rows, hi, hs)
    cur = _currency(hs, [r for _, r in body], p)

    def col(r, name):
        return r[hs.index(name)].strip() if name in hs else ""

    data, ev, txns, payouts = _empty_data(), {}, [], []
    for n, row in body:
        cat = col(row, "reporting_category")
        if cat == "payout":
            payouts.append((n, row))
            continue
        tid = f"txn-{len(txns) + 1:05d}"
        t = {"id": tid, "batch_id": "batch-1", "date": to_date(col(row, "created"), f"row {n}"),
             "kind": cat or "other", "reference": col(row, "balance_transaction_id") or None}
        for f in ("gross", "fee", "net"):
            t[f] = money(to_dec(col(row, f), f"row {n} {f}", blank_zero=(f == "fee")), cur)
            evidence(ev, tid, f, n, col(row, f))
        evidence(ev, tid, "date", n, col(row, "created"))
        txns.append(t)
    if not txns or len(payouts) > 1:
        raise Refusal("PARSE_ERROR", "need at least one transaction and at most one payout row")
    payout = payout_raw = None
    if payouts:
        n, row = payouts[0]
        payout, payout_raw = -to_dec(col(row, "net"), f"row {n} payout net"), col(row, "net")
    _settlement(data, ev, cur, txns, payout, payout_raw)
    return data, ev


def parse_razorpay(args, p: Params):
    rows, hi, hs = args
    body = _body(rows, hi, hs)
    cur = _currency(hs, [r for _, r in body], p)

    def col(r, name):
        return r[hs.index(name)].strip() if name in hs else ""

    created = "created_at" if "created_at" in hs else "settled_at"
    data, ev, txns, payouts = _empty_data(), {}, [], []
    for n, row in body:
        deb = to_dec(col(row, "debit"), f"row {n} debit", blank_zero=True)
        cre = to_dec(col(row, "credit"), f"row {n} credit", blank_zero=True)
        if col(row, "type") == "settlement":
            payouts.append((n, deb))
            continue
        tid = f"txn-{len(txns) + 1:05d}"
        amt = to_dec(col(row, "amount"), f"row {n} amount")
        t = {"id": tid, "batch_id": "batch-1", "date": to_date(col(row, created), f"row {n}"),
             "kind": col(row, "type") or "other", "reference": col(row, "entity_id") or None,
             "gross": money(amt if cre else -amt, cur),
             "fee": money(to_dec(col(row, "fee"), f"row {n} fee", blank_zero=True), cur),
             "tax": money(to_dec(col(row, "tax"), f"row {n} tax", blank_zero=True), cur), "net": money(cre - deb, cur)}
        for f, raw in (("gross", col(row, "amount")), ("fee", col(row, "fee")), ("tax", col(row, "tax")),
                       ("net", f"credit={col(row, 'credit')} debit={col(row, 'debit')}"), ("date", col(row, created))):
            evidence(ev, tid, f, n, raw)
        txns.append(t)
    if not txns or len(payouts) > 1:
        raise Refusal("PARSE_ERROR", "need at least one transaction and at most one settlement row")
    payout = payouts[0][1] if payouts else None
    _settlement(data, ev, cur, txns, payout, f"row {payouts[0][0]} debit" if payouts else "")
    return data, ev


_TAG = re.compile(r"^:(\d{2}[A-Z]?):(.*)$")
_MT_BAL = re.compile(r"([CD])(\d{6})([A-Z]{3})(\d+,\d*)")
_MT_TXN = re.compile(r"(\d{6})(\d{4})?(R?[CD])([A-Z])?(\d+,\d*)N([A-Z0-9]{3})(.*)", re.S)


def _mt_fields(text: str) -> list[list[str]]:
    out: list[list[str]] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        m = _TAG.match(line)
        if m:
            out.append([m.group(1), m.group(2)])
        elif out and line.strip() not in ("", "-", "-}") and not line.startswith(("{", "}")):
            out[-1][1] += "\n" + line
    return out


def _mt_date(yymmdd: str, where: str) -> str:
    try:
        return datetime.strptime(yymmdd, "%y%m%d").date().isoformat()
    except ValueError:
        raise Refusal("PARSE_ERROR", f"{where}: unreadable date {yymmdd!r}") from None


def _mt_bal(v: str, where: str):
    m = _MT_BAL.fullmatch(v.strip())
    if not m:
        raise Refusal("PARSE_ERROR", f"{where}: unreadable balance {v!r}")
    sign = 1 if m.group(1) == "C" else -1
    return sign * Decimal(m.group(4).replace(",", ".")), _mt_date(m.group(2), where), m.group(3)


def parse_mt940(text: str, p: Params):
    stmts: list[dict] = []
    for tag, val in _mt_fields(text):
        if tag == "20":
            stmts.append({"txns": [], "open": None, "close": None})
        elif not stmts:
            continue
        elif tag == "25":
            stmts[-1]["acct"] = val.strip()
        elif tag in ("60F", "60M") and stmts[-1]["open"] is None:
            stmts[-1]["open"] = (_mt_bal(val, "opening"), val.strip())
        elif tag in ("62F", "62M"):
            stmts[-1]["close"] = (_mt_bal(val, "closing"), val.strip())
        elif tag == "61":
            m = _MT_TXN.fullmatch(val.split("\n")[0].strip())
            if not m:
                raise Refusal("PARSE_ERROR", f":61: unreadable {val!r}")
            stmts[-1]["txns"].append({"m": m, "raw": val.split("\n")[0].strip(), "info": ""})
        elif tag == "86" and stmts[-1]["txns"]:
            stmts[-1]["txns"][-1]["info"] = " ".join(x.strip() for x in val.split("\n"))
    data, ev, accts = _empty_data(), {}, {}
    for si, s in enumerate(stmts, 1):
        if not (s.get("acct") and s["open"] and s["close"]):
            raise Refusal("PARSE_ERROR", f"statement {si}: missing :25:, :60F: or :62F:")
        (ob, od, ocur), oraw = s["open"]
        (cb, cd, ccur), craw = s["close"]
        if ocur != ccur:
            raise Refusal("PARSE_ERROR", f"statement {si}: currency changes inside statement")
        aid = accts.setdefault(s["acct"], f"acct-{len(accts) + 1}")
        if not any(a["id"] == aid for a in data["accounts"]):
            data["accounts"].append({"id": aid, "number": s["acct"], "currency": ocur})
        bid = f"batch-{si}"
        data["batches"].append({"id": bid, "kind": "statement", "account_id": aid, "currency": ocur,
                                "period_start": od, "period_end": cd, "opening": money(ob, ocur),
                                "closing": money(cb, ocur), "opening_derived": False})
        for f, raw in (("opening", oraw), ("closing", craw), ("period_start", oraw), ("period_end", craw)):
            evidence(ev, bid, f, None, raw)
        for k, t in enumerate(s["txns"], 1):
            m = t["m"]
            tid = f"txn-{si}-{k:05d}"
            credit = m.group(3) in ("C", "RD")
            ref = m.group(7).split("//")[0].strip()
            data["transactions"].append({
                "id": tid, "batch_id": bid, "account_id": aid, "date": _mt_date(m.group(1), tid),
                "direction": "credit" if credit else "debit",
                "amount": money(Decimal(m.group(5).replace(",", ".")), ocur),
                "description": t["info"], "reference": None if ref in ("", "NONREF") else ref,
            })
            evidence(ev, tid, "date", None, t["raw"])
            evidence(ev, tid, "amount", None, t["raw"])
    if not data["transactions"]:
        raise Refusal("PARSE_ERROR", "no :61: transactions")
    return data, ev


def _ofx_tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}>([^<\r\n]*)", block, re.I)
    return m.group(1).strip() if m else None


def parse_ofx(text: str, p: Params):
    chunks = [c for c in re.split(r"(?=<STMTRS>|<CCSTMTRS>)", text, flags=re.I) if re.match(r"<(CC)?STMTRS>", c, re.I)]
    if not chunks:
        raise Refusal("PARSE_ERROR", "no statement response in OFX")
    if p.opening is None:
        raise Refusal("PARSE_ERROR", "OFX carries no opening balance; supply --opening")
    if len(chunks) > 1:
        raise Refusal("PARSE_ERROR", "multi-statement OFX with one --opening is ambiguous")
    c = chunks[0]
    cur = (_ofx_tag(c, "CURDEF") or p.currency or "").upper()
    acct = _ofx_tag(c, "ACCTID")
    bal = _ofx_tag(c, "BALAMT")
    if not (cur and bal):
        raise Refusal("PARSE_ERROR", "OFX missing CURDEF or LEDGERBAL")
    blocks = re.findall(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>|</CCSTMTTRNRS>|$)", c, re.S | re.I)
    data, ev = _empty_data(), {}
    data["accounts"].append({"id": "acct-1", "number": acct, "currency": cur})
    seen, dates = set(), []
    for k, b in enumerate(blocks, 1):
        fit, amt_raw, dt = _ofx_tag(b, "FITID"), _ofx_tag(b, "TRNAMT"), _ofx_tag(b, "DTPOSTED")
        if not (fit and amt_raw and dt) or fit in seen:
            raise Refusal("PARSE_ERROR", f"transaction {k}: missing field or duplicate FITID")
        seen.add(fit)
        amt = to_dec(amt_raw, f"txn {k} amount")
        if amt == 0:
            raise Refusal("PARSE_ERROR", f"txn {k}: zero amount")
        tid = f"txn-{k:05d}"
        if not re.match(r"\d{8}", dt):
            raise Refusal("PARSE_ERROR", f"{tid}: unreadable DTPOSTED {dt!r}")
        d = datetime.strptime(dt[:8], "%Y%m%d").date().isoformat()
        dates.append(d)
        data["transactions"].append({
            "id": tid, "batch_id": "batch-1", "account_id": "acct-1", "date": d,
            "direction": "credit" if amt > 0 else "debit", "amount": money(abs(amt), cur),
            "description": _ofx_tag(b, "NAME") or _ofx_tag(b, "MEMO") or "", "reference": fit,
        })
        evidence(ev, tid, "date", None, dt)
        evidence(ev, tid, "amount", None, amt_raw)
    if not dates:
        raise Refusal("PARSE_ERROR", "no transactions")
    data["batches"].append({
        "id": "batch-1", "kind": "statement", "account_id": "acct-1", "currency": cur,
        "period_start": min(dates), "period_end": max(dates), "opening": money(p.opening, cur),
        "closing": money(to_dec(bal, "LEDGERBAL"), cur), "opening_derived": False,
    })
    evidence(ev, "batch-1", "opening", None, "supplied by caller")
    evidence(ev, "batch-1", "closing", None, bal)
    evidence(ev, "batch-1", "period_start", None, min(dates))
    evidence(ev, "batch-1", "period_end", None, max(dates))
    return data, ev


def D(m: dict) -> Decimal:
    return Decimal(m["amount"])


def fx_check(foreign: Decimal, rate: Decimal, inr: Decimal) -> bool:
    """INR amount equals foreign x rate within 0.01 INR. Not wired to a parser until FIRA exists."""
    return abs(foreign * rate - inr) <= FX_TOLERANCE


def run_gate(data: dict) -> list[dict]:
    out: list[dict] = []

    def add(rule, expected, computed, independent):
        out.append({"id": f"A{len(out) + 1}", "rule": rule, "expected": expected, "computed": computed,
                    "passed": expected == computed, "independent": independent})

    def amt(d, cur):
        return f"{fmt(d, cur)} {cur}"

    statements = [b for b in data["batches"] if b["kind"] == "statement"]
    for b in statements:
        cur, tx = b["currency"], [t for t in data["transactions"] if t["batch_id"] == b["id"]]
        signed = [D(t["amount"]) if t["direction"] == "credit" else -D(t["amount"]) for t in tx]
        opening = D(b["opening"])
        add(f"{b['id']}: opening + sum(txns) = closing", amt(D(b["closing"]), cur), amt(opening + sum(signed), cur),
            not b["opening_derived"])
        if b.get("no_movement"):
            before = {t["id"]: D(t["balance_after"]) for t in tx if "balance_after" in t} | {"opening": opening}
            ok = sum(1 for n in b["no_movement"] if before.get(n["after"]) == D(n["balance"]))
            add(f"{b['id']}: no-movement rows leave the balance unchanged", f"{len(b['no_movement'])} rows", f"{ok} rows", True)
        if "stated_closing" in b:
            add(f"{b['id']}: document-stated closing = last running balance", amt(D(b["stated_closing"]), cur),
                amt(D(b["closing"]), cur), True)
        if tx and all("balance_after" in t for t in tx):
            run, ok = opening, 0
            for t, s in zip(tx, signed):
                run += s
                ok += run == D(t["balance_after"])
            checked = len(tx) - (1 if b["opening_derived"] else 0)
            if b["opening_derived"]:
                ok -= 1
            add(f"{b['id']}: running balance ties on every row", f"{checked} rows", f"{ok} rows", checked > 0)
    by_acct: dict[str, list[dict]] = {}
    for b in statements:
        by_acct.setdefault(b["account_id"], []).append(b)
    for accts in by_acct.values():
        for a, b in zip(accts, accts[1:]):
            add(f"{a['id']} closing = {b['id']} opening", amt(D(a["closing"]), a["currency"]),
                amt(D(b["opening"]), b["currency"]), True)
    for b in (x for x in data["batches"] if x["kind"] == "settlement"):
        cur, tx = b["currency"], [t for t in data["transactions"] if t["batch_id"] == b["id"]]
        bad = [t["id"] for t in tx if D(t["gross"]) - D(t["fee"]) - (D(t["tax"]) if "tax" in t else 0) != D(t["net"])]
        add(f"{b['id']}: gross - fees - tax = net on every row", f"{len(tx)} rows", f"{len(tx) - len(bad)} rows", len(tx) > 0)
        g, f, n = (sum(D(t[k]) for t in tx) for k in ("gross", "fee", "net"))
        t_tax = sum(D(t["tax"]) for t in tx if "tax" in t)
        add(f"{b['id']}: sum(gross) - sum(fees) - sum(tax) = sum(net)", amt(n, cur), amt(g - f - t_tax, cur), False)
        if b["payout"] is not None:
            add(f"{b['id']}: sum(net) = payout", amt(D(b["payout"]), cur), amt(n, cur), True)
    from .parsers_extra import extra_gate

    for rule, expected, computed, independent in extra_gate(data):
        add(rule, expected, computed, independent)
    return out


_MONEY = {"type": "object", "required": ["amount", "currency"], "additionalProperties": False,
          "properties": {"amount": {"type": "string", "pattern": r"^-?\d+(\.\d+)?$"},
                         "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}}}
# Evidence: where a value came from. Located methods (anything but "parser") must carry page + bbox.
_EVIDENCE = {
    "type": "object", "required": ["page", "bbox", "row", "raw_text", "method"],
    "properties": {
        "page": {"type": ["integer", "null"], "minimum": 1},
        "bbox": {"type": ["array", "null"], "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
        "row": {"type": ["integer", "null"]},
        "raw_text": {"type": "string"},
        "method": {"type": "string", "pattern": r"^(parser|pdf_text|ocr)(\+model)?$"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "if": {"properties": {"method": {"not": {"const": "parser"}}}},
    "then": {"properties": {"page": {"type": "integer"}, "bbox": {"type": "array"}}},
}
_ASSERTION = {
    "type": "object", "required": ["id", "rule", "expected", "computed", "passed", "independent"],
    "properties": {"id": {"type": "string"}, "rule": {"type": "string"}, "expected": {"type": "string"},
                   "computed": {"type": "string"}, "passed": {"type": "boolean"}, "independent": {"type": "boolean"}},
}
SCHEMA = {
    "type": "object", "required": ["schema_version", "status", "file", "data", "evidence", "assertions"],
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION}, "status": {"const": "ok"},
        "file": {"type": "object", "required": ["sha256", "name", "detected_format", "layout_version", "method"],
                 "properties": {"sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                                "model": {"type": "object", "required": ["weights_sha256", "calibration_sha256"],
                                          "additionalProperties": False,
                                          "properties": {"weights_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                                                         "calibration_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}}}},
        "data": {"type": "object", "required": ["accounts", "parties", "batches", "transactions", "claims"],
                 "properties": {"transactions": {"type": "array", "minItems": 1}}},
        "evidence": {"type": "object", "additionalProperties": _EVIDENCE},
        "assertions": {"type": "array", "minItems": 1, "items": _ASSERTION},
    },
}


def _needs_evidence(rec: dict):
    for k, v in rec.items():
        if isinstance(v, dict) and set(v) == {"amount", "currency"}:
            jsonschema.validate(v, _MONEY)
            yield k
        elif isinstance(v, str) and (k == "date" or k.startswith("period_")):
            yield k


def validate_output(doc: dict) -> None:
    try:
        jsonschema.validate(doc, SCHEMA)
        data = doc["data"]
        for key in ("accounts", "batches", "transactions"):
            for rec in data[key]:
                for f in _needs_evidence(rec):
                    if f"{rec['id']}.{f}" not in doc["evidence"]:
                        raise Refusal("OUTPUT_INVALID", f"missing evidence for {rec['id']}.{f}")
    except jsonschema.ValidationError as e:
        raise Refusal("OUTPUT_INVALID", f"schema: {e.message[:200]}") from None
    accounts, batches = {a["id"] for a in data["accounts"]}, {b["id"] for b in data["batches"]}
    for t in data["transactions"]:
        if t["batch_id"] not in batches or ("account_id" in t and t["account_id"] not in accounts):
            raise Refusal("OUTPUT_INVALID", f"{t['id']} points to a missing account or batch")
    ass = doc["assertions"]
    if not all(a["passed"] for a in ass) or not any(a["independent"] for a in ass):
        raise Refusal("OUTPUT_INVALID", "assertions incomplete")


def run_layout(layout: str, args, p: Params):
    from . import parsers_extra as x

    table = {"bank_csv.v1": parse_bank_csv, "stripe_balance.v1": parse_stripe, "razorpay_settlement.v1": parse_razorpay,
             "tds_26as.v1": x.parse_tds, "ais.v1": x.parse_ais, "fira.v1": x.parse_fira,
             "trial_balance.v1": x.parse_trial_balance}
    return table[layout](args, p)


def refusal_doc(code: str, message: str, sha: str) -> dict:
    return {"schema_version": SCHEMA_VERSION, "status": "refused", "data": None,
            "error": {"code": code, "message": message, "file_sha256": sha}}


def process(path: str | Path, params: Params | None = None) -> dict:
    path, p = Path(path), params or Params()
    sha = sha256_file(path)
    try:
        raw = guard(path)
        ext = path.suffix.lower()
        method = "parser"
        if ext in DOC_EXT:
            from .pdf_front import extract_document

            data, ev, fmt_name, layout, method = extract_document(path, p)
        elif ext == ".xlsx":
            from .parsers_extra import parse_xlsx

            data, ev, fmt_name, layout = parse_xlsx(path, p)
        else:
            text = decode(raw)
            fmt_name, layout, args = detect(text)
            if fmt_name == "ofx":
                data, ev = parse_ofx(text, p)
            elif fmt_name == "mt940":
                data, ev = parse_mt940(text, p)
            else:
                data, ev = run_layout(layout, args, p)
        assertions = run_gate(data)
        failed = [a for a in assertions if not a["passed"]]
        if failed:
            raise Refusal("BALANCE_MISMATCH", "; ".join(
                f"{a['rule']} (expected {a['expected']}, got {a['computed']})" for a in failed))
        if not any(a["independent"] for a in assertions):
            raise Refusal("BALANCE_MISMATCH", "no independent balance evidence in this file")
        model_id = None
        if p.model and ext in DOC_EXT:  # a --model release names the exact weights and calibration that cross-checked it
            from .roles import RoleModel

            model_id = getattr(RoleModel.load(), "identity", None)
        doc = {"schema_version": SCHEMA_VERSION, "status": "ok",
               "file": {"sha256": sha, "name": path.name, "detected_format": fmt_name,
                        "layout_version": layout, "method": method, **({"model": model_id} if model_id else {})},
               "data": data, "evidence": ev, "assertions": assertions}
        validate_output(doc)
        return doc
    except Refusal as r:
        return refusal_doc(r.code, r.message, sha)
    except Exception as e:
        return refusal_doc("PARSE_ERROR", f"unexpected {type(e).__name__}: {e}", sha)


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def run_eval(root: Path) -> int:
    bad = false_accepts = 0
    cases = sorted(d for d in root.iterdir() if d.is_dir())
    for d in cases:
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        src = next(f for f in d.iterdir() if f.name != "expected.json")
        pr = exp.get("params", {})
        doc = process(src, Params(pr.get("currency"), Decimal(pr["opening"]) if "opening" in pr else None,
                                  pr.get("account"), pr.get("allow_derived_opening", False)))
        got = (doc["status"], doc.get("error", {}).get("code"))
        want = (exp["status"], exp.get("code"))
        codes = exp.get("code") if isinstance(exp.get("code"), list) else None
        if (got[0] != want[0] or got[1] not in codes) if codes else got != want:
            bad += 1
            false_accepts += exp["status"] == "refused" and doc["status"] == "ok"
            print(f"MISMATCH {d.name}: want {want} got {got}")
    print(f"cases={len(cases)} mismatches={bad} false_accepts={false_accepts}")
    return 1 if bad else 0


def run_report(folder: Path, out: Path, p: Params) -> int:
    """End to end: every supported file -> openbooks.v1 JSON (or typed refusal) -> cross-file links -> report.json."""
    from collections import Counter

    from .link import link

    out.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in ALLOWED_EXT)
    per_file = json.loads((folder / "params.json").read_text(encoding="utf-8")) if (folder / "params.json").exists() else {}
    docs, rows, seen = [], [], set()
    for f in files:
        sha = sha256_file(f)
        if sha in seen:
            rows.append({"file": f.name, "status": "duplicate", "code": None, "format": None, "method": None, "message": "same bytes as an earlier file"})
            continue
        seen.add(sha)
        q = per_file.get(f.name, {})
        doc = process(f, Params(q.get("currency", p.currency), Decimal(q["opening"]) if "opening" in q else p.opening,
                                q.get("account", p.account), q.get("allow_derived_opening", p.allow_derived_opening), p.ocr, p.model))
        (out / f"{doc['file']['sha256'] if doc['status'] == 'ok' else sha256_file(f)}.json").write_text(dumps(doc), encoding="utf-8")
        docs.append(doc)
        rows.append({"file": f.name, "status": doc["status"], "code": doc.get("error", {}).get("code"),
                     "format": doc.get("file", {}).get("detected_format"), "method": doc.get("file", {}).get("method"),
                     "message": doc.get("error", {}).get("message")})
    links = link(docs)
    report = {"files": rows, "released": sum(r["status"] == "ok" for r in rows),
              "refused": dict(Counter(r["code"] for r in rows if r["status"] == "refused")),
              "links": links["links"], "ambiguous": links["ambiguous"],
              "unlinked_sources": links["unlinked_sources"], "unlinked_credits": links["unlinked_credits"]}
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    for r in rows:
        sys.stdout.write(f"{r['file']}: {r['status']} {r['code'] or r['format'] or ''}\n")
    sys.stdout.write(f"released={report['released']}/{len(rows)} refused={report['refused']} links={len(links['links'])} "
                     f"ambiguous={len(links['ambiguous'])} -> {out / 'report.json'}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="openbooks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="write one openbooks.v1 JSON per input file")
    r.add_argument("files", nargs="+")
    r.add_argument("--out", default="out")
    r.add_argument("--currency")
    r.add_argument("--opening", help="opening balance, if the file does not state one")
    r.add_argument("--account")
    r.add_argument("--allow-derived-opening", action="store_true")
    r.add_argument("--no-ocr", action="store_true", help="refuse scans instead of running OCR")
    r.add_argument("--model", action="store_true", help="typed-head cross-check on PDFs/scans (needs models/roles_head.pt)")
    e = sub.add_parser("eval", help="run the golden set")
    e.add_argument("root")
    lk = sub.add_parser("link", help="link settlement payouts and FIRA credits to bank credits")
    lk.add_argument("files", nargs="+")
    lk.add_argument("--out", default="links.json")
    rp = sub.add_parser("report", help="run every file in a folder, link the released ones, write report.json")
    rp.add_argument("folder", help="a params.json in the folder gives per-file currency/opening/account")
    rp.add_argument("--out", default="out")
    rp.add_argument("--currency")
    rp.add_argument("--opening", help="opening balance, if the files do not state one")
    rp.add_argument("--account")
    rp.add_argument("--allow-derived-opening", action="store_true")
    rp.add_argument("--no-ocr", action="store_true")
    rp.add_argument("--model", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "eval":
        return run_eval(Path(a.root))
    if a.cmd == "report":
        return run_report(Path(a.folder), Path(a.out),
                          Params(a.currency, Decimal(a.opening) if a.opening else None, a.account,
                                 a.allow_derived_opening, not a.no_ocr, a.model))
    if a.cmd == "link":
        from .link import run_link

        return run_link(a.files, a.out)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    p = Params(a.currency, Decimal(a.opening) if a.opening else None, a.account, a.allow_derived_opening,
               not a.no_ocr, a.model)
    rc = 0
    for f in a.files:
        sha = sha256_file(Path(f))
        target = out / f"{sha}.json"
        # No reuse of an earlier <sha>.json: the same bytes give a different result under another --currency,
        # --opening or --model, and a stale refusal or release must never be returned silently.
        doc = process(f, p)
        target.write_text(dumps(doc), encoding="utf-8")
        err = doc.get("error", {})
        sys.stdout.write(f"{Path(f).name}: {doc['status']} {err.get('code', '')} -> {target.name}\n")
        rc |= doc["status"] != "ok"
    return rc


if __name__ == "__main__":
    sys.exit(main())
