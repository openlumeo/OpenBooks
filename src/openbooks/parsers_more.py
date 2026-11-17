"""PayPal activity, Wise statement and Form 1099-B detail parsers (CSV or XLSX rows).

Layouts follow public descriptions of those exports, not real files (see docs/HANDOFF.md): treat them as unverified
until real redacted samples exist. Each can only be released when the document supplies a figure of its own to check:
  PayPal  gross + fee = net on every row (PayPal's own three columns; Fee is signed as its impact on the balance).
  Wise    the running balance ties on every row (opening supplied or derived, as for bank CSV). Amount is read as printed;
          if the running balance does not tie under that reading the file refuses rather than guessing about fees.
  1099-B  proceeds - cost basis + adjustment = gain or loss on every row, and printed totals tie.
Numeric dates: Wise defaults to day-first; PayPal and 1099-B (US exports) have no safe default, so the order is proven
from the file (a day or month above 12) or supplied with --date-order. Other 1099 forms have no arithmetic to prove and
are not parsed.
"""
from __future__ import annotations

from .parsers_extra import _cell, _finish, _money_fields, _split_total, _stated_totals
from .pipeline import (Params, Refusal, _body, _currency, _empty_data, _settlement, date_order, evidence, money, statement_doc,
                       to_date, to_dec)

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


def parse_1099b(args, p: Params):
    rows, hi, hs = args
    items, total = _split_total(_body(rows, hi, hs))
    get, data, ev, txns = _cell(hs), _empty_data(), {}, []
    cur = (p.currency or "USD").upper()
    adj_col = next((c for c in ("wash_sale_loss_disallowed", "adjustment", "adjustments") if c in hs), None)
    various = lambda s: s.strip().upper() in {"VARIOUS", ""}  # noqa: E731
    dates = [get(r, "date_sold") for _, r in items] + [get(r, "date_acquired") for _, r in items if not various(get(r, "date_acquired"))]
    order = date_order(dates, p.date_order, where="1099-B date columns")
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        t = {"id": tid, "batch_id": "batch-1", "kind": "1099b", "description": get(row, "description"),
             "date": to_date(get(row, "date_sold"), f"row {n}", order)}
        evidence(ev, tid, "date", n, get(row, "date_sold"))
        if not various(get(row, "date_acquired")):
            t["date_acquired"] = to_date(get(row, "date_acquired"), f"row {n}", order)
            evidence(ev, tid, "date_acquired", n, get(row, "date_acquired"))
        _money_fields(t, ev, tid, row, n, cur, get, (("proceeds", "proceeds"), ("cost_basis", "cost_basis"), ("gain_loss", "gain_loss")))
        if adj_col:
            _money_fields(t, ev, tid, row, n, cur, get, (("adjustment", adj_col),), blank_zero=("adjustment",))
        txns.append(t)
    totals = _stated_totals(total, hs, cur, (("total_proceeds", "proceeds"), ("total_cost_basis", "cost_basis"),
                                             ("total_gain_loss", "gain_loss")), ev)
    return _finish(data, ev, "form_1099b", cur, txns, totals)
