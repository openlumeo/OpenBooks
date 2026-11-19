"""Read and verify the files produced by a typed-head training run."""
import hashlib
import json
from pathlib import Path

ARTIFACTS = ("roles_head.pt", "roles_calibration.json", "roles_metrics.json")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def split_sha256(windows: list[dict]) -> str:
    """Hash the ordered inputs and labels of an evaluation split."""
    digest = hashlib.sha256()
    for window in windows:
        values = [window[name] for name in ("w", "s", "b", "y", "t")]
        digest.update(json.dumps(values, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def verify_bundle(directory: Path) -> dict[str, str]:
    manifest = json.loads((directory / "roles_manifest.json").read_text(encoding="utf-8"))
    expected = manifest.get("artifacts_sha256")
    if not isinstance(expected, dict) or set(expected) != set(ARTIFACTS):
        raise ValueError("Candidate manifest must list all three artifact hashes")
    for name in ARTIFACTS:
        if sha256(directory / name) != expected[name]:
            raise ValueError(f"Candidate artifact changed: {name}")
    return expected
