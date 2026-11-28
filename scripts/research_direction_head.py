"""Train and compare a proof-gated direction head on fresh synthetic statement layouts."""
from __future__ import annotations

import argparse
import random
import re
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np
import torch
from torch import nn

import train_roles as tr
from openbooks.pipeline import Params, Refusal, to_dec
from openbooks.statements import pdf_front as pdf
from openbooks.statements.roles import Pred, Predictions, RoleModel, vtype_of
from openbooks_lab.calibration_fit import fit_temperature
from openbooks_lab.golden_docs import _pdf_rows
from openbooks_lab.synth import label_words, random_layout, render
from promote import judge
from role_candidates import sha256, split_sha256, write_json

DIRECTIONS = ("debit", "credit", "balance")
ROLE_IDS = [tr.RID[role] for role in DIRECTIONS]
SPLITS = {"train": (220_000, 96), "calib": (230_000, 24),
          "test": (240_000, 36), "shifted": (250_000, 48), "tampered": (260_000, 12)}
MIN_PROBABILITY = 0.90


def amount(word):
    return to_dec(word.text, "printed amount", dr_cr=True)


def document_features(pages, probabilities):
    """Use only printed tokens and their boxes. Return local evidence and verified direction candidates."""
    words = [word for page in pages for word in page]
    indices = {word: i for i, word in enumerate(words)}
    all_lines = [pdf._lines(page) for page in pages]
    flat = [line for lines in all_lines for line in lines]
    rows = []
    try:
        opening = {record[0] for record in pdf._stated(flat, r"opening\s+balance")}
        closing = {record[0] for record in pdf._stated(flat, r"closing\s+balance")}
        if len(opening) != 1 or len(closing) != 1:
            return {}, {}
        order, _ = pdf._date_order(all_lines, Params())
        for lines in all_lines:
            header = pdf.find_header(lines)
            for _, text, dates, money in pdf._statement_lines(lines[header[0] + 1:] if header else lines, order):
                if dates and money:
                    rows.append(money)
                elif money and not re.match(r"\s*(total|brought forward|carried forward|b/f|c/f)\b", text, re.I):
                    return {}, {}
        if not rows or any(len(row) > 2 for row in rows):
            return {}, {}
        values = [[amount(word) for word in row] for row in rows]
    except Refusal:
        return {}, {}

    first = next(iter(opening))
    previous = {first}
    features = {}
    for row, vals in zip(rows, values):
        if len(row) == 2:
            for position, word in enumerate(row):
                if word not in indices or vtype_of(word.text) != "money":
                    continue
                idx = indices[word]
                current, other = vals[position], vals[1-position]
                features[idx] = [
                    *probabilities[idx], word.cx / word.pw, position,
                    abs(word.cx - row[1-position].cx) / word.pw,
                    any(p - abs(current) == other for p in previous),
                    any(p + abs(current) == other for p in previous),
                    any(p + abs(other) == current or p - abs(other) == current for p in previous),
                ]
        previous = set(vals)

    wide = Pred("balance", DIRECTIONS, "money", ("money",))
    proposals = Predictions({word: wide for row in rows for word in row})
    try:
        chain = proposals.resolve_chain(rows, first, next(iter(closing)), amount)
    except Refusal:
        return features, {}
    proved = {indices[word]: tr.RID[role] for row in chain for word, role in row.items()
              if word in indices and indices[word] in features and role in DIRECTIONS[:2]}
    return features, proved


@dataclass
class Example:
    pdf_sha256: str
    windows: list[dict]
    role: np.ndarray
    types: np.ndarray
    labels: np.ndarray
    type_labels: np.ndarray
    features: dict
    proved: dict


def corpus(name, model, scratch):
    seed_start, count = SPLITS[name]
    examples = []
    for seed in range(seed_start, seed_start + count):
        rng = random.Random(seed)
        rows = _pdf_rows(rng, 12)
        layout = random_layout(rng, shifted=name in ("shifted", "tampered"), rich=True)
        layout.has_header = seed % 5 != 0
        closing = Decimal(rows[-1][4]) + (Decimal("0.01") if name == "tampered" else 0)
        path = scratch / f"{seed}.pdf"
        raw, cells = render(rows, "1000.00", layout, rng, closing=str(closing))
        path.write_bytes(raw)
        pages, _ = pdf.read_words(path, Params(ocr=False))
        words = [word for page in pages for word in page]
        role, types = model.logits(words)
        features, proved = document_features(pages, model.role_cal.probs(role))
        labels = [tr.RID[r] for page in pages for r in label_words(page, cells)]
        type_labels = [tr.TID[vtype_of(word.text)] for word in words]
        examples.append(Example(sha256(path), tr.items_of(pages, cells), role, types,
                                np.asarray(labels), np.asarray(type_labels), features, proved))
    print(f"{name}: {count} layouts, {sum(len(x.proved) for x in examples)} arithmetic proposals", flush=True)
    return examples


