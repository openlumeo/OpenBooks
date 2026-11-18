"""Write models/roles_model_card.json: the public-safe description of the shipped heads that goes inside the statements wheel.

The full models/roles_manifest.json (hyperparameters, seeds, calibration fit sets, source hashes) is the training record and
stays private. Run this after every promotion; tests/test_model_card.py fails if the card disagrees with the weights."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build() -> dict:
    m = json.loads((ROOT / "models" / "roles_manifest.json").read_text(encoding="utf-8"))
    cal = json.loads((ROOT / "models" / "roles_calibration.json").read_text(encoding="utf-8"))
    weights = (ROOT / "models" / "roles_head.pt").read_bytes()
    sha = hashlib.sha256(weights).hexdigest()
    assert m["weights_sha256"] == cal["weights_sha256"] == sha, "manifest, calibration and weights disagree; promote again"
    return {
        "model": m["model"], "parameters": m["parameters"], "weights_mb_int8_at_rest": m["weights_mb_int8_at_rest"],
        "weights_sha256": sha, "initialisation": "random; no pretrained weights",
        "training_data": "synthetic statements only; no third-party dataset and no real client document",
        "calibration": {"method": m["calibration"]["method"], "alpha": m["calibration"]["alpha"]},
        "role": "cross-check only: the heads can add refusals, never cause a release",
    }


if __name__ == "__main__":
    card = build()
    (ROOT / "models" / "roles_model_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print("wrote models/roles_model_card.json", card["weights_sha256"][:12])
