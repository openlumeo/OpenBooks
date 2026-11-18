"""The public model card must agree with the weights and must not carry the training recipe."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_model_card_matches_the_weights_and_the_calibration():
    card = json.loads((ROOT / "models" / "roles_model_card.json").read_text(encoding="utf-8"))
    cal = json.loads((ROOT / "models" / "roles_calibration.json").read_text(encoding="utf-8"))
    assert card["weights_sha256"] == cal["weights_sha256"] == hashlib.sha256((ROOT / "models" / "roles_head.pt").read_bytes()).hexdigest()


def test_the_model_card_carries_no_training_recipe():
    text = (ROOT / "models" / "roles_model_card.json").read_text(encoding="utf-8").lower()
    for word in ("seed", "lr_", "batch_size", "epochs", "jepa", "cord", "source_sha256", "scripts/", "synth.py"):
        assert word not in text, word
