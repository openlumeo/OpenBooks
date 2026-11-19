"""Promotion gate for typed-head candidates: a candidate replaces the shipped model only if every rule below holds.

Rules, judged on the candidate's own metrics against the shipped model's:
  shifted coverage >= 0.98, shifted confident-wrong tokens <= baseline, test amount accuracy no more than 0.005 below,
  test confident-wrong tokens <= baseline, test abstain rate no more than 0.40 above (calibration trades abstention for coverage).
Usage: python scripts/promote.py [--baseline metrics.json] candidate_metrics.json [more.json ...]
The default baseline is docs/evidence/roles_metrics_calibrated.json. Candidates need comparable held-out token counts.
Exit code 0 when every candidate passes, 1 otherwise. Reads files only; it never copies or replaces a model.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "evidence" / "roles_metrics_calibrated.json"
MIN_SHIFTED_COVERAGE = 0.98
MAX_TEST_ACCURACY_DROP = 0.005
MAX_TEST_ABSTAIN_RISE = 0.40  # abstain only routes to refusal, never a release; >=98% coverage via calibration costs ~+0.38 (26% -> 64%)


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = data["int8_shipped"]
    for name in ("test", "shifted"):
        row = metrics[name]
        for key in ("role_coverage", "amount_role_accuracy", "amount_abstain_rate"):
            v = row[key]
            if type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1:
                raise ValueError(f"{path}: invalid {name}.{key}")
        n, count, wrong = (row[k] for k in ("tokens", "amount_tokens", "amount_singleton_wrong"))
        if any(type(v) is not int for v in (n, count, wrong)) or not (0 < count <= n and 0 <= wrong <= count):
            raise ValueError(f"{path}: invalid {name} token counts")
        fingerprint = row.get("split_sha256")
        if fingerprint is not None and (not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint)):
            raise ValueError(f"{path}: invalid {name} split hash")
    return metrics


def judge(cand: dict, base: dict) -> list[str]:
    for name in ("test", "shifted"):
        if any(cand[name][k] != base[name][k] for k in ("tokens", "amount_tokens")):
            return [f"{name} split counts differ from baseline; use the same evaluation corpus"]
        if base[name].get("split_sha256") and cand[name].get("split_sha256") != base[name]["split_sha256"]:
            return [f"{name} split contents differ from baseline; use the same evaluation corpus"]
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
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--baseline", type=Path, default=BASELINE)
    cli.add_argument("candidates", nargs="+", type=Path)
    args = cli.parse_args(paths)
    try:
        base = load(args.baseline)
    except (OSError, KeyError, TypeError, ValueError) as e:
        cli.error(str(e))
    print(f"{'candidate':44} {'sh.cov':>7} {'sh.wrong':>8} {'te.acc':>7} {'te.wrong':>8} {'te.abst':>7}  verdict")
    row = lambda name, m, verdict: print(  # noqa: E731
        f"{name[:44]:44} {m['shifted']['role_coverage']:7.4f} {m['shifted']['amount_singleton_wrong']:8d} "
        f"{m['test']['amount_role_accuracy']:7.4f} {m['test']['amount_singleton_wrong']:8d} {m['test']['amount_abstain_rate']:7.4f}  {verdict}")
    row("baseline (shipped)", base, "-")
    bad = 0
    for p in args.candidates:
        try:
            cand = load(p)
        except (OSError, KeyError, TypeError, ValueError) as e:
            print(f"{p}: REJECT: {e}", file=sys.stderr)
            bad += 1
            continue
        fails = judge(cand, base)
        bad += bool(fails)
        row(p.parent.name + "/" + p.name, cand, "PASS" if not fails else "REJECT: " + "; ".join(fails))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
