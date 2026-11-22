"""Balance gates. Core owns the proofs every provider relies on (statement chain, settlement arithmetic) and the rules
that make a release honest: every assertion must pass, at least one must be independent, and every batch kind in the
document must be covered by a registered gate (a kind nobody checks is refused, never waved through).

Providers contribute gates per batch kind: gate(batch, transactions) -> iterable of (rule, expected, computed, independent).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal

from .builders import D
from .errors import Refusal
from .normalise import fmt

GateRule = tuple[str, str, str, bool]
Gate = Callable[[dict, list[dict]], Iterable[GateRule]]
Add = Callable[[str, str, str, bool], None]
CORE_KINDS = frozenset({"statement", "settlement"})


def amount_str(d, cur: str) -> str:
    """Format a Decimal amount with its currency code, e.g. '12.50 INR'."""
    return f"{fmt(d, cur)} {cur}"


def printed_rule(b: dict, tx: list[dict], total_key: str, field: str) -> Iterable[GateRule]:
    """sum(field) over the batch's rows equals the total the document printed, if it printed one."""
    if total_key in b:
        cur = b["currency"]
        yield (f"{b['id']}: sum({field}) = printed total", amount_str(D(b[total_key]), cur),
               amount_str(sum(D(t[field]) for t in tx), cur), not b.get("totals_are_formulas"))


def _statement_rules(data: dict, statements: list[dict], add: Add) -> None:
    """Per statement: opening + movements = closing, no-movement rows, stated closing, running balance."""
    for b in statements:
        cur, tx = b["currency"], [t for t in data["transactions"] if t["batch_id"] == b["id"]]
        signed = [D(t["amount"]) if t["direction"] == "credit" else -D(t["amount"]) for t in tx]
        opening = D(b["opening"])
        add(f"{b['id']}: opening + sum(txns) = closing", amount_str(D(b["closing"]), cur),
            amount_str(opening + sum(signed), cur), not b["opening_derived"])
        if b.get("no_movement"):
            before = {t["id"]: D(t["balance_after"]) for t in tx if "balance_after" in t} | {"opening": opening}
            ok = sum(1 for n in b["no_movement"] if before.get(n["after"]) == D(n["balance"]))
            add(f"{b['id']}: no-movement rows leave the balance unchanged", f"{len(b['no_movement'])} rows", f"{ok} rows", True)
        if "stated_closing" in b:
            add(f"{b['id']}: document-stated closing = last running balance", amount_str(D(b["stated_closing"]), cur),
                amount_str(D(b["closing"]), cur), True)
        if tx and all("balance_after" in t for t in tx):
            run, ok = opening, 0
            for t, s in zip(tx, signed):
                run += s
                ok += run == D(t["balance_after"])
            checked = len(tx) - (1 if b["opening_derived"] else 0)
            if b["opening_derived"]:
                ok -= 1
            add(f"{b['id']}: running balance ties on every row", f"{checked} rows", f"{ok} rows", checked > 0)


def _account_chain_rules(statements: list[dict], add: Add) -> None:
    """Within each account, each statement's closing equals the next statement's opening."""
    by_acct: dict[str, list[dict]] = {}
    for b in statements:
        by_acct.setdefault(b["account_id"], []).append(b)
    for accts in by_acct.values():
        for a, b in zip(accts, accts[1:]):
            add(f"{a['id']} closing = {b['id']} opening", amount_str(D(a["closing"]), a["currency"]),
                amount_str(D(b["opening"]), b["currency"]), True)


def _settlement_rules(data: dict, add: Add) -> None:
    """Per settlement batch: gross - fee - tax = net on each row, and the column totals reconcile to the payout."""
    for b in (x for x in data["batches"] if x["kind"] == "settlement"):
        cur, tx = b["currency"], [t for t in data["transactions"] if t["batch_id"] == b["id"]]
        bad = [t["id"] for t in tx if D(t["gross"]) - D(t["fee"]) - (D(t["tax"]) if "tax" in t else 0) != D(t["net"])]
        add(f"{b['id']}: gross - fees - tax = net on every row", f"{len(tx)} rows", f"{len(tx) - len(bad)} rows", len(tx) > 0)
        g, f, n = (sum((D(t[k]) for t in tx), Decimal(0)) for k in ("gross", "fee", "net"))
        t_tax = sum((D(t["tax"]) for t in tx if "tax" in t), Decimal(0))
        add(f"{b['id']}: sum(gross) - sum(fees) - sum(tax) = sum(net)", amount_str(n, cur), amount_str(g - f - t_tax, cur), False)
        if b["payout"] is not None:
            add(f"{b['id']}: sum(net) = payout", amount_str(D(b["payout"]), cur), amount_str(n, cur), True)


def run_gate(data: dict, provider_gates: Sequence[tuple[str, Gate]] = ()) -> list[dict]:
    """Run core and provider gates over a document. Returns numbered assertions (A1, A2, ...) in a fixed order.
    Refuses (OUTPUT_INVALID) if any batch kind has no registered gate."""
    out: list[dict] = []

    def add(rule, expected, computed, independent):
        out.append({"id": f"A{len(out) + 1}", "rule": rule, "expected": expected, "computed": computed,
                    "passed": expected == computed, "independent": independent})

    statements = [b for b in data["batches"] if b["kind"] == "statement"]
    _statement_rules(data, statements, add)
    _account_chain_rules(statements, add)
    _settlement_rules(data, add)

    covered = CORE_KINDS | {kind for kind, _ in provider_gates}
    for b in data["batches"]:
        if b["kind"] not in covered:
            raise Refusal("OUTPUT_INVALID", f"no gate is registered for batch kind {b['kind']!r}; refusing rather than releasing unchecked")
        tx = [t for t in data["transactions"] if t["batch_id"] == b["id"]]
        for kind, gate in provider_gates:
            if kind == b["kind"]:
                for rule, expected, computed, independent in gate(b, tx):
                    add(rule, expected, computed, independent)
    return out
