from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "harness"))

from bench.score import EXPECTED_FILE, tasks_digest  # noqa: E402

TASKS_DIR = ROOT / "harness" / "bench" / "tasks"
OUTPUT = ROOT / "web" / "lib" / "benchmark" / "task-sets.json"
SCHEMA = "openbooks.bench.task-sets.v1"
LABEL = "openbooks-bench-1"


def collect_tasks(root: Path) -> dict[str, dict[str, str]]:
    tasks: dict[str, dict[str, str]] = {}
    for child in sorted(root.iterdir()):
        expected = child / EXPECTED_FILE
        if child.is_dir() and expected.is_file():
            tasks[child.name] = {"expectedRaw": expected.read_bytes().decode("utf-8")}
    return tasks


def main() -> int:
    digest = tasks_digest(TASKS_DIR)
    tasks = collect_tasks(TASKS_DIR)
    document = {"schema": SCHEMA, "sets": {digest: {"label": LABEL, "tasks": tasks}}}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"digest {digest} tasks {len(tasks)} wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
