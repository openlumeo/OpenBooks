"""Payment gateway parsers: Stripe, Razorpay, PayPal, Wise. Moved verbatim; become openbooks-gateways.
"""
from __future__ import annotations

from openbooks_core.builders import (D, body_rows as _body, cell_getter as _cell, currency_of as _currency, empty_data as _empty_data,
                                     finish_batch as _finish, money_fields as _money_fields, settlement_batch as _settlement,
                                     split_total as _split_total, stated_totals as _stated_totals, statement_doc)
from openbooks_core.errors import Refusal
from openbooks_core.evidence import evidence
from openbooks_core.normalise import date_order, fmt, money, to_date, to_dec
from openbooks_core.params import Params


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


PAYPAL_BALANCE_IMPACT = {"credit", "debit"}


def parse_paypal(args, p: Params):
    """One settlement batch. Only rows that moved the balance are read: Balance Impact Credit/Debit when that column
    exists (Memo rows are skipped), otherwise Status Completed."""
    rows, hi, hs = args
    get = _cell(hs)
    keep = []
    for n, row in _body(rows, hi, hs):
        if "balance_impact" in hs:
            impact = get(row, "balance_impact").lower()
            if impact == "memo":
                continue
            if impact not in PAYPAL_BALANCE_IMPACT:
                raise Refusal("PARSE_ERROR", f"row {n}: unknown Balance Impact {impact!r}")
        elif get(row, "status").lower() != "completed":
            continue
        keep.append((n, row))
    if not keep:
        raise Refusal("PARSE_ERROR", "no rows that moved the balance")
    cur = _currency(hs, [r for _, r in keep], p)
    order = date_order([get(r, "date") for _, r in keep], p.date_order, where="PayPal date column")
    data, ev, txns = _empty_data(), {}, []
    for n, row in keep:
        tid = f"txn-{len(txns) + 1:05d}"
        fee_raw = to_dec(get(row, "fee"), f"row {n} fee", blank_zero=True)
        t = {"id": tid, "batch_id": "batch-1", "date": to_date(get(row, "date"), f"row {n}", order),
             "kind": get(row, "type") or "other", "reference": get(row, "transaction_id") or None,
             "gross": money(to_dec(get(row, "gross"), f"row {n} gross"), cur),
             "fee": money(-fee_raw, cur),  # PayPal prints the fee as a negative balance impact; the schema holds the amount charged
             "net": money(to_dec(get(row, "net"), f"row {n} net"), cur)}
        for field in ("gross", "fee", "net", "date"):
            evidence(ev, tid, field, n, get(row, field))
        txns.append(t)
    _settlement(data, ev, cur, txns, None, None)
    return data, ev


def parse_wise(args, p: Params):
    rows, hi, hs = args
    body, get = _body(rows, hi, hs), _cell(hs)
    cur = _currency(hs, [r for _, r in body], p)
    if p.opening is None and not p.allow_derived_opening:
        raise Refusal("PARSE_ERROR", "statement has no stated opening balance; supply --opening")
    order = date_order([get(r, "date") for _, r in body], p.date_order, default="dmy", where="Wise date column")
    recs = []
    for n, row in body:
        amount = to_dec(get(row, "amount"), f"row {n} amount")
        if amount == 0:
            raise Refusal("PARSE_ERROR", f"row {n}: zero amount")
        recs.append({"row": n, "date": to_date(get(row, "date"), f"row {n}", order), "dir": "credit" if amount > 0 else "debit",
                     "amt": abs(amount), "amt_raw": get(row, "amount"), "date_raw": get(row, "date"),
                     "bal": to_dec(get(row, "running_balance"), f"row {n} running balance"), "bal_raw": get(row, "running_balance"),
                     "desc": get(row, "description"), "ref": get(row, "transferwise_id") or None})
    return statement_doc(recs, cur, p.account, p.opening)
