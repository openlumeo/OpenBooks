"""Link payouts and remittances to the bank credits that received them (openbooks.links.v1).

A small factor graph over released openbooks.v1 files. Variables: which bank credit each source (a settlement
payout or a FIRA net credit) landed in. Hard factor: the amounts are exactly equal (Decimal), same currency, and
the bank date falls inside a window after the source date. Soft factors: date closeness and a reference match.
The best joint assignment is a maximum-weight bipartite matching; if a second assignment with the same score exists
the link is reported as ambiguous and not made. Several sources may share one credit only when their exact sum equals it
and exactly one such subset exists. Nothing is linked by similarity: equal amounts are required.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

LINKS_VERSION = "openbooks.links.v1"
WINDOWS = {"settlement": (-1, 10), "fira": (-3, 5)}
MAX_GROUP_CANDIDATES, MAX_GROUP_SIZE = 12, 6


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    amount: Decimal
    currency: str
    day: date
    ref: str | None


@dataclass(frozen=True)
class Credit:
    id: str
    amount: Decimal
    currency: str
    day: date
    text: str


def _amt(m: dict) -> Decimal:
    return Decimal(m["amount"])


def collect(docs: list[dict]) -> tuple[list[Source], list[Credit]]:
    sources, credits = [], []
    for doc in docs:
        if doc.get("status") != "ok":
            continue
        sha = doc["file"]["sha256"][:12]
        for b in doc["data"]["batches"]:
            tx = [t for t in doc["data"]["transactions"] if t["batch_id"] == b["id"]]
            if b["kind"] == "settlement" and b.get("payout"):
                sources.append(Source(f"{sha}:{b['id']}:payout", "settlement", _amt(b["payout"]), b["payout"]["currency"],
                                      date.fromisoformat(b["period_end"]), None))
            elif b["kind"] == "fira":
                for t in tx:
                    m = t.get("net_credited") or t["inr_amount"]
                    sources.append(Source(f"{sha}:{t['id']}", "fira", _amt(m), m["currency"], date.fromisoformat(t["date"]),
                                          t.get("reference")))
            elif b["kind"] == "statement":
                for t in tx:
                    if t["direction"] == "credit":
                        credits.append(Credit(f"{sha}:{t['id']}", _amt(t["amount"]), t["amount"]["currency"],
                                              date.fromisoformat(t["date"]), f"{t.get('description') or ''} {t.get('reference') or ''}".lower()))
    return sources, credits


def _edge(s: Source, c: Credit) -> float | None:
    lo, hi = WINDOWS[s.kind]
    gap = (c.day - s.day).days
    if s.amount != c.amount or s.currency != c.currency or not lo <= gap <= hi:
        return None
    ref = 1.0 if s.ref and s.ref.lower() in c.text else 0.0
    return 1.0 + 0.5 * (1 - abs(gap) / (hi - lo + 1)) + ref


def _components(edges: dict[tuple[int, int], float], n_s: int):
    parent: dict[int, int] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (i, j) in edges:
        parent[find(i)] = find(n_s + j)
    comps: dict[int, tuple[set, set]] = {}
    for (i, j) in edges:
        s, c = comps.setdefault(find(i), (set(), set()))
        s.add(i)
        c.add(j)
    return list(comps.values())


def _solve(w: np.ndarray) -> tuple[float, list[tuple[int, int]]]:
    r, c = linear_sum_assignment(-w)
    pairs = [(int(i), int(j)) for i, j in zip(r, c) if w[i, j] > 0]
    return float(sum(w[i, j] for i, j in pairs)), pairs


def link(docs: list[dict]) -> dict:
    sources, credits = collect(docs)
    edges = {(i, j): w for i, s in enumerate(sources) for j, c in enumerate(credits) if (w := _edge(s, c)) is not None}
    links, ambiguous = [], []
    used_s, used_c = set(), set()

    def add(kind, srcs, credit, how):
        total = sum(s.amount for s in srcs)
        links.append({"id": f"L{len(links) + 1}", "kind": kind, "credit": credit.id, "sources": [s.id for s in srcs],
                      "amount": {"amount": format(credit.amount, "f"), "currency": credit.currency}, "evidence": how,
                      "assertion": {"rule": "sum(source amounts) = credit amount", "expected": format(credit.amount, "f"),
                                    "computed": format(total, "f"), "passed": total == credit.amount}})

    for ss, cs in _components(edges, len(sources)):
        si, ci = sorted(ss), sorted(cs)
        w = np.zeros((len(si), len(ci)))
        for a, i in enumerate(si):
            for b, j in enumerate(ci):
                w[a, b] = edges.get((i, j), 0.0)
        best, pairs = _solve(w)
        unique = True
        for a, b in pairs:
            w2 = w.copy()
            w2[a, b] = 0.0
            if _solve(w2)[0] >= best - 1e-9:
                unique = False
                break
        for a, b in pairs:
            s, c = sources[si[a]], credits[ci[b]]
            used_s.add(si[a])
            used_c.add(ci[b])
            if unique:
                how = ["amount equal", "date in window"] + (["reference in bank description"] if s.ref and s.ref.lower() in c.text else [])
                add("one_to_one", [s], c, how)
            else:
                ambiguous.append({"source": s.id, "credit": c.id, "reason": "another assignment scores the same"})
    for j, c in enumerate(credits):
        if j in used_c:
            continue
        cand = [i for i, s in enumerate(sources) if i not in used_s and s.currency == c.currency
                and WINDOWS[s.kind][0] <= (c.day - s.day).days <= WINDOWS[s.kind][1]][:MAX_GROUP_CANDIDATES]
        hits = [g for n in range(2, min(MAX_GROUP_SIZE, len(cand)) + 1) for g in combinations(cand, n)
                if sum(sources[i].amount for i in g) == c.amount]
        if len(hits) == 1:
            add("many_to_one", [sources[i] for i in hits[0]], c, ["exact sum", "date in window"])
            used_s.update(hits[0])
            used_c.add(j)
        elif hits:
            ambiguous.append({"credit": c.id, "sources": [[sources[i].id for i in g] for g in hits],
                              "reason": "several subsets sum to this credit"})
    return {"schema_version": LINKS_VERSION, "links": links, "ambiguous": ambiguous,
            "unlinked_sources": [s.id for i, s in enumerate(sources) if i not in used_s],
            "unlinked_credits": [c.id for j, c in enumerate(credits) if j not in used_c],
            "inputs": sorted({d["file"]["sha256"] for d in docs if d.get("status") == "ok"})}


def run_link(paths: list[str], out: str) -> int:
    docs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    res = link(docs)
    Path(out).write_text(json.dumps(res, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"links={len(res['links'])} ambiguous={len(res['ambiguous'])} unlinked_sources={len(res['unlinked_sources'])} "
          f"unlinked_credits={len(res['unlinked_credits'])} -> {out}")
    return 0
