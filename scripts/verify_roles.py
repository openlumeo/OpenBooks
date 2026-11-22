"""Check a candidate bundle, compare token metrics, and run the synthetic release gate."""
import argparse
import os
from pathlib import Path

from promote import BASELINE, judge, load
from role_candidates import sha256, verify_bundle, write_json


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("candidate", type=Path)
    cli.add_argument("--baseline", type=Path, default=BASELINE)
    cli.add_argument("--scans", action="store_true", help="Include OCR cases in the file-level check")
    cli.add_argument("--threads", type=int, default=4, help="PyTorch CPU thread count")
    args = cli.parse_args()
    if args.threads < 1:
        cli.error("--threads must be positive")
    folder = args.candidate.resolve()
    try:
        hashes = verify_bundle(folder)
        candidate = load(folder / "roles_metrics.json")
        baseline = load(args.baseline)
        failures = judge(candidate, baseline)
        baseline_hash = sha256(args.baseline)
    except (OSError, KeyError, TypeError, ValueError) as e:
        cli.error(str(e))

    os.environ["OPENBOOKS_MODELS_DIR"] = str(folder)
    import torch

    from e2e_synthetic import main as evaluate, passed
    from openbooks.statements.roles import RoleModel
    from openbooks.statements.assets import ModelUnavailable

    torch.set_num_threads(args.threads)
    try:
        model = RoleModel.load(folder / "roles_head.pt", folder / "roles_calibration.json")
    except ModelUnavailable as e:
        cli.error(e.message)
    if model is None:
        cli.error("Candidate model artifacts are missing")
    result = evaluate(args.scans, True, folder / "file_evaluation.json", model.identity)
    report = {"status": "pass" if not failures and passed(result) else "reject",
              "candidate_sha256": hashes, "model": model.identity, "metric_failures": failures,
              "baseline_sha256": baseline_hash,
              "split_comparison": "contents and counts" if all(baseline[n].get("split_sha256") for n in ("test", "shifted")) else "counts only (legacy baseline)",
              "file_gate_passed": passed(result), "file_evaluation": "file_evaluation.json"}
    write_json(folder / "verification.json", report)
    print(f"{report['status'].upper()}: {folder / 'verification.json'}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
