"""Token screening gate for typed-head candidates on identical fingerprinted splits.

Each direction must correctly commit on at least 1% of its labeled tokens and
match or exceed its shipped count. Wrong amount commitments cannot increase.
Shifted coverage must reach 0.98 and test amount accuracy may drop at most 0.005.
Usage: python scripts/promote.py [--baseline metrics.json] candidate_metrics.json [more.json ...]
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
BASELINE = ROOT / "docs" / "evidence" / "roles_metrics_token_baseline.json"
MIN_SHIFTED_COVERAGE = 0.98
MAX_TEST_ACCURACY_DROP = 0.005
DIRECTIONS = ("debit", "credit")
AMOUNT_ROLES = (*DIRECTIONS, "balance")
MIN_DIRECTION_RECALL = 0.01


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
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            raise ValueError(f"{path}: invalid {name} split hash")
        roles = row["by_role"]
        if not isinstance(roles, dict):
            raise ValueError(f"{path}: invalid {name}.by_role")
        for role, counts in roles.items():
            support, covered, actual, predicted, correct = (
                counts[key] for key in ("tokens", "covered", "singletons_on_true_role",
                                        "predicted_singletons", "correct_singletons")
            )
            if (any(type(v) is not int for v in (support, covered, actual, predicted, correct))
                    or not (0 <= correct <= min(actual, covered, predicted)
                            and max(covered, actual) <= support <= n and predicted <= n)):
                raise ValueError(f"{path}: invalid {name}.{role} commitment counts")
        amount = [roles[role] for role in AMOUNT_ROLES]
        actual = sum(r["singletons_on_true_role"] for r in amount)
        predicted = sum(r["predicted_singletons"] for r in amount)
        correct = sum(r["correct_singletons"] for r in amount)
        from_other = row["non_amount_predicted_as_amount"]
        if (any(type(row[key]) is not int for key in
                ("predicted_amount_singletons", "predicted_amount_singletons_wrong", "non_amount_predicted_as_amount"))
                or any(roles[role]["tokens"] == 0 for role in DIRECTIONS)
                or sum(r["tokens"] for r in roles.values()) != n
                or sum(r["tokens"] for r in amount) != count
                or sum(r["predicted_singletons"] for r in roles.values())
                    != sum(r["singletons_on_true_role"] for r in roles.values())
                or row["predicted_amount_singletons"] != predicted
                or row["predicted_amount_singletons_wrong"] != predicted - correct
                or wrong != actual - correct
                or not 0 <= predicted - correct - from_other <= wrong
                or not 0 <= from_other <= n - count
                or abs(row["amount_abstain_rate"] - (count - actual) / count) > 0.000050001):
            raise ValueError(f"{path}: inconsistent {name} commitment counts")
    return metrics


def judge(cand: dict, base: dict) -> list[str]:
    for name in ("test", "shifted"):
        if any(cand[name][k] != base[name][k] for k in ("tokens", "amount_tokens")):
            return [f"{name} split counts differ from baseline; use the same evaluation corpus"]
        if not base[name].get("split_sha256") or cand[name].get("split_sha256") != base[name]["split_sha256"]:
            return [f"{name} split contents differ from baseline; use the same evaluation corpus"]
        if {r: c["tokens"] for r, c in cand[name]["by_role"].items()} != {
            r: c["tokens"] for r, c in base[name]["by_role"].items()
        }:
            return [f"{name} per-role support differs from baseline"]
    fails = []
    if cand["shifted"]["role_coverage"] < MIN_SHIFTED_COVERAGE:
        fails.append(f"shifted coverage {cand['shifted']['role_coverage']:.4f} < {MIN_SHIFTED_COVERAGE}")
    if cand["test"]["amount_role_accuracy"] < base["test"]["amount_role_accuracy"] - MAX_TEST_ACCURACY_DROP:
        fails.append("test amount accuracy dropped more than allowed")
    for name in ("test", "shifted"):
        current, shipped = cand[name], base[name]
        if current["amount_singleton_wrong"] > shipped["amount_singleton_wrong"]:
            fails.append(f"{name} wrong singleton on a true amount increased")
        if (current["predicted_amount_singletons_wrong"] > shipped["predicted_amount_singletons_wrong"]
                or current["non_amount_predicted_as_amount"] > shipped["non_amount_predicted_as_amount"]):
            fails.append(f"{name} false amount commitments increased")
        for role in DIRECTIONS:
            counts = current["by_role"][role]
            minimum = max(math.ceil(MIN_DIRECTION_RECALL * counts["tokens"]),
                          shipped["by_role"][role]["correct_singletons"])
            correct = counts["correct_singletons"]
            if correct < minimum:
                fails.append(f"{name} {role} correct commitments {correct} < {minimum}")
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
    print(f"{'candidate':44} {'test D/C':>10} {'shift D/C':>10} {'false amt T/S':>13}  verdict")

    def row(name: str, metrics: dict, verdict: str) -> None:
        counts = ["/".join(str(metrics[split]["by_role"][role]["correct_singletons"]) for role in DIRECTIONS)
                  for split in ("test", "shifted")]
        false_amounts = "/".join(str(metrics[split]["predicted_amount_singletons_wrong"])
                                 for split in ("test", "shifted"))
        print(f"{name[:44]:44} {counts[0]:>10} {counts[1]:>10} {false_amounts:>13}  {verdict}")

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
