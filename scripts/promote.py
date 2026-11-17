"""Promotion gate for typed-head candidates: a candidate replaces the shipped model only if every rule below holds.

Rules, judged on the candidate's own metrics against the shipped model's:
  shifted coverage >= 0.98, shifted confident-wrong tokens <= baseline, test amount accuracy no more than 0.005 below,
  test confident-wrong tokens <= baseline, test abstain rate no more than 0.40 above (calibration trades abstention for coverage).
Usage: python scripts/promote.py [--baseline metrics.json] candidate_metrics.json [more.json ...]
The default baseline is docs/evidence/roles_metrics.json; pass --baseline while an experiment queue is overwriting that file.
Exit code 0 when every candidate passes, 1 otherwise. Reads files only; it never copies or replaces a model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "evidence" / "roles_metrics.json"
MIN_SHIFTED_COVERAGE = 0.98
MAX_TEST_ACCURACY_DROP = 0.005
MAX_TEST_ABSTAIN_RISE = 0.40  # abstain only routes to refusal, never a release; >=98% coverage via calibration costs ~+0.38 (26% -> 64%)


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("int8_shipped") or data["fp32"]


def judge(cand: dict, base: dict) -> list[str]:
    fails = []
    if cand["shifted"]["role_coverage"] < MIN_SHIFTED_COVERAGE:
        fails.append(f"shifted coverage {cand['shifted']['role_coverage']:.4f} < {MIN_SHIFTED_COVERAGE}")
    if cand["shifted"]["amount_singleton_wrong"] > base["shifted"]["amount_singleton_wrong"]:
        fails.append(f"shifted confident-wrong {cand['shifted']['amount_singleton_wrong']} > baseline {base['shifted']['amount_singleton_wrong']}")
    if cand["test"]["amount_role_accuracy"] < base["test"]["amount_role_accuracy"] - MAX_TEST_ACCURACY_DROP:
        fails.append("test amount accuracy dropped more than allowed")
    if cand["test"]["amount_singleton_wrong"] > base["test"]["amount_singleton_wrong"]:
        fails.append(f"test confident-wrong {cand['test']['amount_singleton_wrong']} > baseline {base['test']['amount_singleton_wrong']}")
    if cand["test"]["amount_abstain_rate"] > base["test"]["amount_abstain_rate"] + MAX_TEST_ABSTAIN_RISE:
        fails.append("test abstain rate rose more than allowed")
    return fails


def main(paths: list[str]) -> int:
    baseline = BASELINE
    if paths[:1] == ["--baseline"]:
        baseline, paths = Path(paths[1]), paths[2:]
    base = load(baseline)
    print(f"{'candidate':44} {'sh.cov':>7} {'sh.wrong':>8} {'te.acc':>7} {'te.wrong':>8} {'te.abst':>7}  verdict")
    row = lambda name, m, verdict: print(  # noqa: E731
        f"{name[:44]:44} {m['shifted']['role_coverage']:7.4f} {m['shifted']['amount_singleton_wrong']:8d} "
        f"{m['test']['amount_role_accuracy']:7.4f} {m['test']['amount_singleton_wrong']:8d} {m['test']['amount_abstain_rate']:7.4f}  {verdict}")
    row("baseline (shipped)", base, "-")
    bad = 0
    for p in paths:
        cand = load(Path(p))
        fails = judge(cand, base)
        bad += bool(fails)
        row(Path(p).parent.name + "/" + Path(p).name, cand, "PROMOTE" if not fails else "REJECT: " + "; ".join(fails))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
