from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import train_roles as tr  # noqa: E402
from openbooks.calibration import Calibrator  # noqa: E402
from openbooks.encoder import RoleNet, dequantize_state  # noqa: E402


def main(tag: str, alpha: float) -> None:
    trained = tuple(f for f in tag.split("+") if f != "none")
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    blob = torch.load(ROOT / "models" / f"fam_{tag}" / "roles_head.pt", map_location="cpu", weights_only=False)
    net = RoleNet(len(tr.ROLES), len(tr.VTYPES))
    net.load_state_dict(dequantize_state(blob["int8_state"]))
    net.to(dev).eval()
    splits = pickle.loads((ROOT / "data" / "roles_dataset_1200_150.pkl").read_bytes())
    wide = pickle.loads((ROOT / "data" / "roles_dataset_wide_1200_150.pkl").read_bytes())
    fam = pickle.loads((ROOT / "data" / "roles_dataset_fam_1200_150.pkl").read_bytes())
    calib_sets = [splits["calib"], wide["train"], wide["calib"]] + [fam[f]["calib"] for f in trained]
    lg = [tr.logits_of(net, s, dev) for s in calib_sets]
    cat = lambda i: np.concatenate([x[i] for x in lg])  # noqa: E731
    cal_r, cal_t = Calibrator.fit(cat(0), cat(2), alpha), Calibrator.fit(cat(1), cat(3), alpha)
    to_json = lambda c: {"temperature": c.temperature, "qhat": None if np.isinf(c.qhat) else c.qhat, "alpha": c.alpha}  # noqa: E731
    (ROOT / "models" / f"fam_{tag}" / f"roles_calibration_shift_{alpha}.json").write_text(
        json.dumps({"role": to_json(cal_r), "vtype": to_json(cal_t)}), encoding="utf-8")
    res = {"calibration": {"role_temperature": round(cal_r.temperature, 3), "role_qhat": cal_r.qhat, "alpha": alpha,
                           "fit_on": ["calib", "wide_train", "wide_calib"] + [f"family_{f}_calib" for f in trained]}}
    targets = {"test": splits["test"], "shifted": splits["shifted"], **{f"family_{f}": fam[f]["test"] for f in fam}}
    for name, items in targets.items():
        x = tr.logits_of(net, items, dev)
        res[name] = {**tr.report(x[0], x[1], x[2], x[3], cal_r, cal_t), **({"trained_on": name[7:] in trained} if name.startswith("family_") else {})}
    out = ROOT / "docs" / "evidence" / f"roles_metrics_fam_{tag}_shiftcal_a{alpha}.json"
    out.write_text(json.dumps({"int8_shipped": res, "note": f"candidate models/fam_{tag}, shift-aware calibration, SYNTHETIC"}, indent=2), encoding="utf-8")
    for k in ("test", "shifted", *[f"family_{f}" for f in fam]):
        m = res[k]
        print(f"{k:14} cov {m['role_coverage']:.4f} acc {m['amount_role_accuracy']:.4f} wrong {m['amount_singleton_wrong']:4d} abst {m['amount_abstain_rate']:.3f}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.003)
