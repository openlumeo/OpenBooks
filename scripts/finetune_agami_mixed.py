"""Fit an experimental RoleNet head on mixed Agami Type 1 and Type 2 PDFs, calibrated on both types."""
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
from finetune_agami_roles import features, score
from openbooks.statements.calibration import Calibrator
from openbooks.statements.roles import RoleModel

TEST_TYPE1 = 8
TRAIN_PER_TYPE = 30
CALIBRATION_PER_TYPE = 12
EPOCHS = 30


def pdfs(kind):
    return sorted((BASE / f"India_Bank_Statement_Digital_{kind}").glob("*.pdf"))


def merge(parts):
    return torch.cat([p[0] for p in parts]), torch.cat([p[1] for p in parts])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    torch.manual_seed(21)
    model = RoleModel.load()
    if model is None:
        parser.error("Shipped model assets are required")
    type1, type2 = pdfs("Type1"), pdfs("Type2")
    held_out = type1[:TEST_TYPE1]
    pool1 = type1[TEST_TYPE1:]
    train_files = pool1[:TRAIN_PER_TYPE] + type2[:TRAIN_PER_TYPE]
    cal_files = pool1[TRAIN_PER_TYPE:TRAIN_PER_TYPE + CALIBRATION_PER_TYPE] + type2[TRAIN_PER_TYPE:TRAIN_PER_TYPE + CALIBRATION_PER_TYPE]
    args.out.mkdir(parents=True, exist_ok=False)
    print(f"Encoding {len(train_files)} train, {len(cal_files)} calibration, {len(held_out)} held-out files", flush=True)
    x, y = merge([features(model, [p]) for p in train_files])
    calibration = merge([features(model, [p]) for p in cal_files])
    test_data = features(model, held_out)
    original_file = features(model, held_out[:1])
    baseline = copy.deepcopy(model.net.role).cpu()
    candidate = copy.deepcopy(baseline)
    optimizer = torch.optim.AdamW(candidate.parameters(), lr=0.002, weight_decay=0.01)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    for epoch in range(EPOCHS):
        for indices in torch.randperm(len(y)).split(256):
            optimizer.zero_grad(set_to_none=True)
            cross_entropy(candidate(x[indices]), y[indices], label_smoothing=0.05).backward()
            optimizer.step()
        schedule.step()
        print(f"Epoch {epoch + 1}/{EPOCHS}", flush=True)
    with torch.no_grad():
        probs = Calibrator().probs(candidate(calibration[0]).numpy())
    scores = 1 - probs[np.arange(len(calibration[1])), calibration[1].numpy()]
    alpha = model.role_cal.alpha
    rank = math.ceil((len(scores) + 1) * (1 - alpha))
    if rank > len(scores):
        parser.error("Calibration set is too small for the shipped alpha")
    calibrator = Calibrator(qhat=float(np.partition(scores, rank - 1)[rank - 1]), alpha=alpha)
    report = {"scope": "Synthetic digital PDFs, mixed Type 1 and Type 2 training and calibration; held-out Type 1 files are excluded from both",
              "counts": {"train_files": len(train_files), "calibration_files": len(cal_files), "test_files": len(held_out), "training_tokens": len(y), "calibration_tokens": len(calibration[1])},
              "calibration": {"alpha": alpha, "qhat": calibrator.qhat},
              "test": {"shipped": score(baseline, model.role_cal, test_data), "candidate": score(candidate, calibrator, test_data)},
              "profile_pdf": {"shipped": score(baseline, model.role_cal, original_file), "candidate": score(candidate, calibrator, original_file)}}
    torch.save(candidate.state_dict(), args.out / "experimental-role-head.pt")
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["test"], indent=2))


if __name__ == "__main__":
    main()
