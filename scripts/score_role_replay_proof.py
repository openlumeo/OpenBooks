"""Compare raw and proof-assisted RoleNet scores on the same replayable evaluation evidence."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

import train_roles as tr
from openbooks.statements.roles import RoleModel, vtype_of
from promote import judge
from research_direction_head import VerifiedRoles, document_features
from role_candidates import write_json
from role_replay_cache import EVIDENCE, Word, verify

SPLITS = ("test", "shifted")


def score_bundle(cache: Path, directory: Path, fingerprints: dict) -> dict:
    model = RoleModel.load(directory / "roles_head.pt", directory / "roles_calibration.json")
    if model is None:
        raise ValueError(f"missing model assets: {directory}")
    arrays = {name: [] for name in SPLITS}
    choices = {name: {} for name in SPLITS}
    offsets = dict.fromkeys(SPLITS, 0)
    by_method = {name: {} for name in SPLITS}
    with gzip.open(cache / EVIDENCE, "rt", encoding="utf-8") as stream:
        for line in stream:
            doc = json.loads(line)
            split = doc["split"]
            if split not in SPLITS:
                continue
            pages = [[Word(**word) for word in page] for page in doc["pages"]]
            words = [word for page in pages for word in page]
            role, types = model.logits(words)
            labels = np.asarray([tr.RID[label] for page in pages for label in tr.label_words(page, doc["cells"])])
            type_labels = np.asarray([tr.TID[vtype_of(word.text)] for word in words])
            arrays[split].append((role, types, labels, type_labels))

            _, proved = document_features(pages, model.role_cal.probs(role))
            allowed = model.role_cal.sets(role)
            commitments = {i: direction for i, direction in proved.items() if direction in allowed[i]}
            counts = by_method[split].setdefault(doc["method"], {"documents": 0, "proof_commitments": 0, "wrong": 0})
            counts["documents"] += 1
            counts["proof_commitments"] += len(commitments)
            counts["wrong"] += sum(int(labels[i] != direction) for i, direction in commitments.items())
            choices[split].update({offsets[split] + i: role for i, role in commitments.items()})
            offsets[split] += len(words)
    scores = {"raw": {}, "proof": {}}
    for split in SPLITS:
        inputs = [np.concatenate(parts) for parts in zip(*arrays[split])]
        for mode, calibration in (
                ("raw", model.role_cal), ("proof", VerifiedRoles(model.role_cal, choices[split]))):
            scores[mode][split] = tr.report(*inputs, calibration, model.type_cal)
            scores[mode][split]["split_sha256"] = fingerprints[split]
    return {"identity": model.identity, **scores, "by_method": by_method}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tr.torch.set_num_threads(4)
    verified = verify(args.cache)
    models = {name: score_bundle(args.cache, directory, verified["split_sha256"])
              for name, directory in (("shipped", tr.ROOT / "models"), ("candidate", args.candidate))}
    baseline = models["shipped"]["raw"]
    checks = {name: {mode: judge(result[mode], baseline) for mode in ("raw", "proof")}
              for name, result in models.items()}
    write_json(args.out, {"manifest_sha256": verified["manifest_sha256"], "models": models, "failures": checks})
    for name, result in models.items():
        shifted = result["proof"]["shifted"]
        print(f"{name}: shifted proof commitments "
              f"{shifted['by_role']['debit']['correct_singletons']} debit / "
              f"{shifted['by_role']['credit']['correct_singletons']} credit; "
              f"{shifted['predicted_amount_singletons_wrong']} wrong amount")
        print(f"{name} proof gate: {checks[name]['proof'] or 'PASS'}")


if __name__ == "__main__":
    main()
