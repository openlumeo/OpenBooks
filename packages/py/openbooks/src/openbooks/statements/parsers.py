"""Bank statement parsers: bank CSV, MT940 and OFX. Moved verbatim from pipeline.py into openbooks.statements."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from xml.etree import ElementTree

from openbooks.core.registry import bank_cols, signed_bank_cols
from openbooks.core.builders import (
    body_rows as _body,
    currency_of as _currency,
    empty_data as _empty_data,
    statement_doc,
)
from openbooks.core.errors import Refusal
from openbooks.core.gates import OPENING_NOT_EVIDENCE
from openbooks.core.evidence import evidence
from openbooks.core.normalise import date_order, money, to_date, to_dec
from openbooks.core.params import Params
from openbooks.core.provenance import Provenance


def _with_date_order(doc_and_ev: tuple, order: str, p: Params) -> tuple:
    data, ev = doc_and_ev
    evidence(ev, "batch-1", "date_order", None, order, provenance="CALLER_SUPPLIED" if p.date_order else "FILE_EVIDENCE")
    return data, ev


_OPENING_ROW = re.compile(r"opening balance|balance brought forward|balance b/?f|opening bal", re.IGNORECASE)


def _printed_opening(n: int, row: list[str], idx: dict[str, int]) -> Decimal | None:
    """The balance of a printed opening row: described as an opening balance, with no amount, and with a balance."""
    if "balance" not in idx or "desc" not in idx or not _OPENING_ROW.search(row[idx["desc"]]):
        return None
    if any(row[idx[role]].strip() for role in ("debit", "credit", "amount") if role in idx):
        return None
    raw = row[idx["balance"]].strip()
    return to_dec(raw, f"row {n} balance", dr_cr=True) if raw else None


def _opening_for(body: list, idx: dict[str, int], p: Params) -> tuple[list, Decimal | None, tuple | None]:
    """The opening balance. A printed opening row (the first body row) is source evidence and is not a transaction. A
    caller --opening is checked against it, and is never evidence by itself."""
    first_n, first = body[0]
    printed = _printed_opening(first_n, first, idx)
    if printed is None:
        if p.opening is None and not p.allow_derived_opening:
            raise Refusal("PARSE_ERROR", f"statement has no stated opening balance; supply --opening to check the arithmetic ({OPENING_NOT_EVIDENCE})")
        return body, p.opening, None
    if p.opening is not None and p.opening != printed:
        raise Refusal("PARSE_ERROR", f"supplied opening balance differs from the one printed on row {first_n}")
    rest = body[1:]
    if not rest:
        raise Refusal("PARSE_ERROR", "no transactions after the opening balance")
    return rest, printed, (None, f"printed opening balance on row {first_n}")


def parse_bank_csv(args, p: Params):
    rows, hi, hs = args
    idx = bank_cols(hs)
    body, opening, opening_loc = _opening_for(_body(rows, hi, hs), idx, p)
    cur = _currency(hs, [r for _, r in body], p)
    order = date_order([r[idx["date"]] for _, r in body], p.date_order, where="date column")
    recs = []
    for n, row in body:

        def g(role: str) -> str:
            return row[idx[role]].strip() if role in idx else ""

        deb = to_dec(g("debit"), f"row {n} debit", blank_zero=True)
        cre = to_dec(g("credit"), f"row {n} credit", blank_zero=True)
        if (deb and cre) or not (deb or cre) or deb < 0 or cre < 0:
            raise Refusal("PARSE_ERROR", f"row {n}: need exactly one positive debit or credit")
        recs.append(
            {
                "row": n,
                "date": to_date(g("date"), f"row {n}", order),
                "dir": "credit" if cre else "debit",
                "amt": cre or deb,
                "amt_raw": g("credit") if cre else g("debit"),
                "date_raw": g("date"),
                "bal": to_dec(g("balance"), f"row {n} balance", dr_cr=True),
                "bal_raw": g("balance"),
                "desc": g("desc"),
                "ref": g("ref") or None,
            }
        )
    return _with_date_order(statement_doc(recs, cur, p.account, opening, opening_loc=opening_loc), order, p)


def parse_bank_csv_signed(args, p: Params):
    rows, hi, hs = args
    idx = signed_bank_cols(hs)
    if idx is None:
        raise Refusal("UNKNOWN_LAYOUT", "ambiguous amount columns: need exactly one signed amount column")
    body, opening, opening_loc = _opening_for(_body(rows, hi, hs), idx, p)
    cur = _currency(hs, [r for _, r in body], p)
    order = date_order([r[idx["date"]] for _, r in body], p.date_order, where="date column")
    recs = []
    for n, row in body:

        def g(role: str) -> str:
            return row[idx[role]].strip()

        amount = to_dec(g("amount"), f"row {n} amount")
        if amount == 0:
            raise Refusal("PARSE_ERROR", f"row {n}: zero amount")
        recs.append(
            {
                "row": n,
                "date": to_date(g("date"), f"row {n}", order),
                "dir": "credit" if amount > 0 else "debit",
                "amt": abs(amount),
                "amt_raw": g("amount"),
                "date_raw": g("date"),
                "bal": to_dec(g("balance"), f"row {n} balance", dr_cr=True),
                "bal_raw": g("balance"),
                "desc": g("desc"),
                "ref": None,
            }
        )
    return _with_date_order(statement_doc(recs, cur, p.account, opening, opening_loc=opening_loc), order, p)


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


def _mt_statements(text: str) -> list[dict]:
    """Group the tagged fields into statements (:20: starts one), each with its account, balances and :61:/:86: pairs."""
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
    return stmts


def _mt_add_statement(data: dict, ev: dict, accts: dict, si: int, s: dict) -> None:
    """Append statement si's account, batch, transactions and their evidence to data and ev (accts maps account numbers to ids)."""
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
    data["batches"].append(
        {
            "id": bid,
            "kind": "statement",
            "account_id": aid,
            "currency": ocur,
            "period_start": od,
            "period_end": cd,
            "opening": money(ob, ocur),
            "closing": money(cb, ocur),
            "opening_derived": False,
            "opening_provenance": Provenance.SOURCE_OBSERVED.value,
        }
    )
    for f, raw in (("opening", oraw), ("closing", craw), ("period_start", oraw), ("period_end", craw)):
        evidence(ev, bid, f, None, raw)
    for k, t in enumerate(s["txns"], 1):
        m = t["m"]
        tid = f"txn-{si}-{k:05d}"
        credit = m.group(3) in ("C", "RD")
        ref = m.group(7).split("//")[0].strip()
        data["transactions"].append(
            {
                "id": tid,
                "batch_id": bid,
                "account_id": aid,
                "date": _mt_date(m.group(1), tid),
                "direction": "credit" if credit else "debit",
                "amount": money(Decimal(m.group(5).replace(",", ".")), ocur),
                "description": t["info"],
                "reference": None if ref in ("", "NONREF") else ref,
            }
        )
        evidence(ev, tid, "date", None, t["raw"])
        evidence(ev, tid, "amount", None, t["raw"])


