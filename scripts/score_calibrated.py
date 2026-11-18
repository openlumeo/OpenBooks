import json
import pickle
import sys
from pathlib import Path

import torch

ROOT = Path("C:/Desktop/openbooks")
sys.path.insert(0, str(ROOT / "scripts"))
import train_roles as tr  # noqa: E402
from openbooks.calibration import Calibrator  # noqa: E402
from openbooks.encoder import RoleNet, dequantize_state  # noqa: E402

torch.set_num_threads(10)
blob = torch.load(ROOT / "models" / "roles_head.pt", map_location="cpu", weights_only=False)
net = RoleNet(len(tr.ROLES), len(tr.VTYPES))
net.load_state_dict(dequantize_state(blob["int8_state"]))
net.eval()
cal = json.loads((ROOT / "models" / "roles_calibration.json").read_text(encoding="utf-8"))
mk = lambda d: Calibrator(d["temperature"], float("inf") if d["qhat"] is None else d["qhat"], d["alpha"])  # noqa: E731
cal_r, cal_t = mk(cal["role"]), mk(cal["vtype"])
splits = pickle.loads((ROOT / "data" / "roles_dataset_1200_150.pkl").read_bytes())
dev = torch.device("cpu")
res = {"calibration": {"role_temperature": round(cal_r.temperature, 3), "role_qhat": cal_r.qhat, "alpha": cal_r.alpha}}
for name in ("calib", "test", "shifted"):
    lg = tr.logits_of(net, splits[name], dev)
    res[name] = tr.report(lg[0], lg[1], lg[2], lg[3], cal_r, cal_t)
out = {"int8_shipped": res, "note": "shipped weights (unchanged) + shift-aware calibration (calib + wide-layout windows, alpha 0.003); scored on the original calib/test/shifted splits, SYNTHETIC"}
dst = ROOT / "docs" / "evidence" / "roles_metrics_calibrated.json"
dst.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps({k: res[k] for k in ("test", "shifted")}, indent=1))
