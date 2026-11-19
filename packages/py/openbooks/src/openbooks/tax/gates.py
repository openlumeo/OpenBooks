"""Gates for the tax and ledger batch kinds: printed totals, FX arithmetic, debits equal credits. Rules and wording are unchanged from 0.1."""
from __future__ import annotations

from decimal import Decimal

from openbooks.core.builders import D
from openbooks.core.gates import amount_str, printed_rule

from .parsers import fx_check


def tax_statement(b, tx):
    yield from printed_rule(b, tx, "total_amount", "amount")
    yield from printed_rule(b, tx, "total_tax_deducted", "tax_deducted")
    yield from printed_rule(b, tx, "total_tax_deposited", "tax_deposited")


def ais(b, tx):
    yield from printed_rule(b, tx, "total_reported_value", "reported_value")


def form_1099b(b, tx):
    bid = b["id"]
    bad = [t for t in tx if D(t["proceeds"]) - D(t["cost_basis"]) + (D(t["adjustment"]) if "adjustment" in t else 0)
           != D(t["gain_loss"])]
    yield (f"{bid}: proceeds - cost basis + adjustment = gain or loss on every row", f"{len(tx)} rows",
           f"{len(tx) - len(bad)} rows", len(tx) > 0)
    yield from printed_rule(b, tx, "total_proceeds", "proceeds")
    yield from printed_rule(b, tx, "total_cost_basis", "cost_basis")
    yield from printed_rule(b, tx, "total_gain_loss", "gain_loss")


def fira(b, tx):
    bid = b["id"]
    bad = [t for t in tx if not fx_check(D(t["foreign_amount"]), Decimal(t["exchange_rate"]), D(t["inr_amount"]))]
    yield (f"{bid}: foreign amount x rate = INR amount on every row (within 0.01)", f"{len(tx)} rows",
           f"{len(tx) - len(bad)} rows", True)
    if tx and all("net_credited" in t for t in tx):
        bad = [t for t in tx if D(t["inr_amount"]) - D(t["bank_charges"]) != D(t["net_credited"])]
        yield f"{bid}: INR amount - charges = net credited on every row", f"{len(tx)} rows", f"{len(tx) - len(bad)} rows", True
    yield from printed_rule(b, tx, "total_inr_amount", "inr_amount")
    yield from printed_rule(b, tx, "total_net_credited", "net_credited")


def trial_balance(b, tx):
    bid, cur = b["id"], b["currency"]
    deb, cre = sum(D(t["debit"]) for t in tx), sum(D(t["credit"]) for t in tx)
    yield f"{bid}: sum(debits) = sum(credits)", amount_str(deb, cur), amount_str(cre, cur), True
    yield from printed_rule(b, tx, "total_debit", "debit")
    yield from printed_rule(b, tx, "total_credit", "credit")