def parse_mt940(text: str, p: Params):
    data, ev, accts = _empty_data(), {}, {}
    for si, s in enumerate(_mt_statements(text), 1):
        _mt_add_statement(data, ev, accts, si, s)
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
        raise Refusal("PARSE_ERROR", f"OFX carries no opening balance; supply --opening to check the arithmetic ({OPENING_NOT_EVIDENCE})")
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
        data["transactions"].append(
            {
                "id": tid,
                "batch_id": "batch-1",
                "account_id": "acct-1",
                "date": d,
                "direction": "credit" if amt > 0 else "debit",
                "amount": money(abs(amt), cur),
                "description": _ofx_tag(b, "NAME") or _ofx_tag(b, "MEMO") or "",
                "reference": fit,
            }
        )
        evidence(ev, tid, "date", None, dt)
        evidence(ev, tid, "amount", None, amt_raw)
    if not dates:
        raise Refusal("PARSE_ERROR", "no transactions")
    data["batches"].append(
        {
            "id": "batch-1",
            "kind": "statement",
            "account_id": "acct-1",
            "currency": cur,
            "period_start": min(dates),
            "period_end": max(dates),
            "opening": money(p.opening, cur),
            "closing": money(to_dec(bal, "LEDGERBAL"), cur),
            "opening_derived": False,
            "opening_provenance": Provenance.CALLER_SUPPLIED.value,
        }
    )
    evidence(ev, "batch-1", "opening", None, "supplied by caller", provenance=Provenance.CALLER_SUPPLIED.value)
    evidence(ev, "batch-1", "closing", None, bal)
    evidence(ev, "batch-1", "period_start", None, min(dates))
    evidence(ev, "batch-1", "period_end", None, max(dates))
    return data, ev


_CAMT_OPENING_CODES = ("OPBD", "PRCD")
_CAMT_DECLARATIONS = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.I)


