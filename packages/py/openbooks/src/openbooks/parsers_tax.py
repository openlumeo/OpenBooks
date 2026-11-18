"""Tax document parsers: 26AS, AIS, FIRA, trial balance, 1099-B. Moved verbatim; become openbooks-tax.
"""
from __future__ import annotations

import re
from decimal import Decimal

from openbooks_core.builders import (D, body_rows as _body, cell_getter as _cell, currency_of as _currency, empty_data as _empty_data,
                                     finish_batch as _finish, money_fields as _money_fields, settlement_batch as _settlement,
                                     split_total as _split_total, stated_totals as _stated_totals, statement_doc)
from openbooks_core.errors import Refusal
from openbooks_core.evidence import evidence
from openbooks_core.normalise import date_order, fmt, money, to_date, to_dec
from openbooks_core.params import Params


_CCY = re.compile(r"[A-Z]{3}")
FX_TOLERANCE = Decimal("0.01")


def parse_tds(args, p: Params):
    rows, hi, hs = args
    items, total = _split_total(_body(rows, hi, hs))
    cur, get, data, ev, txns = (p.currency or "INR").upper(), _cell(hs), _empty_data(), {}, []
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        t = {"id": tid, "batch_id": "batch-1", "date": to_date(get(row, "transaction_date"), f"row {n}"),
             "kind": "tds", "deductor": get(row, "deductor_name"), "tan": get(row, "tan"), "section": get(row, "section")}
        evidence(ev, tid, "date", n, get(row, "transaction_date"))
        _money_fields(t, ev, tid, row, n, cur, get, (("amount", "amount_paid_credited"), ("tax_deducted", "tax_deducted"),
                                                      ("tax_deposited", "tds_deposited")))
        txns.append(t)
    totals = _stated_totals(total, hs, cur, (("total_amount", "amount_paid_credited"), ("total_tax_deducted", "tax_deducted"),
                                             ("total_tax_deposited", "tds_deposited")), ev)
    return _finish(data, ev, "tax_statement", cur, txns, totals)


def parse_ais(args, p: Params):
    rows, hi, hs = args
    items, total = _split_total(_body(rows, hi, hs))
    cur, get, data, ev, txns = (p.currency or "INR").upper(), _cell(hs), _empty_data(), {}, []
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        t = {"id": tid, "batch_id": "batch-1", "kind": "ais", "category": get(row, "information_category"),
             "description": get(row, "information_description"), "source": get(row, "source")}
        if "date" in hs and get(row, "date"):
            t["date"] = to_date(get(row, "date"), f"row {n}")
            evidence(ev, tid, "date", n, get(row, "date"))
        _money_fields(t, ev, tid, row, n, cur, get, (("reported_value", "reported_value"),))
        if "modified_value" in hs and get(row, "modified_value"):
            _money_fields(t, ev, tid, row, n, cur, get, (("modified_value", "modified_value"),))
        txns.append(t)
    totals = _stated_totals(total, hs, cur, (("total_reported_value", "reported_value"),), ev)
    return _finish(data, ev, "ais", cur, txns, totals)


def parse_fira(args, p: Params):
    rows, hi, hs = args
    items, total = _split_total(_body(rows, hi, hs))
    get, data, ev, txns = _cell(hs), _empty_data(), {}, []
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        fcy = get(row, "currency").upper()
        if not _CCY.fullmatch(fcy):
            raise Refusal("PARSE_ERROR", f"row {n}: bad currency {fcy!r}")
        rate_raw = get(row, "exchange_rate")
        rate = to_dec(rate_raw, f"row {n} exchange_rate")
        if rate <= 0:
            raise Refusal("PARSE_ERROR", f"row {n}: exchange rate must be positive")
        t = {"id": tid, "batch_id": "batch-1", "date": to_date(get(row, "date"), f"row {n}"), "kind": "fira",
             "reference": get(row, "fira_no") or None, "remitter": get(row, "remitter") or None,
             "exchange_rate": format(rate, "f")}
        evidence(ev, tid, "date", n, get(row, "date"))
        evidence(ev, tid, "exchange_rate", n, rate_raw)
        t["foreign_amount"] = money(to_dec(get(row, "foreign_amount"), f"row {n} foreign_amount"), fcy)
        evidence(ev, tid, "foreign_amount", n, get(row, "foreign_amount"))
        _money_fields(t, ev, tid, row, n, "INR", get, (("inr_amount", "inr_amount"),))
        if "bank_charges" in hs and "net_credited" in hs:
            _money_fields(t, ev, tid, row, n, "INR", get, (("bank_charges", "bank_charges"), ("net_credited", "net_credited")),
                          blank_zero=("bank_charges",))
        txns.append(t)
    totals = _stated_totals(total, hs, "INR", (("total_inr_amount", "inr_amount"), ("total_net_credited", "net_credited")), ev)
    return _finish(data, ev, "fira", "INR", txns, totals)


def parse_trial_balance(args, p: Params):
    rows, hi, hs = args
    items, total = _split_total(_body(rows, hi, hs))
    cur = _currency(hs, [r for _, r in items], p)
    get, data, ev, txns = _cell(hs), _empty_data(), {}, []
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        t = {"id": tid, "batch_id": "batch-1", "kind": "ledger_balance", "account": get(row, "account")}
        _money_fields(t, ev, tid, row, n, cur, get, (("debit", "debit"), ("credit", "credit")), blank_zero=("debit", "credit"))
        txns.append(t)
    totals = _stated_totals(total, hs, cur, (("total_debit", "debit"), ("total_credit", "credit")), ev)
    return _finish(data, ev, "trial_balance", cur, txns, totals)


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


def fx_check(foreign: Decimal, rate: Decimal, inr: Decimal) -> bool:
    """INR amount equals foreign x rate within 0.01 INR."""
    return abs(foreign * rate - inr) <= FX_TOLERANCE
