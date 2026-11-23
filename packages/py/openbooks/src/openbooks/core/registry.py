"""Layout detection and provider registry.

Core owns *what exists and in what order* (KNOWN_LAYOUTS, KNOWN_SNIFFERS): detection never depends on which providers
happen to be registered. Providers (openbooks.statements, openbooks.gateways, openbooks.tax, or a third-party plugin) supply
only *implementations*, discovered through entry points:

  openbooks.layouts    name = layout id          value -> parse(args, params) -> (data, evidence)
  openbooks.sniffers   name = layout id          value -> parse(text, params) -> (data, evidence)
  openbooks.frontends  name = "document"         value -> object with extract(path, params) and identity(params)
  openbooks.gates      name = kind[:label]       value -> gate(batch, transactions) -> rules
  openbooks.linkers    name = "default"          value -> module/object with link(docs) and run_link(paths, out)

If detection recognises a known layout and its provider is absent the result is ProviderMissing (a typed refusal that
names the provider). Detection never continues to a lower-ranked layout, because a looser layout (bank CSV, trial balance)
could otherwise claim a file meant for the missing one.
"""
from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from .errors import PluginLoadError, ProviderMissing, Refusal
from .gates import Gate
from .normalise import norm

LAYOUT_API_VERSION = 1
HEADER_SCAN_ROWS = 30

STATEMENTS, GATEWAYS, TAX = "openbooks.statements", "openbooks.gateways", "openbooks.tax"
RETIRED_DISTRIBUTIONS = ("openbooks-core", "openbooks-statements", "openbooks-gateways", "openbooks-tax", "openbooks-doctor")

BANK_ROLES = {
    "date": ("txn_date", "transaction_date", "value_date", "posting_date", "date"),
    "desc": ("description", "narration", "particulars", "transaction_remarks", "details"),
    "debit": ("debit", "withdrawal", "withdrawals", "withdrawal_amt", "debit_amount", "dr"),
    "credit": ("credit", "deposit", "deposits", "deposit_amt", "credit_amount", "cr"),
    "balance": ("balance", "closing_balance", "running_balance"),
    "ref": ("ref_no", "reference", "chq_ref_no", "utr", "cheque_no"),
}
SIGNED_BANK_ROLES = {
    "date": BANK_ROLES["date"],
    "desc": BANK_ROLES["desc"],
    "amount": ("amount", "amt", "transaction_amount", "signed_amount"),
    "balance": BANK_ROLES["balance"],
}
DIRECTION_HEADERS = ("type", "dr_cr", "drcr", "cr_dr", "crdr", "indicator", "debit_credit", "direction", "txn_type", "transaction_type")
STRIPE_REQ = {"balance_transaction_id", "created", "currency", "gross", "fee", "net"}
RAZORPAY_REQ = {"entity_id", "type", "debit", "credit", "amount", "fee", "tax", "settlement_id"}
TDS_REQ = {"deductor_name", "tan", "section", "transaction_date", "amount_paid_credited", "tax_deducted", "tds_deposited"}
AIS_REQ = {"information_category", "information_description", "source", "reported_value"}
FIRA_REQ = {"fira_no", "date", "currency", "foreign_amount", "exchange_rate", "inr_amount"}
TB_REQ = {"account", "debit", "credit"}
PAYPAL_REQ = {"date", "type", "status", "currency", "gross", "fee", "net", "transaction_id"}
WISE_REQ = {"transferwise_id", "date", "amount", "currency", "description", "running_balance"}
B1099_REQ = {"description", "date_acquired", "date_sold", "proceeds", "cost_basis", "gain_loss"}


def bank_cols(hs: list[str]) -> dict[str, int]:
    return {r: hs.index(next(n for n in names if n in hs)) for r, names in BANK_ROLES.items() if any(n in hs for n in names)}


def signed_bank_cols(hs: list[str]) -> dict[str, int] | None:
    """Column index per role when every role has exactly one header and nothing hints at a debit/credit split or direction flag."""
    if any(n in hs for n in (*BANK_ROLES["debit"], *BANK_ROLES["credit"], *DIRECTION_HEADERS)):
        return None
    found: dict[str, int] = {}
    for role, names in SIGNED_BANK_ROLES.items():
        hits = [i for i, h in enumerate(hs) if h in names]
        if len(hits) != 1:
            return None
        found[role] = hits[0]
    return found


@dataclass(frozen=True)
class LayoutSpec:
    """A layout core knows exists. `rank` is the detection order (lower first); `distribution` is the provider that owns it."""
    id: str
    rank: int
    distribution: str
    batch_kinds: frozenset[str]
    matches: Callable[[list[str], frozenset[str]], bool]


def _req(req: set[str]) -> Callable[[list[str], frozenset[str]], bool]:
    return lambda hs, s: req <= s


