"""Balance gates. Core owns the proofs every provider relies on (statement chain, settlement arithmetic) and the rules
that make a release honest: every assertion must pass, every statement transaction must be independently covered, and
every batch kind in the document must be covered by a registered gate (a kind nobody checks is refused, never waved through).

Providers contribute gates per batch kind: gate(batch, transactions) -> iterable of (rule, expected, computed, independent).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal

from .builders import D
from .errors import Refusal
from .normalise import fmt
from .provenance import INDEPENDENT, Provenance, circular_dependencies, weakest

GateRule = tuple[str, str, str, bool]
Gate = Callable[[dict, list[dict]], Iterable[GateRule]]
Add = Callable[[str, str, str, bool, Provenance | None], None]
CORE_KINDS = frozenset({"statement", "settlement"})
OPENING_NOT_EVIDENCE = ("a supplied or derived opening balance is checked but is not independent evidence; "
                        "to release, use a statement that prints its opening balance")


def release_eligible(data: dict, assertions: list[dict]) -> bool:
    """The single release criterion: every statement transaction is covered by an independent assertion, and at least
    one assertion in the document is independent. Caller-supplied or derived openings never satisfy it."""
    counts = coverage(data)
    return counts["independent_covered"] == counts["transactions"] and any(a["independent"] for a in assertions)


def require_balance(data: dict, assertions: list[dict]) -> str:
    failed = [a for a in assertions if not a["passed"]]
    if failed:
        raise Refusal("BALANCE_MISMATCH", "; ".join(
            f"{a['rule']} (expected {a['expected']}, got {a['computed']})" for a in failed))
    if release_eligible(data, assertions):
        return "independent"
    counts = coverage(data)
    missing = counts["transactions"] - counts["independent_covered"]
    none_independent = "" if any(a["independent"] for a in assertions) else "; no independent balance evidence in this file"
    weak_opening = any(b["kind"] == "statement" and _opening_provenance(b) not in INDEPENDENT for b in data["batches"])
    advice = f". Note: {OPENING_NOT_EVIDENCE}" if weak_opening else ""
    raise Refusal("BALANCE_MISMATCH", f"insufficient independent evidence: {missing} of {counts['transactions']} "
                  f"transactions lack independent coverage{none_independent}{advice}")


def amount_str(d, cur: str) -> str:
    """Format a Decimal amount with its currency code, e.g. '12.50 INR'."""
    return f"{fmt(d, cur)} {cur}"


def printed_rule(b: dict, tx: list[dict], total_key: str, field: str) -> Iterable[GateRule]:
    """sum(field) over the batch's rows equals the total the document printed, if it printed one."""
    if total_key in b:
        cur = b["currency"]
        yield (f"{b['id']}: sum({field}) = printed total", amount_str(D(b[total_key]), cur),
               amount_str(sum(D(t[field]) for t in tx), cur), not b.get("totals_are_formulas"))


def _opening_provenance(b: dict) -> Provenance:
    if "opening_provenance" in b:
        return Provenance(b["opening_provenance"])
    return Provenance.DETERMINISTICALLY_DERIVED if b["opening_derived"] else Provenance.CALLER_SUPPLIED


def _closing_provenance(b: dict) -> Provenance:
    return Provenance(b.get("closing_provenance", Provenance.SOURCE_OBSERVED.value))


def _balance_provenance(t: dict) -> Provenance:
    return Provenance(t.get("balance_after_provenance", Provenance.SOURCE_OBSERVED.value))


def _sum_provenance(b: dict) -> Provenance:
    return weakest(_opening_provenance(b), _closing_provenance(b))


def _transition_provenances(opening_prov: Provenance, tx: list[dict]) -> list[Provenance]:
    """Row i's transition (previous balance + amount = printed balance) is independent only if every operand is observed."""
    previous = [opening_prov] + [_balance_provenance(t) for t in tx[:-1]]
    return [weakest(prev, _balance_provenance(t)) for prev, t in zip(previous, tx)]


def _running_rules(b: dict, tx: list[dict], signed: list[Decimal], opening: Decimal, opening_prov: Provenance,
                   add: Add) -> None:
    printed = [D(t["balance_after"]) for t in tx]
    previous = [opening] + printed[:-1]
    ok = sum(1 for prev, s, cur in zip(previous, signed, printed) if prev + s == cur)
    provenances = _transition_provenances(opening_prov, tx)
    independent = all(p in INDEPENDENT for p in provenances)
    weak = next((p for p in provenances if p not in INDEPENDENT), provenances[0])
    add(f"{b['id']}: running balance ties on every row", f"{len(tx)} rows", f"{ok} rows", independent,
        Provenance.SOURCE_OBSERVED if independent else weak)


