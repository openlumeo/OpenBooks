"""Bank statement parsers: bank CSV, MT940 and OFX. Moved verbatim from pipeline.py into openbooks.statements.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from openbooks.core.registry import bank_cols
from openbooks.core.builders import (D, body_rows as _body, cell_getter as _cell, currency_of as _currency, empty_data as _empty_data,
                                     finish_batch as _finish, money_fields as _money_fields, settlement_batch as _settlement,
                                     split_total as _split_total, stated_totals as _stated_totals, statement_doc)
from openbooks.core.errors import Refusal
from openbooks.core.evidence import evidence
from openbooks.core.normalise import date_order, fmt, money, to_date, to_dec
from openbooks.core.params import Params


def parse_bank_csv(args, p: Params):
    rows, hi, hs = args
    idx = bank_cols(hs)
    body = _body(rows, hi, hs)
    cur = _currency(hs, [r for _, r in body], p)
    if p.opening is None and not p.allow_derived_opening:
        raise Refusal("PARSE_ERROR", "statement has no stated opening balance; supply --opening")
    order = date_order([r[idx["date"]] for _, r in body], p.date_order, default="dmy", where="date column")
    recs = []
    for n, row in body:
        def g(role: str) -> str:
            return row[idx[role]].strip() if role in idx else ""

        deb = to_dec(g("debit"), f"row {n} debit", blank_zero=True)
        cre = to_dec(g("credit"), f"row {n} credit", blank_zero=True)
        if (deb and cre) or not (deb or cre) or deb < 0 or cre < 0:
            raise Refusal("PARSE_ERROR", f"row {n}: need exactly one positive debit or credit")
        recs.append({
            "row": n, "date": to_date(g("date"), f"row {n}", order), "dir": "credit" if cre else "debit",
            "amt": cre or deb, "amt_raw": g("credit") if cre else g("debit"), "date_raw": g("date"),
            "bal": to_dec(g("balance"), f"row {n} balance", dr_cr=True), "bal_raw": g("balance"),
            "desc": g("desc"), "ref": g("ref") or None,
        })
    return statement_doc(recs, cur, p.account, p.opening)


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
