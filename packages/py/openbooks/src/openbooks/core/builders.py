"""Builders shared by every parser family: the canonical data skeleton, statement and settlement batches, total rows.

Moved verbatim from pipeline.py and parsers_extra.py (names made public); behaviour is frozen by tests/characterise.
"""
from __future__ import annotations

from decimal import Decimal

from .errors import Refusal
from .evidence import evidence
from .iso4217 import exponent_of
from .normalise import money, to_dec
from .params import Params
from .provenance import Provenance


def empty_data() -> dict:
    return {"accounts": [], "parties": [], "batches": [], "transactions": [], "claims": []}



def currency_of(hs: list[str], body: list[list[str]], p: Params) -> str:
    if "currency" in hs:
        i = hs.index("currency")
        vals = {r[i].strip().upper() for r in body if len(r) > i and r[i].strip()}
        if len(vals) != 1:
            raise Refusal("PARSE_ERROR", f"expected one currency, found {sorted(vals)}")
        cur = vals.pop()
    elif p.currency:
        cur = p.currency.upper()
    else:
        raise Refusal("PARSE_ERROR", "currency not in file; supply --currency")
    exponent_of(cur)
    return cur


def body_rows(rows, hi, hs):
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


def record_date_order(ev, order: str, provenance: str) -> None:
    evidence(ev, "batch-1", "date_order", None, order, provenance=provenance)


def statement_doc(recs, cur, account, opening, *, method="parser", opening_loc=None, stated_closing=None, noops=(),
                  date_order=None):
    """Shared by CSV, PDF and scan paths. Each rec may carry loc={field: (page, bbox, conf)}.
    opening=None means derived from the first row (not independent). stated_closing=(Decimal, raw, loc)."""
    if recs[0]["date"] > recs[-1]["date"]:
        recs.reverse()
        noops = [{**n, "pos": len(recs) - n["pos"]} for n in noops]
    derived = opening is None
    if derived:
        opening = recs[0]["bal"] - (recs[0]["amt"] if recs[0]["dir"] == "credit" else -recs[0]["amt"])
    if derived:
        opening_prov = Provenance.DETERMINISTICALLY_DERIVED
    elif opening_loc is None:
        opening_prov = Provenance.CALLER_SUPPLIED
    elif "+model" in method:
        opening_prov = Provenance.MODEL_PREDICTED
    else:
        opening_prov = Provenance.SOURCE_OBSERVED
    data, ev = empty_data(), {}
    if date_order is not None:
        record_date_order(ev, *date_order)

    def put(rid, field, raw, row=None, loc=None, provenance=None):
        page, bbox, conf = loc or (None, None, None)
        evidence(ev, rid, field, row, raw, page=page, bbox=bbox, method=method if loc else "parser", conf=conf,
                 provenance=provenance)

    data["accounts"].append({"id": "acct-1", "number": account, "currency": cur})
    batch = {"id": "batch-1", "kind": "statement", "account_id": "acct-1", "currency": cur,
             "period_start": recs[0]["date"], "period_end": recs[-1]["date"],
             "opening": money(opening, cur), "closing": money(recs[-1]["bal"], cur), "opening_derived": derived,
             "opening_provenance": opening_prov.value}
    if method != "parser":
        batch["source_method"] = method
    if stated_closing:
        batch["stated_closing"] = money(stated_closing[0], cur)
    data["batches"].append(batch)
    put("batch-1", "opening", "derived from first row balance" if derived else (
        "supplied by caller" if opening_loc is None else opening_loc[1]), loc=None if opening_loc is None else opening_loc[0],
        provenance=opening_prov.value)
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


def settlement_batch(data, ev, cur, txns, payout, payout_raw):
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


TOTAL_LABELS = {"total", "totals", "grand total"}


def cell_getter(hs: list[str]):
    def get(row: list[str], name: str) -> str:
        i = hs.index(name) if name in hs else -1
        return row[i].strip() if 0 <= i < len(row) else ""

    return get



def is_total(row: list[str]) -> bool:
    first = next((c.strip() for c in row if c.strip()), "")
    return first.lower().rstrip(":") in TOTAL_LABELS


def split_total(body):
    rows, total = [], None
    for n, row in body:
        if is_total(row):
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


def stated_totals(total, hs, cur, spec, ev) -> dict:
    """Printed totals become batch fields with evidence; blank total cells are simply not stated."""
    out: dict = {}
    if total is None:
        return out
    n, row = total
    get = cell_getter(hs)
    for field, col in spec:
        raw = get(row, col)
        if raw:
            out[field] = money(to_dec(raw, f"total row {col}"), cur)
            evidence(ev, "batch-1", field, n, raw)
    return out


def finish_batch(data, ev, kind, cur, txns, totals):
    dates = [t["date"] for t in txns if "date" in t]
    batch = {"id": "batch-1", "kind": kind, "currency": cur, **totals}
    if dates:
        batch["period_start"], batch["period_end"] = min(dates), max(dates)
        evidence(ev, "batch-1", "period_start", None, min(dates))
        evidence(ev, "batch-1", "period_end", None, max(dates))
    data["batches"].append(batch)
    data["transactions"].extend(txns)
    return data, ev


def money_fields(t, ev, tid, row, n, cur, get, spec, *, blank_zero=()):
    for field, col in spec:
        raw = get(row, col)
        t[field] = money(to_dec(raw, f"row {n} {col}", blank_zero=field in blank_zero), cur)
        evidence(ev, tid, field, n, raw)


def D(m: dict) -> Decimal:
    return Decimal(m["amount"])

