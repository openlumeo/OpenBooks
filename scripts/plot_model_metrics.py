"""Model accuracy graph and confusion matrices for the shipped typed heads (column role), on synthetic splits.

Scores models/roles_head.pt with models/roles_calibration.json on the cached splits (data/roles_dataset_*.pkl, rebuilt by
scripts/train_roles.py) and writes docs/figures/model_accuracy.png, docs/figures/confusion_role.png and
docs/evidence/model_confusion.json. The confusion matrix has an extra "abstain" column: a token whose conformal set is not
exactly one role, which the pipeline treats as "not sure". Usage: python scripts/plot_model_metrics.py
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import train_roles as tr  # noqa: E402
from openbooks.statements.calibration import Calibrator  # noqa: E402
from openbooks.statements.encoder import RoleNet, dequantize_state  # noqa: E402

SPLITS = ("test", "shifted", "family_sign", "family_branch", "family_skew")
TITLES = {"test": "test", "shifted": "shifted (unseen fonts, headers, dates)", "family_sign": "family: sign column",
          "family_branch": "family: branch print", "family_skew": "family: date skew"}
CONFUSION_SPLITS = ("test", "shifted")


def load_model(dev: torch.device) -> tuple[RoleNet, Calibrator]:
    net = RoleNet(len(tr.ROLES), len(tr.VTYPES))
    blob = torch.load(ROOT / "models" / "roles_head.pt", map_location="cpu", weights_only=False)
    net.load_state_dict(dequantize_state(blob["int8_state"]))
    cal = json.loads((ROOT / "models" / "roles_calibration.json").read_text(encoding="utf-8"))["role"]
    qhat = float("inf") if cal["qhat"] is None else cal["qhat"]
    return net.to(dev).eval(), Calibrator(cal["temperature"], qhat, cal["alpha"])


def confusion(logits: np.ndarray, y: np.ndarray, cal: Calibrator) -> np.ndarray:
    """Rows: true role. Columns: predicted role (singleton conformal set) plus a final 'abstain' column."""
    n = len(tr.ROLES)
    out = np.zeros((n, n + 1), dtype=np.int64)
    for true, s in zip(y, cal.sets(logits)):
        out[true, s[0] if len(s) == 1 else n] += 1
    return out


def main() -> None:
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net, cal = load_model(dev)
    base = pickle.loads((ROOT / "data" / "roles_dataset_1200_150.pkl").read_bytes())
    fam = pickle.loads((ROOT / "data" / "roles_dataset_fam_1200_150.pkl").read_bytes())
    items = {"test": base["test"], "shifted": base["shifted"], **{f"family_{f}": fam[f]["test"] for f in fam}}
    stats, matrices = {}, {}
    for name in SPLITS:
        lg = tr.logits_of(net, items[name], dev)
        money = np.array([tr.ROLES[y] in tr.AMOUNT for y in lg[2]])
        sets = cal.sets(lg[0])
        single = np.array([len(s) == 1 for s in sets])
        correct = np.array([len(s) == 1 and s[0] == y for y, s in zip(lg[2], sets)])
        stats[name] = {
            "role accuracy": float((cal.probs(lg[0]).argmax(1) == lg[2]).mean()),
            "amount-role accuracy": float((cal.probs(lg[0]).argmax(1)[money] == lg[2][money]).mean()),
            "set coverage": float(np.mean([y in s for y, s in zip(lg[2], sets)])),
            "amount abstain rate": float((~single[money]).mean()),
            "confident-wrong amounts": int((single[money] & ~correct[money]).sum()),
            "amount tokens": int(money.sum()),
        }
        if name in CONFUSION_SPLITS:
            matrices[name] = confusion(lg[0], lg[2], cal)
    figures = ROOT / "docs" / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.6))
    x, w = np.arange(len(SPLITS)), 0.26
    for k, (key, color) in enumerate((("role accuracy", "#4c78a8"), ("amount-role accuracy", "#f58518"), ("set coverage", "#54a24b"))):
        bars = a.bar(x + (k - 1) * w, [stats[s][key] for s in SPLITS], w, label=key, color=color)
        a.bar_label(bars, fmt="%.2f", fontsize=7, padding=1)
    a.set_xticks(x, [s.replace("family_", "fam: ") for s in SPLITS], fontsize=8)
    a.set_ylim(0.5, 1.14)
    a.set_title("Accuracy and coverage by split")
    a.legend(fontsize=8, loc="upper center", ncol=3)
    bars = b.bar(x, [stats[s]["amount abstain rate"] for s in SPLITS], 0.5, color="#b279a2")
    b.bar_label(bars, labels=[f"{stats[s]['amount abstain rate']:.0%}\n{stats[s]['confident-wrong amounts']} wrong" for s in SPLITS],
                fontsize=8, padding=2)
    b.set_xticks(x, [s.replace("family_", "fam: ") for s in SPLITS], fontsize=8)
    b.set_ylim(0, 1.0)
    b.set_title("Amount tokens the heads decline to decide (abstain)\nlabel: abstain rate and confident-wrong tokens")
    fig.suptitle("Shipped typed heads, synthetic data (calibration alpha 0.001)", fontsize=10)
    fig.tight_layout()
    fig.savefig(figures / "model_accuracy.png", dpi=150)
    plt.close(fig)

    labels = list(tr.ROLES) + ["abstain"]
    fig, axes = plt.subplots(1, len(matrices), figsize=(6.4 * len(matrices), 5.4))
    for ax, (name, m) in zip(np.atleast_1d(axes), matrices.items()):
        norm = m / np.maximum(m.sum(1, keepdims=True), 1)
        ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                if m[i, j]:
                    ax.text(j, i, f"{norm[i, j]:.0%}\n{m[i, j]:,}", ha="center", va="center", fontsize=6.5,
                            color="white" if norm[i, j] > 0.55 else "black")
        ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right", fontsize=8)
        ax.set_yticks(range(len(tr.ROLES)), tr.ROLES, fontsize=8)
        ax.set_xlabel("predicted (singleton conformal set, else abstain)")
        ax.set_ylabel("true column role")
        ax.set_title(f"{TITLES[name]}: {int(m.sum()):,} tokens", fontsize=9)
    fig.suptitle("Role confusion matrix (row-normalised; cells show % and token count)", fontsize=10)
    fig.tight_layout()
    fig.savefig(figures / "confusion_role.png", dpi=150)
    plt.close(fig)

    (ROOT / "docs" / "evidence" / "model_confusion.json").write_text(json.dumps(
        {"labels": labels, "stats": stats, "counts": {k: v.tolist() for k, v in matrices.items()},
         "note": "shipped heads + shipped calibration, synthetic splits; rows true role, columns predicted role or abstain"},
        indent=2), encoding="utf-8")
    for name, s in stats.items():
        print(f"{name:14} role acc {s['role accuracy']:.4f}  amount acc {s['amount-role accuracy']:.4f}  cov {s['set coverage']:.4f}  "
              f"abstain {s['amount abstain rate']:.3f}  wrong {s['confident-wrong amounts']}/{s['amount tokens']}")


if __name__ == "__main__":
    main()