KNOWN_LAYOUTS: tuple[LayoutSpec, ...] = (
    LayoutSpec("stripe_balance.v1", 10, GATEWAYS, frozenset({"settlement"}), _req(STRIPE_REQ)),
    LayoutSpec("razorpay_settlement.v1", 20, GATEWAYS, frozenset({"settlement"}), _req(RAZORPAY_REQ)),
    LayoutSpec("paypal_activity.v1", 30, GATEWAYS, frozenset({"settlement"}), _req(PAYPAL_REQ)),
    LayoutSpec("wise_statement.v1", 40, GATEWAYS, frozenset({"statement"}), _req(WISE_REQ)),
    LayoutSpec("form_1099b.v1", 50, TAX, frozenset({"form_1099b"}), _req(B1099_REQ)),
    LayoutSpec("tds_26as.v1", 60, TAX, frozenset({"tax_statement"}), _req(TDS_REQ)),
    LayoutSpec("ais.v1", 70, TAX, frozenset({"ais"}), _req(AIS_REQ)),
    LayoutSpec("fira.v1", 80, TAX, frozenset({"fira"}), _req(FIRA_REQ)),
    LayoutSpec("bank_csv.v1", 90, STATEMENTS, frozenset({"statement"}),
               lambda hs, s: {"date", "desc", "debit", "credit", "balance"} <= set(bank_cols(hs))),
    LayoutSpec("bank_csv_signed.v1", 95, STATEMENTS, frozenset({"statement"}),
               lambda hs, s: signed_bank_cols(hs) is not None),
    LayoutSpec("trial_balance.v1", 100, TAX, frozenset({"trial_balance"}), _req(TB_REQ)),
)
LAYOUT_BY_ID = {s.id: s for s in KNOWN_LAYOUTS}


@dataclass(frozen=True)
class SnifferSpec:
    """Text formats recognised before any CSV parsing, in this order."""
    id: str
    format: str
    distribution: str
    matches: Callable[[str], bool]


def _is_ofx(text: str) -> bool:
    head = text[:400].upper()
    return "<OFX" in head or "OFXHEADER" in head


def _is_mt940(text: str) -> bool:
    return all(re.search(rf"^:{t}:", text, re.M) for t in ("20", "60[FM]", "62[FM]"))


def _is_camt053(text: str) -> bool:
    return re.search(r"<(\w+:)?BkToCstmrStmt[\s>]", text[:8000]) is not None


KNOWN_SNIFFERS: tuple[SnifferSpec, ...] = (SnifferSpec("ofx.v1", "ofx", STATEMENTS, _is_ofx),
                                           SnifferSpec("mt940.v1", "mt940", STATEMENTS, _is_mt940),
                                           SnifferSpec("camt053.v1", "camt053", STATEMENTS, _is_camt053))
SNIFFER_BY_ID = {s.id: s for s in KNOWN_SNIFFERS}
FRONTEND_DISTRIBUTION = {"document": STATEMENTS}
GATE_OWNER = {"tax_statement": TAX, "ais": TAX, "form_1099b": TAX, "fira": TAX, "trial_balance": TAX,
              "statement:ocr_dates": STATEMENTS}


def find_header(rows: list[list[str]]) -> tuple[int, str, list[str]] | None:
    """First header row (within HEADER_SCAN_ROWS) that matches a known layout; on one row, the lowest rank wins."""
    for i, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        hs = [norm(c) for c in row]
        s = frozenset(hs)
        for spec in KNOWN_LAYOUTS:
            if spec.matches(hs, s):
                return i, spec.id, hs
    return None


@dataclass(frozen=True)
class Detected:
    format: str
    layout: str
    args: Any


def detect(text: str) -> Detected:
    """Which known layout is this text? Unknown layouts are refused, never guessed. Does not look at installed providers."""
    for sn in KNOWN_SNIFFERS:
        if sn.matches(text):
            return Detected(sn.format, sn.id, None)
    for delim in (",", ";", "\t"):
        try:
            rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        except csv.Error as e:
            raise Refusal("PARSE_ERROR", f"the file is not readable as a table ({e})") from None
        hit = find_header(rows)
        if hit:
            return Detected("csv", hit[1], (rows, hit[0], hit[2]))
    raise Refusal("UNKNOWN_LAYOUT", "no known layout matches this file")


def _entry_points(group: str, *, unique_names: bool = True) -> list[EntryPoint]:
    """Entry points of one openbooks.* group, de-duplicated (an editable and a regular install may both list one)."""
    seen: dict[tuple[str, str], EntryPoint] = {}
    for ep in entry_points(group=f"openbooks.{group}"):
        if _dist_name(ep) in RETIRED_DISTRIBUTIONS:
            continue
        seen.setdefault((ep.name, ep.value), ep)
    out = [seen[k] for k in sorted(seen)]
    if unique_names:
        names = [ep.name for ep in out]
        for n in set(names):
            if names.count(n) > 1:
                dup = ", ".join(ep.value for ep in out if ep.name == n)
                raise PluginLoadError(f"openbooks.{group}: {n!r} is registered more than once ({dup})")
    return out


