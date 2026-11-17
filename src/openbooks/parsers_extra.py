"""Deterministic parsers for Form 26AS, AIS, FIRA and trial balances, plus the .xlsx front end.

The layouts come from public descriptions of those documents, not from real exports (see docs/HANDOFF.md).
Each layout can only be released when the document supplies a figure of its own to check against:
a printed total, or a relation between numbers it states (foreign x rate = INR, debits = credits).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .pipeline import (D, Params, Refusal, _body, _currency, _empty_data, evidence, find_header, fmt, fx_check,
                       money, run_layout, to_date, to_dec)

TOTAL_LABELS = {"total", "totals", "grand total"}
MAX_SHEETS, MAX_ROWS = 20, 100_000
_CCY = re.compile(r"[A-Z]{3}")


def _cell(hs: list[str]):
    def get(row: list[str], name: str) -> str:
        i = hs.index(name) if name in hs else -1
        return row[i].strip() if 0 <= i < len(row) else ""

    return get


def _is_total(row: list[str]) -> bool:
    first = next((c.strip() for c in row if c.strip()), "")
    return first.lower().rstrip(":") in TOTAL_LABELS


def _split_total(body):
    rows, total = [], None
    for n, row in body:
        if _is_total(row):
            if total is not None:
                raise Refusal("PARSE_ERROR", f"row {n}: second total row")
            total = (n, row)
        elif total is not None:
            raise Refusal("PARSE_ERROR", f"row {n}: data after the total row")
        else:
            rows.append((n, row))
    if not rows:
        raise Refusal("PARSE_ERROR", "no data rows")
    return rows, total


def _stated_totals(total, hs, cur, spec, ev) -> dict:
    """Printed totals become batch fields with evidence; blank total cells are simply not stated."""
    out: dict = {}
    if total is None:
        return out
    n, row = total
    get = _cell(hs)
    for field, col in spec:
        raw = get(row, col)
        if raw:
            out[field] = money(to_dec(raw, f"total row {col}"), cur)
            evidence(ev, "batch-1", field, n, raw)
    return out


def _finish(data, ev, kind, cur, txns, totals):
    dates = [t["date"] for t in txns if "date" in t]
    batch = {"id": "batch-1", "kind": kind, "currency": cur, **totals}
    if dates:
        batch["period_start"], batch["period_end"] = min(dates), max(dates)
        evidence(ev, "batch-1", "period_start", None, min(dates))
        evidence(ev, "batch-1", "period_end", None, max(dates))
    data["batches"].append(batch)
    data["transactions"].extend(txns)
    return data, ev


def _money_fields(t, ev, tid, row, n, cur, get, spec, *, blank_zero=()):
    for field, col in spec:
        raw = get(row, col)
        t[field] = money(to_dec(raw, f"row {n} {col}", blank_zero=field in blank_zero), cur)
        evidence(ev, tid, field, n, raw)


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


def extra_gate(data: dict):
    """Yield (rule, expected, computed, independent) for every non-statement, non-settlement batch."""
    for b in data["batches"]:
        kind, cur, bid = b["kind"], b["currency"], b["id"]
        tx = [t for t in data["transactions"] if t["batch_id"] == bid]
        amt = lambda d: f"{fmt(d, cur)} {cur}"  # noqa: E731
        printed_ok = not b.get("totals_are_formulas")

        def printed(total_key, field):
            if total_key in b:
                yield (f"{bid}: sum({field}) = printed total", amt(D(b[total_key])), amt(sum(D(t[field]) for t in tx)),
                       printed_ok)

        if kind == "tax_statement":
            yield from printed("total_amount", "amount")
            yield from printed("total_tax_deducted", "tax_deducted")
            yield from printed("total_tax_deposited", "tax_deposited")
        elif kind == "ais":
            yield from printed("total_reported_value", "reported_value")
        elif kind == "fira":
            bad = [t for t in tx if not fx_check(D(t["foreign_amount"]), Decimal(t["exchange_rate"]), D(t["inr_amount"]))]
            yield (f"{bid}: foreign amount x rate = INR amount on every row (within 0.01)", f"{len(tx)} rows",
                   f"{len(tx) - len(bad)} rows", True)
            if tx and all("net_credited" in t for t in tx):
                bad = [t for t in tx if D(t["inr_amount"]) - D(t["bank_charges"]) != D(t["net_credited"])]
                yield f"{bid}: INR amount - charges = net credited on every row", f"{len(tx)} rows", f"{len(tx) - len(bad)} rows", True
            yield from printed("total_inr_amount", "inr_amount")
            yield from printed("total_net_credited", "net_credited")
        elif kind == "trial_balance":
            deb, cre = sum(D(t["debit"]) for t in tx), sum(D(t["credit"]) for t in tx)
            yield f"{bid}: sum(debits) = sum(credits)", amt(deb), amt(cre), True
            yield from printed("total_debit", "debit")
            yield from printed("total_credit", "credit")
        elif kind == "statement" and b.get("source_method") == "ocr":
            ds = [t["date"] for t in tx]
            ok = sum(1 for a, c in zip(ds, ds[1:]) if a <= c)
            yield f"{bid}: dates are in order (guards OCR date misreads)", f"{max(len(ds) - 1, 0)} steps", f"{ok} steps", False


def _to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == datetime.min.time() else v.isoformat(" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        raise Refusal("PARSE_ERROR", "boolean cell where a value was expected")
    if isinstance(v, float):
        return format(Decimal(repr(v)), "f")
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v).strip()


def _sheet_rows(ws) -> list[list[str]]:
    rows = []
    for k, r in enumerate(ws.iter_rows(values_only=True)):
        if k >= MAX_ROWS:
            raise Refusal("UNSUPPORTED_INPUT", f"sheet {ws.title!r} has more than {MAX_ROWS} rows")
        rows.append([_to_str(c) for c in r])
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def _formula_scan(path: Path, title: str, header_row: int) -> bool:
    """Returns True if the total row holds formulas. Formulas in data rows, or without a stored result, are refused."""
    import openpyxl

    formulas = openpyxl.load_workbook(path, data_only=False, read_only=True)[title]
    cached = openpyxl.load_workbook(path, data_only=True, read_only=True)[title]
    total_formula = False
    for k, (a, b) in enumerate(zip(formulas.iter_rows(values_only=True), cached.iter_rows(values_only=True))):
        if k <= header_row:
            continue
        label = [c for c in a if c not in (None, "")]
        in_total = bool(label) and isinstance(label[0], str) and label[0].strip().lower().rstrip(":") in TOTAL_LABELS
        for x, y in zip(a, b):
            if isinstance(x, str) and x.startswith("="):
                if y is None:
                    raise Refusal("PARSE_ERROR", "workbook has formulas without stored results; open and save it in Excel first")
                if not in_total:
                    raise Refusal("PARSE_ERROR", "formulas in data rows are not independent evidence; export values")
                total_formula = True
    return total_formula


def parse_xlsx(path: Path, p: Params):
    import openpyxl

    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception:
        raise Refusal("UNSUPPORTED_INPUT", "unreadable workbook") from None
    hits = []
    for ws in wb.worksheets[:MAX_SHEETS]:
        rows = _sheet_rows(ws)
        hit = find_header(rows)
        if hit:
            hits.append((ws.title, rows, hit))
    if len(hits) != 1:
        raise Refusal("UNKNOWN_LAYOUT", "no sheet matches a known layout" if not hits else "more than one sheet matches a layout")
    title, rows, (hi, layout, hs) = hits[0]
    total_formula = _formula_scan(path, title, hi)
    data, ev = run_layout(layout, (rows, hi, hs), p)
    if total_formula:
        for b in data["batches"]:
            b["totals_are_formulas"] = True
    return data, ev, "xlsx", layout
