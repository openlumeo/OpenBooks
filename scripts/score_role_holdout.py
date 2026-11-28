from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from pathlib import Path

from scripts.freeze_role_holdout import asset, build_manifest
from scripts.role_candidates import sha256, verify_bundle

SHIPPED = Path(__file__).resolve().parents[1] / "models"
FIELDS = ("date", "direction", "amount", "balance")


def score_document(doc: dict, truth: dict, identity: dict, pdf_hash: str) -> dict:
    """Score the verified output in statement order, keeping raw rows out of the report."""
    expected = truth["outcome"] == "released"
    reference = truth["transactions"] if expected else []
    matches = dict.fromkeys(FIELDS, 0)
    if doc["status"] == "refused":
        error = doc["error"]
        if error.get("internal") or error["file_sha256"] != pdf_hash:
            raise ValueError("engine fault or unexpected input identity")
        return {"result": "missed_release" if expected else "correct_refusal",
                "reference_rows": len(reference), "field_matches": matches,
                "refusal_code": error["code"]}
    if (doc["status"] != "ok" or doc["file"].get("model") != identity
            or doc["file"]["sha256"] != pdf_hash):
        raise ValueError("unexpected release, model or input identity")

    rows = doc["data"]["transactions"]
    exact = expected and len(rows) == len(reference)
    for row, wanted in zip(rows, reference):
        for field, actual in zip(FIELDS, (row["date"], row["direction"],
                                         Decimal(row["amount"]["amount"]),
                                         Decimal(row["balance_after"]["amount"]))):
            value = Decimal(wanted[field]) if field in ("amount", "balance") else wanted[field]
            matches[field] += actual == value
            exact = exact and actual == value
    return {"result": "correct_release" if exact else "false_release",
            "reference_rows": len(reference), "field_matches": matches}


def model_identity(folder: Path) -> dict[str, str]:
    return {"weights_sha256": sha256(folder / "roles_head.pt"),
            "calibration_sha256": sha256(folder / "roles_calibration.json")}


def score_bundle(folder: Path, root: Path, holdout: dict, identity: dict, threads: int) -> dict:
    os.environ["OPENBOOKS_MODELS_DIR"] = str(folder)
    import torch

    from openbooks.pipeline import Params, process
    from openbooks.statements.assets import ModelUnavailable
    from openbooks.statements.roles import RoleModel

    torch.set_num_threads(threads)
    try:
        model = RoleModel.load()
    except ModelUnavailable as exc:
        raise ValueError("cannot load the selected model bundle") from exc
    if model is None or model.identity != identity:
        raise ValueError("the selected model does not match the recorded bundle")
    scores = {}
    for doc_id, entry in holdout.items():
        pdf = asset(root, entry["pdf"], ".pdf")
        truth_bytes = asset(root, entry["truth"], ".json").read_bytes()
        if hashlib.sha256(truth_bytes).hexdigest() != entry["truth_sha256"]:
            raise ValueError(f"truth changed for {doc_id}")
        truth = json.loads(truth_bytes)
        try:
            doc = process(pdf, Params(currency=entry.get("currency"), model=True), strict=True)
            scores[doc_id] = score_document(doc, truth, identity, entry["pdf_sha256"])
        except Exception as exc:
            raise ValueError(f"evaluation failed for {doc_id} ({type(exc).__name__})") from exc
    return scores


def summarize(holdout: dict, scores: dict) -> dict:
    groups = {entry["source_document"].strip().casefold() for entry in holdout.values()}
    false_groups = {holdout[key]["source_document"].strip().casefold()
                    for key, score in scores.items() if score["result"] == "false_release"}
    counts = {result: sum(score["result"] == result for score in scores.values())
              for result in ("correct_release", "correct_refusal", "missed_release", "false_release")}
    return {
        **counts,
        "reference_rows": sum(score["reference_rows"] for score in scores.values()),
        "field_matches": {field: sum(score["field_matches"][field] for score in scores.values())
                          for field in FIELDS},
        "source_groups": len(groups),
        "source_groups_with_false_release": len(false_groups),
        "zero_event_upper_95_if_groups_independent": (
            1 - 0.05 ** (1 / len(groups)) if groups and not false_groups else None
        ),
    }


def compare(shipped: dict, candidate: dict) -> list[str]:
    failures = []
    if any(score["result"] == "false_release" for score in candidate.values()):
        failures.append("candidate made a false release")
    if not any(score["result"] == "correct_release" for score in candidate.values()):
        failures.append("candidate made no correct releases")
    if any(score["result"] == "correct_release" and candidate[key]["result"] != "correct_release"
           for key, score in shipped.items()):
        failures.append("candidate lost a correct shipped release")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roster", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--threads", type=int, default=4, help="PyTorch CPU thread count")
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")

    try:
        frozen = args.manifest.read_bytes()
        manifest = json.loads(frozen)
        if build_manifest(args.roster) != manifest:
            raise ValueError("roster, PDF or truth differs from the frozen manifest")
        holdout = {key: entry for key, entry in manifest["documents"].items()
                   if entry["split"] == "holdout"}
        root = args.roster.resolve().parent
        outcomes = {json.loads(asset(root, entry["truth"], ".json").read_bytes())["outcome"]
                    for entry in holdout.values()}
        if outcomes != {"released", "refused"}:
            raise ValueError("holdout must cover both expected releases and expected refusals")

        candidate = args.candidate.resolve()
        bundles = {"shipped": SHIPPED, "candidate": candidate}
        artifact_hashes = verify_bundle(candidate)
        identities = {label: model_identity(folder) for label, folder in bundles.items()}
        if identities["candidate"] != {
            "weights_sha256": artifact_hashes["roles_head.pt"],
            "calibration_sha256": artifact_hashes["roles_calibration.json"],
        }:
            raise ValueError("candidate model artifacts changed after bundle verification")
        scores = {}
        with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
            for label, folder in bundles.items():
                scores[label] = pool.submit(score_bundle, folder, root, holdout,
                                            identities[label], args.threads).result()
        if (args.manifest.read_bytes() != frozen or build_manifest(args.roster) != manifest
                or verify_bundle(candidate) != artifact_hashes
                or any(model_identity(folder) != identities[label] for label, folder in bundles.items())):
            raise ValueError("holdout or model artifacts changed during evaluation")
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    failures = compare(scores["shipped"], scores["candidate"])
    report = {
        "holdout_gate": "reject" if failures else "pass",
        "failures": failures,
        "manifest_sha256": hashlib.sha256(frozen).hexdigest(),
        "candidate_artifacts_sha256": artifact_hashes,
        "threads": args.threads,
        "models": {label: {"identity": identities[label], **summarize(holdout, result)}
                   for label, result in scores.items()},
        "documents": {key: {label: result[key] for label, result in scores.items()} for key in holdout},
    }
    print(json.dumps(report, indent=2, allow_nan=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