def _local(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _camt_path(element, *names: str) -> list:
    found = [element]
    for name in names:
        found = [child for node in found for child in node if _local(child) == name]
    return found


def _camt_text(element, *names: str) -> str | None:
    found = _camt_path(element, *names)
    return (found[0].text or "").strip() if found else None


def _camt_date(element, container: str, where: str) -> tuple[str, str]:
    raw = _camt_text(element, container, "Dt") or _camt_text(element, container, "DtTm")
    if not raw:
        raise Refusal("PARSE_ERROR", f"{where}: missing date")
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date().isoformat(), raw
    except ValueError:
        raise Refusal("PARSE_ERROR", f"{where}: unreadable date {raw!r}") from None


def _camt_amount(element, where: str) -> tuple[Decimal, str, str]:
    nodes = _camt_path(element, "Amt")
    if not nodes or not (nodes[0].text or "").strip():
        raise Refusal("PARSE_ERROR", f"{where}: missing amount")
    raw = nodes[0].text.strip()
    currency = (nodes[0].get("Ccy") or "").upper()
    if not currency:
        raise Refusal("PARSE_ERROR", f"{where}: amount has no currency")
    return to_dec(raw, where), currency, raw


def _camt_balances(statement, where: str) -> tuple[tuple, tuple]:
    opening = closing = None
    for balance in _camt_path(statement, "Bal"):
        code = _camt_text(balance, "Tp", "CdOrPrtry", "Cd")
        if code not in (*_CAMT_OPENING_CODES, "CLBD"):
            continue
        amount, currency, raw = _camt_amount(balance, f"{where} {code}")
        sign = -1 if _camt_text(balance, "CdtDbtInd") == "DBIT" else 1
        day, _ = _camt_date(balance, "Dt", f"{where} {code}")
        found = (sign * amount, day, currency, raw)
        if code == "CLBD":
            closing = found
        elif opening is None:
            opening = found
    if not (opening and closing):
        raise Refusal("PARSE_ERROR", f"{where}: missing opening (OPBD) or closing (CLBD) balance")
    return opening, closing


def _camt_entry(entry, tid: str, bid: str, aid: str, currency: str, data: dict, ev: dict) -> None:
    amount, entry_currency, raw_amount = _camt_amount(entry, tid)
    if entry_currency != currency:
        raise Refusal("PARSE_ERROR", f"{tid}: currency {entry_currency} differs from account currency {currency}")
    if amount <= 0:
        raise Refusal("PARSE_ERROR", f"{tid}: amount must be positive")
    credit = _camt_text(entry, "CdtDbtInd") == "CRDT"
    if (_camt_text(entry, "RvslInd") or "").lower() == "true":
        credit = not credit
    day, raw_date = _camt_date(entry, "BookgDt", tid)
    detail = _camt_path(entry, "NtryDtls", "TxDtls")
    lines = [(node.text or "").strip() for node in _camt_path(detail[0], "RmtInf", "Ustrd")] if detail else []
    description = " ".join(part for part in lines if part) or _camt_text(entry, "AddtlNtryInf") or ""
    ref = _camt_text(entry, "AcctSvcrRef") or (_camt_text(detail[0], "Refs", "EndToEndId") if detail else None)
    data["transactions"].append(
        {
            "id": tid,
            "batch_id": bid,
            "account_id": aid,
            "date": day,
            "direction": "credit" if credit else "debit",
            "amount": money(amount, currency),
            "description": description,
            "reference": None if ref in (None, "", "NOTPROVIDED") else ref,
        }
    )
    evidence(ev, tid, "date", None, raw_date)
    evidence(ev, tid, "amount", None, raw_amount)


def _camt_statement(statement, si: int, data: dict, ev: dict, accts: dict) -> None:
    where = f"statement {si}"
    account = _camt_text(statement, "Acct", "Id", "IBAN") or _camt_text(statement, "Acct", "Id", "Othr", "Id")
    if not account:
        raise Refusal("PARSE_ERROR", f"{where}: missing account identifier")
    (opening, open_day, open_cur, open_raw), (closing, close_day, close_cur, close_raw) = _camt_balances(
        statement, where
    )
    if open_cur != close_cur:
        raise Refusal("PARSE_ERROR", f"{where}: currency changes inside statement")
    aid = accts.setdefault(account, f"acct-{len(accts) + 1}")
    if not any(a["id"] == aid for a in data["accounts"]):
        data["accounts"].append({"id": aid, "number": account, "currency": open_cur})
    bid = f"batch-{si}"
    data["batches"].append(
        {
            "id": bid,
            "kind": "statement",
            "account_id": aid,
            "currency": open_cur,
            "period_start": open_day,
            "period_end": close_day,
            "opening": money(opening, open_cur),
            "closing": money(closing, close_cur),
            "opening_derived": False,
            "opening_provenance": Provenance.SOURCE_OBSERVED.value,
        }
    )
    for field, raw in (
        ("opening", open_raw),
        ("closing", close_raw),
        ("period_start", open_day),
        ("period_end", close_day),
    ):
        evidence(ev, bid, field, None, raw)
    booked = [
        e
        for e in _camt_path(statement, "Ntry")
        if (_camt_text(e, "Sts") or _camt_text(e, "Sts", "Cd") or "BOOK") == "BOOK"
    ]
    for k, entry in enumerate(booked, 1):
        _camt_entry(entry, f"txn-{si}-{k:05d}", bid, aid, open_cur, data, ev)


def parse_camt053(text: str, p: Params):
    if _CAMT_DECLARATIONS.search(text):
        raise Refusal("PARSE_ERROR", "DTD and entity declarations are not accepted in camt.053")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as e:
        raise Refusal("PARSE_ERROR", f"camt.053 is not well-formed XML ({e})") from None
    statements = [s for group in root.iter() if _local(group) == "BkToCstmrStmt" for s in _camt_path(group, "Stmt")]
    if not statements:
        raise Refusal("PARSE_ERROR", "no statements in camt.053")
    data, ev, accts = _empty_data(), {}, {}
    for si, statement in enumerate(statements, 1):
        _camt_statement(statement, si, data, ev, accts)
    if not data["transactions"]:
        raise Refusal("PARSE_ERROR", "no booked entries in camt.053")
    return data, ev
