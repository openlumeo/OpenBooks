import json
import pickle
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import numpy as np
import torch

ROOT = Path("C:/Desktop/openbooks")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import train_roles as tr  # noqa: E402
from openbooks import roles  # noqa: E402
from openbooks.calibration import Calibrator  # noqa: E402
from openbooks.encoder import RoleNet, dequantize_state  # noqa: E402
from openbooks.golden import build  # noqa: E402
from openbooks.pipeline import Params, process  # noqa: E402

SCANS = "--scans" in sys.argv
OUT = Path("C:/tmp/ob/filelevel")
OUT.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(10)

print("loading model + datasets", flush=True)
blob = torch.load("C:/tmp/ob/base_final/roles_head.pt", map_location="cpu", weights_only=False)
net = RoleNet(len(tr.ROLES), len(tr.VTYPES))
net.load_state_dict(dequantize_state(blob["int8_state"]))
net.eval()
splits = pickle.loads((ROOT / "data" / "roles_dataset_1200_150.pkl").read_bytes())
wide = pickle.loads((ROOT / "data" / "roles_dataset_wide_1200_150.pkl").read_bytes())
sets = {"calib": splits["calib"], "wide_a": wide["train"], "wide_b": wide["calib"]}
lg = {k: tr.logits_of(net, v, torch.device("cpu")) for k, v in sets.items()}
print("logits ready", flush=True)


def fit(names, alpha):
    cat = lambda i: np.concatenate([lg[n][i] for n in names])  # noqa: E731
    cr, ct = Calibrator.fit(cat(0), cat(2), alpha), Calibrator.fit(cat(1), cat(3), alpha)
    row = lambda c: {"temperature": c.temperature, "qhat": c.qhat, "alpha": alpha}  # noqa: E731
    return {"role": row(cr), "vtype": row(ct)}


CONFIGS = {
    "shipped_calib_a0.01": json.loads((ROOT / "models" / "roles_calibration.json").read_text()),
    "calib_a0.001": fit(["calib"], 0.001),
    "calib+wide_a0.01": fit(["calib", "wide_a", "wide_b"], 0.01),
    "calib+wide_a0.003": fit(["calib", "wide_a", "wide_b"], 0.003),
}
for name, cfg in CONFIGS.items():
    (OUT / f"{name}.json").write_text(json.dumps(cfg), encoding="utf-8")

tmp = Path(tempfile.mkdtemp(prefix="ob_fl_"))
build(tmp, 7, 0, SCANS)
files = []
for d in sorted(p for p in tmp.iterdir() if p.is_dir()):
    exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
    src = next(f for f in d.iterdir() if f.name != "expected.json")
    if src.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg"):
        files.append((d.name, src, exp))
print(f"{len(files)} pdf/scan cases", flush=True)

orig = roles.RoleModel.load.__func__
summary = {}
for name in CONFIGS:
    cal = OUT / f"{name}.json"
    roles.RoleModel.load = classmethod(lambda cls, weights=roles.WEIGHTS, calibration=cal: orig(cls, weights, calibration))
    rel = wrong = 0
    for cname, src, exp in files:
        pr = exp.get("params", {})
        doc = process(src, Params(pr.get("currency"), Decimal(pr["opening"]) if "opening" in pr else None,
                                  pr.get("account"), pr.get("allow_derived_opening", False), model=True))
        released = doc["status"] == "ok"
        rel += released and exp["status"] == "ok"
        bad = released and exp["status"] == "refused"
        wrong += bad
        print(f"  {name:20} {cname:38} want={exp['status']:7} got={doc['status']:7} {doc.get('error', {}).get('code', '')}{'  FALSE ACCEPT' if bad else ''}", flush=True)
    n_ok = sum(1 for _, _, e in files if e["status"] == "ok")
    summary[name] = (rel, n_ok, wrong)
    print(f"== {name}: released {rel}/{n_ok} expected-ok files, false accepts {wrong}", flush=True)
print("\nSUMMARY", flush=True)
for k, (r, n, w) in summary.items():
    print(f"{k:24} released {r}/{n}  false_accepts {w}", flush=True)
(OUT / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
