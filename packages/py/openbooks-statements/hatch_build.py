"""Ships the model assets in both targets. The source of truth is models/ at the repo root; the sdist carries a copy under
models/ so a wheel built from the sdist gets the same weights, calibration and model card (the hash binding needs the pair)."""
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

ASSETS = ("roles_head.pt", "roles_calibration.json", "roles_model_card.json")


class ModelAssets(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        src = root / "models" if (root / "models").is_dir() else root / ".." / ".." / ".." / "models"
        for name in ASSETS:
            path = src / name
            if not path.is_file():
                raise FileNotFoundError(f"model asset missing: {path}")
            dest = f"models/{name}" if self.target_name == "sdist" else f"openbooks_statements/data/{name}"
            build_data["force_include"][str(path.resolve())] = dest