def training_data(examples):
    pairs = [(features, ROLE_IDS.index(ex.labels[i])) for ex in examples
             for i, features in ex.features.items() if ex.labels[i] in ROLE_IDS]
    x, y = zip(*pairs)
    return torch.tensor(x, dtype=torch.float32), torch.tensor(y)


def fit_head(train, calib):
    x, y = training_data(train)
    x_cal, y_cal = training_data(calib)
    torch.manual_seed(1)
    head = nn.Sequential(nn.Linear(x.shape[1], 16), nn.GELU(), nn.Linear(16, len(ROLE_IDS)))
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.02)
    for _ in range(100):
        optimizer.zero_grad()
        nn.functional.cross_entropy(head(x), y).backward()
        optimizer.step()
    with torch.no_grad():
        temperature = fit_temperature(head(x_cal).numpy().astype(np.float64), y_cal.numpy())
    return head.eval(), temperature, len(x), len(x_cal)


class VerifiedRoles:
    def __init__(self, base, commitments):
        self.base, self.commitments = base, commitments

    def probs(self, logits):
        probabilities = self.base.probs(logits)
        for index, direction in self.commitments.items():
            probabilities[index] = 0
            probabilities[index, direction] = 1
        return probabilities

    def sets(self, logits):
        sets = self.base.sets(logits)
        for index, direction in self.commitments.items():
            if direction in sets[index]:
                sets[index] = [direction]
        return sets


@torch.no_grad()
def evaluate(examples, model, head, temperature, mode):
    commitments = {}
    offset = 0
    for ex in examples:
        supported = model.role_cal.sets(ex.role)
        if mode != "base" and ex.proved:
            indices = list(ex.proved)
            scores = (head(torch.tensor([ex.features[i] for i in indices], dtype=torch.float32))
                      / temperature).softmax(dim=1)
            for index, prediction in zip(indices, scores):
                role = ex.proved[index]
                if role in supported[index] and (mode == "proof" or (
                        ROLE_IDS[int(prediction.argmax())] == role and prediction.max() >= MIN_PROBABILITY)):
                    commitments[offset + index] = role
        offset += len(ex.role)
    arrays = [np.concatenate([getattr(ex, name) for ex in examples])
              for name in ("role", "types", "labels", "type_labels")]
    result = tr.report(*arrays, VerifiedRoles(model.role_cal, commitments), model.type_cal)
    result["split_sha256"] = split_sha256([w for ex in examples for w in ex.windows])
    return result, len(commitments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    model = RoleModel.load(tr.ROOT / "models/roles_head.pt", tr.ROOT / "models/roles_calibration.json")
    with tempfile.TemporaryDirectory(prefix="openbooks-direction-") as temp:
        origin = Path(temp)
        train, calib = (corpus(name, model, origin) for name in ("train", "calib"))
        head, temperature, n_train, n_calib = fit_head(train, calib)
        weights = args.out / "direction_head.pt"
        torch.save({"state": head.state_dict(), "temperature": temperature,
                    "minimum_probability": MIN_PROBABILITY, "role_labels": DIRECTIONS}, weights)
        documents = {name: corpus(name, model, origin) for name in ("test", "shifted", "tampered")}

    audit = {}
    for mode in ("base", "proof", "learned"):
        scores, counts = {}, {}
        for name, examples in documents.items():
            scores[name], counts[name] = evaluate(examples, model, head, temperature, mode)
        audit[mode] = {"metrics": scores, "proof_commitments": counts}
    for mode in ("proof", "learned"):
        metrics = audit[mode]["metrics"]
        failures = judge(metrics, audit["base"]["metrics"])
        if any(metrics[name]["predicted_amount_singletons_wrong"] for name in ("test", "shifted")):
            failures.append("fresh split contains a wrong amount commitment")
        if audit[mode]["proof_commitments"]["tampered"]:
            failures.append("proof accepted a document with a tampered closing balance")
        audit[mode]["gate"] = "reject" if failures else "pass"
        audit[mode]["failures"] = failures
    write_json(args.out / "report.json", {
        "source": "Fresh synthetic PDFs generated from fixed disjoint layout seeds",
        "splits": SPLITS, "pdf_sha256": {name: [ex.pdf_sha256 for ex in examples]
                                        for name, examples in {"train": train, "calib": calib, **documents}.items()},
        "base_model": model.identity, "head_sha256": sha256(weights), "script_sha256": sha256(Path(__file__)),
        "temperature": temperature, "minimum_probability": MIN_PROBABILITY,
        "training_tokens": n_train, "calibration_tokens": n_calib, "results": audit,
    })
    for mode, result in audit.items():
        print(mode, result.get("gate", "baseline"), result.get("failures", []))
        for split, metrics in result["metrics"].items():
            print(split, "coverage", metrics["role_coverage"], "false", metrics["predicted_amount_singletons_wrong"],
                  "debit/credit", *(metrics["by_role"][r]["correct_singletons"] for r in DIRECTIONS[:2]),
                  "proof commitments", result["proof_commitments"][split])
    return int(audit["learned"]["gate"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
