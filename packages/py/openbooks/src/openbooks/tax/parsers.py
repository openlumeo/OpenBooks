"""Tax and ledger parsers: Form 26AS, AIS, FIRA, Form 1099-B and trial balance. Each is released only when the document
supplies a figure of its own to check against (a printed total, or a relation between numbers it states). The layouts
come from public descriptions, not real exports, so all of them are experimental until redacted samples exist."""
from __future__ import annotations

import re
from decimal import Decimal

from openbooks.core.builders import body_rows as _body
from openbooks.core.builders import cell_getter as _cell
from openbooks.core.builders import currency_of as _core_currency
from openbooks.core.builders import empty_data as _empty_data
from openbooks.core.builders import finish_batch as _finish
from openbooks.core.builders import money_fields as _money_fields
from openbooks.core.builders import split_total as _split_total
from openbooks.core.builders import stated_totals as _stated_totals
from openbooks.core.errors import Refusal
from openbooks.core.evidence import evidence
from openbooks.core.normalise import date_order, money, to_date, to_dec
from openbooks.core.params import Params

_CCY = re.compile(r"[A-Z]{3}")
FX_TOLERANCE = Decimal("0.01")


def _currency(hs: list[str], rows: list[list[str]], p: Params) -> str:
    cur = _core_currency(hs, rows, p)
    if p.currency and "currency" in hs and p.currency.upper() != cur:
        raise Refusal("PARSE_ERROR", f"file currency {cur} contradicts --currency {p.currency.upper()}")
    return cur


def _date_order(ev: dict, dates: list[str], p: Params, where: str) -> str:
    order = date_order(dates, p.date_order, where=where)
    evidence(ev, "batch-1", "date_order", None, order, provenance="CALLER_SUPPLIED" if p.date_order else "FILE_EVIDENCE")
    return order


def parse_tds(args, p: Params):
    rows, hi, hs = args
    items, total = _split_total(_body(rows, hi, hs))
    cur, get, data, ev, txns = _currency(hs, [r for _, r in items], p), _cell(hs), _empty_data(), {}, []
    order = _date_order(ev, [get(r, "transaction_date") for _, r in items], p, "transaction date column")
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        t = {"id": tid, "batch_id": "batch-1", "date": to_date(get(row, "transaction_date"), f"row {n}", order),
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
    cur, get, data, ev, txns = _currency(hs, [r for _, r in items], p), _cell(hs), _empty_data(), {}, []
    order = _date_order(ev, [get(r, "date") for _, r in items] if "date" in hs else [], p, "AIS date column")
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        t = {"id": tid, "batch_id": "batch-1", "kind": "ais", "category": get(row, "information_category"),
             "description": get(row, "information_description"), "source": get(row, "source")}
        if "date" in hs and get(row, "date"):
            t["date"] = to_date(get(row, "date"), f"row {n}", order)
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
    order = _date_order(ev, [get(r, "date") for _, r in items], p, "FIRA date column")
    evidence(ev, "batch-1", "currency", None, "INR", provenance="FILE_HEADER")
    for n, row in items:
        tid = f"txn-{len(txns) + 1:05d}"
        fcy = get(row, "currency").upper()
        if not _CCY.fullmatch(fcy):
            raise Refusal("PARSE_ERROR", f"row {n}: bad currency {fcy!r}")
        if fcy == "INR":
            raise Refusal("PARSE_ERROR", f"row {n}: foreign currency is INR; a FIRA remittance must name a foreign currency")
        rate_raw = get(row, "exchange_rate")
        rate = to_dec(rate_raw, f"row {n} exchange_rate")
        if rate <= 0:
            raise Refusal("PARSE_ERROR", f"row {n}: exchange rate must be positive")
        t = {"id": tid, "batch_id": "batch-1", "date": to_date(get(row, "date"), f"row {n}", order), "kind": "fira",
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
    cur = _currency(hs, [r for _, r in items], p)
    adj_col = next((c for c in ("wash_sale_loss_disallowed", "adjustment", "adjustments") if c in hs), None)
    various = lambda s: s.strip().upper() in {"VARIOUS", ""}  # noqa: E731
    dates = [get(r, "date_sold") for _, r in items] + [get(r, "date_acquired") for _, r in items if not various(get(r, "date_acquired"))]
    order = _date_order(ev, dates, p, "1099-B date columns")
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