def _dist_name(ep: EntryPoint) -> str | None:
    dist = getattr(ep, "dist", None)
    name = getattr(dist, "name", None) or (dist.metadata["Name"] if dist is not None else None)
    return name.lower().replace("_", "-") if name else None


def _is_entry_point(x: Any) -> bool:
    return isinstance(x, EntryPoint) or all(hasattr(x, a) for a in ("load", "value", "group", "name"))


def _load(x: Any, what: str) -> Any:
    if _is_entry_point(x):
        try:
            return x.load()
        except Exception as e:  # noqa: BLE001 - a provider that cannot load is a broken install, never a verdict on the file
            raise PluginLoadError(f"provider for {what} failed to load ({x.value}): {type(e).__name__}: {e}") from e
    return x


class Registry:
    """Installed implementations. Build with Registry.discover(), or pass mappings directly in tests."""

    def __init__(self, layouts: Mapping[str, Any] | None = None, sniffers: Mapping[str, Any] | None = None,
                 frontends: Mapping[str, Any] | None = None, gates: Iterable[tuple[str, Any]] = (),
                 linkers: Mapping[str, Any] | None = None) -> None:
        self._layouts = dict(layouts or {})
        self._sniffers = dict(sniffers or {})
        self._frontends = dict(frontends or {})
        self._gates = list(gates)
        self._linkers = dict(linkers or {})
        for lid in self._layouts:
            if lid not in LAYOUT_BY_ID:
                raise PluginLoadError(f"openbooks.layouts: {lid!r} is not a known layout id")
        for sid in self._sniffers:
            if sid not in SNIFFER_BY_ID:
                raise PluginLoadError(f"openbooks.sniffers: {sid!r} is not a known sniffer id")
        for name in self._frontends:
            if name not in FRONTEND_DISTRIBUTION:
                raise PluginLoadError(f"openbooks.frontends: {name!r} is not a known frontend")

    @classmethod
    def discover(cls) -> "Registry":
        return cls(layouts={ep.name: ep for ep in _entry_points("layouts")},
                   sniffers={ep.name: ep for ep in _entry_points("sniffers")},
                   frontends={ep.name: ep for ep in _entry_points("frontends")},
                   gates=[(ep.name, ep) for ep in _entry_points("gates", unique_names=False)],
                   linkers={ep.name: ep for ep in _entry_points("linkers")})

    def installed_layouts(self) -> set[str]:
        return set(self._layouts) | set(self._sniffers)

    def layout_parser(self, layout_id: str) -> Callable:
        if layout_id in self._layouts:
            return _load(self._layouts[layout_id], layout_id)
        raise ProviderMissing(layout_id, LAYOUT_BY_ID[layout_id].distribution)

    def sniffer_parser(self, layout_id: str) -> Callable:
        if layout_id in self._sniffers:
            return _load(self._sniffers[layout_id], layout_id)
        raise ProviderMissing(layout_id, SNIFFER_BY_ID[layout_id].distribution)

    def frontend(self, name: str = "document") -> Any:
        if name in self._frontends:
            return _load(self._frontends[name], f"frontend {name}")
        raise ProviderMissing("a PDF or image statement", FRONTEND_DISTRIBUTION[name])

    def gates(self, kinds: Iterable[str] | None = None) -> list[tuple[str, Gate]]:
        """Gates for these batch kinds (all if None). Only the gates a document needs are imported."""
        want = None if kinds is None else set(kinds)
        return [(name.split(":")[0], _load(g, f"gate {name}")) for name, g in sorted(self._gates, key=lambda x: x[0])
                if want is None or name.split(":")[0] in want]

    def linker(self) -> Any | None:
        return _load(self._linkers["default"], "linker") if "default" in self._linkers else None

    def run_layout(self, layout_id: str, args: Any, params: Any):
        return self.layout_parser(layout_id)(args, params)

    def restricted_to(self, distributions: Iterable[str]) -> "Registry":
        """A view as if only these providers were installed. For tests of the missing-provider guarantees."""
        keep = set(distributions)
        return Registry(
            layouts={k: v for k, v in self._layouts.items() if LAYOUT_BY_ID[k].distribution in keep},
            sniffers={k: v for k, v in self._sniffers.items() if SNIFFER_BY_ID[k].distribution in keep},
            frontends={k: v for k, v in self._frontends.items() if FRONTEND_DISTRIBUTION.get(k) in keep},
            gates=[(n, g) for n, g in self._gates if GATE_OWNER.get(n) in keep],
            linkers=self._linkers)


@lru_cache(maxsize=1)
def default_registry() -> Registry:
    return Registry.discover()


def reload_default_registry() -> Registry:
    default_registry.cache_clear()
    return default_registry()
