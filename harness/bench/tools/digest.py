import hashlib
from pathlib import Path

TASKS = Path(__file__).resolve().parents[1] / "tasks"


def tasks_digest(tasks_dir: Path = TASKS) -> str:
    lines = []
    for folder in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        expected = (folder / "expected.json").read_bytes()
        lines.append(f"{folder.name}:{hashlib.sha256(expected).hexdigest()}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(tasks_digest())