def _statement_rules(data: dict, statements: list[dict], add: Add) -> None:
    """Per statement: opening + movements = closing, no-movement rows, stated closing, running balance."""
    for b in statements:
        cur, tx = b["currency"], [t for t in data["transactions"] if t["batch_id"] == b["id"]]
        signed = [D(t["amount"]) if t["direction"] == "credit" else -D(t["amount"]) for t in tx]
        opening = D(b["opening"])
        opening_prov = _opening_provenance(b)
        sum_prov = _sum_provenance(b)
        add(f"{b['id']}: opening + sum(txns) = closing", amount_str(D(b["closing"]), cur),
            amount_str(opening + sum(signed), cur), sum_prov in INDEPENDENT, sum_prov)
        if b.get("no_movement"):
            before = {t["id"]: D(t["balance_after"]) for t in tx if "balance_after" in t} | {"opening": opening}
            ok = sum(1 for n in b["no_movement"] if before.get(n["after"]) == D(n["balance"]))
            independent = opening_prov in INDEPENDENT or all(n["after"] != "opening" for n in b["no_movement"])
            add(f"{b['id']}: no-movement rows leave the balance unchanged", f"{len(b['no_movement'])} rows", f"{ok} rows",
                independent, Provenance.SOURCE_OBSERVED if independent else opening_prov)
        if "stated_closing" in b:
            add(f"{b['id']}: document-stated closing = last running balance", amount_str(D(b["stated_closing"]), cur),
                amount_str(D(b["closing"]), cur), True)
        printed = sum(1 for t in tx if "balance_after" in t)
        if printed and printed != len(tx):
            raise Refusal("BALANCE_MISMATCH", f"{b['id']}: running balances are printed on {printed} of {len(tx)} rows; "
                          "a partial chain cannot verify the document")
        if tx and printed:
            _running_rules(b, tx, signed, opening, opening_prov, add)


def _account_chain_rules(statements: list[dict], add: Add) -> None:
    """Within each account, each statement's closing equals the next statement's opening."""
    by_acct: dict[str, list[dict]] = {}
    for b in statements:
        by_acct.setdefault(b["account_id"], []).append(b)
    for accts in by_acct.values():
        for a, b in zip(accts, accts[1:]):
            opening_prov = _opening_provenance(b)
            independent = opening_prov in INDEPENDENT
            add(f"{a['id']} closing = {b['id']} opening", amount_str(D(a["closing"]), a["currency"]),
                amount_str(D(b["opening"]), b["currency"]), independent,
                Provenance.SOURCE_OBSERVED if independent else opening_prov)


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


def coverage(data: dict) -> dict:
    """Per-document transaction coverage over statement batches. A transaction is covered when the batch's sum
    assertion covers it (every row) and it is independent when that assertion is, or when its own running-balance
    transition is independent. Returns the counts a release needs: total, covered, independent_covered."""
    total = covered = independent_covered = 0
    for b in data["batches"]:
        if b["kind"] != "statement":
            continue
        tx = [t for t in data["transactions"] if t["batch_id"] == b["id"]]
        total += len(tx)
        covered += len(tx)
        if _sum_provenance(b) in INDEPENDENT:
            independent_covered += len(tx)
        elif tx and all("balance_after" in t for t in tx):
            independent_covered += sum(p in INDEPENDENT for p in _transition_provenances(_opening_provenance(b), tx))
    return {"transactions": total, "covered_transactions": covered, "independent_covered": independent_covered,
            "conditional_transactions": covered - independent_covered}


def verification_cycles(data: dict) -> tuple[str, ...]:
    """Value nodes whose verification depends, directly or through others, on themselves."""
    edges: dict[str, set[str]] = {}
    statements = [b for b in data["batches"] if b["kind"] == "statement"]
    for b in statements:
        bid = b["id"]
        rows = f"{bid}.rows"
        edges.setdefault(f"{bid}.closing", set()).update({f"{bid}.opening", rows})
        if any("balance_after" in t for t in data["transactions"] if t["batch_id"] == bid):
            edges.setdefault(rows, set()).add(f"{bid}.opening")
        if _opening_provenance(b) is Provenance.DETERMINISTICALLY_DERIVED:
            edges.setdefault(f"{bid}.opening", set()).add(rows)
    for a, b in zip(statements, statements[1:]):
        if a["account_id"] == b["account_id"]:
            edges.setdefault(f"{b['id']}.opening", set()).add(f"{a['id']}.closing")
    return circular_dependencies(edges)


def _refuse_independent_circularity(data: dict) -> None:
    cycles = set(verification_cycles(data))
    for b in data["batches"]:
        if b["kind"] == "statement" and f"{b['id']}.opening" in cycles and _opening_provenance(b) in INDEPENDENT:
            raise Refusal("OUTPUT_INVALID", f"{b['id']}: independent opening is part of a circular verification dependency")


def run_gate(data: dict, provider_gates: Sequence[tuple[str, Gate]] = ()) -> list[dict]:
    """Run core and provider gates over a document. Returns numbered assertions (A1, A2, ...) in a fixed order.
    Identical assertions are kept once, so duplicated gate output cannot inflate the independent count.
    Refuses (OUTPUT_INVALID) if any batch kind has no registered gate."""
    out: list[dict] = []
    seen: set[tuple] = set()

    def add(rule, expected, computed, independent, provenance=None):
        if provenance is None:
            provenance = Provenance.SOURCE_OBSERVED if independent else Provenance.DETERMINISTICALLY_DERIVED
        if (provenance in INDEPENDENT) != independent:
            raise ValueError(f"{rule}: independence contradicts provenance {provenance.value}")
        key = (rule, expected, computed, independent, provenance.value)
        if key in seen:
            return
        seen.add(key)
        out.append({"id": f"A{len(out) + 1}", "rule": rule, "expected": expected, "computed": computed,
                    "passed": expected == computed, "independent": independent, "provenance": provenance.value})

    statements = [b for b in data["batches"] if b["kind"] == "statement"]
    _refuse_independent_circularity(data)
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
