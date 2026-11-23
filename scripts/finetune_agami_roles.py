"""Fit an experimental RoleNet head on Agami Type 2 and score it on held-out Type 1 PDFs."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch.nn.functional import cross_entropy

from eval_agami import BASE
from export_agami_roles import export_document
from openbooks.core.params import Params
from openbooks.statements.calibration import Calibrator
from openbooks.statements.encoder import tensors, windows
from openbooks.statements.labels import ROLES
from openbooks.statements.pdf_front import read_words
from openbooks.statements.roles import RoleModel


@torch.no_grad()
def features(model, files):
    activations, labels = [], []
    for path in files:
        truth, _ = export_document(path)
        if not truth:
            raise ValueError(f"Unaligned reference document: {path}")
        pages, _ = read_words(path, Params(ocr=False))
        words = [word for page in pages for word in page]
        annotated = [word for page in truth for word in page["tokens"]]
        if any(w.text != t["text"] for w, t in zip(words, annotated, strict=True)):
            raise ValueError(f"Token positions differ from labels: {path}")
        for group in windows(words):
            matches = [(i, ROLES.index(annotated[k]["role"])) for i, k in enumerate(group) if annotated[k]["role"]]
            if matches:
                indices, roles = zip(*matches)
                hidden = model.net.enc(*tensors(words, group, model.dev))[0]
                activations.append(hidden[list(indices)].cpu())
                labels.extend(roles)
    return torch.cat(activations), torch.tensor(labels)


def score(head, calibrator, data):
    x, y = data
    with torch.no_grad():
        logits = head(x).numpy()
    labels = y.tolist()
    sets = calibrator.sets(logits)
    return {"tokens": len(labels), "top1_accuracy": float((logits.argmax(axis=1) == y.numpy()).mean()),
            "coverage": sum(label in group for label, group in zip(labels, sets)) / len(labels),
            "abstention": sum(len(group) != 1 for group in sets) / len(labels),
            "wrong_singletons": sum(len(group) == 1 and group[0] != label for label, group in zip(labels, sets))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New directory for the experimental results")
    args = parser.parse_args()
    torch.set_num_threads(4)
    torch.manual_seed(21)
    model = RoleModel.load()
    if model is None:
        parser.error("Shipped model assets are required")
    train = sorted((BASE / "India_Bank_Statement_Digital_Type2").glob("*.pdf"))
    test = sorted((BASE / "India_Bank_Statement_Digital_Type1").glob("*.pdf"))
    if len(train) < 17 or len(test) < 8:
        parser.error("Pilot requires 17 Type 2 PDFs and 8 Type 1 PDFs")
    args.out.mkdir(parents=True, exist_ok=False)
    print("Encoding 12 training, 5 calibration, and 8 held-out files", flush=True)
    x, y = features(model, train[:12])
    calibration = features(model, train[12:17])
    test_data = features(model, test[:8])
    original_file = features(model, test[:1])
    baseline = copy.deepcopy(model.net.role).cpu()
    candidate = copy.deepcopy(baseline)
    optimizer = torch.optim.AdamW(candidate.parameters(), lr=0.003)
    for iteration in range(8):
        for indices in torch.randperm(len(y)).split(256):
            optimizer.zero_grad(set_to_none=True)
            cross_entropy(candidate(x[indices]), y[indices]).backward()
            optimizer.step()
        print(f"Head-training epoch {iteration + 1}/8", flush=True)
    with torch.no_grad():
        calibration_probs = Calibrator().probs(candidate(calibration[0]).numpy())
    scores = 1 - calibration_probs[np.arange(len(calibration[1])), calibration[1].numpy()]
    alpha = model.role_cal.alpha
    rank = math.ceil((len(scores) + 1) * (1 - alpha))
    if rank > len(scores):
        parser.error("Calibration set is too small for the shipped alpha")
    calibrator = Calibrator(qhat=float(np.partition(scores, rank - 1)[rank - 1]), alpha=alpha)
    report = {"scope": "Synthetic digital PDFs; parser-aligned critical tokens only; challenger is not promotion-ready",
              "counts": {"train_files": 12, "calibration_files": 5, "test_files": 8, "training_tokens": len(y)},
              "calibration": {"alpha": alpha, "qhat": calibrator.qhat},
              "test": {"shipped": score(baseline, model.role_cal, test_data), "candidate": score(candidate, calibrator, test_data)},
              "profile_pdf": {"shipped": score(baseline, model.role_cal, original_file),
                              "candidate": score(candidate, calibrator, original_file)}}
    torch.save(candidate.state_dict(), args.out / "experimental-role-head.pt")
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
