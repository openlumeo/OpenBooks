"""Fails when package versions drift apart or a release tag disagrees with its package.

Usage: python scripts/check_versions.py [TAG]   (TAG like py-v0.2.0, js-v0.2.1; optional)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

engine = re.search(r'"(.*)"', (ROOT / "packages/py/openbooks/src/openbooks/_version.py").read_text()).group(1)
js = {"cli": json.loads((ROOT / "packages/js/cli/package.json").read_text(encoding="utf-8"))}
js_versions = {pkg["version"] for pkg in js.values()}
if len(js_versions) != 1:
    errors.append("npm packages disagree: " + ", ".join(f"{n}={p['version']}" for n, p in sorted(js.items())))
for name, pkg in js.items():
    for dep, spec in pkg.get("dependencies", {}).items():
        if dep.startswith("@lumeo_hq/") and spec != "workspace:*":
            errors.append(f"{name}: {dep} is '{spec}', expected 'workspace:*'")

if len(sys.argv) > 1:
    tag = sys.argv[1]
    want = {"py-v": engine, "js-v": next(iter(js_versions), "")}
    prefix = next((p for p in want if tag.startswith(p)), None)
    if prefix is None:
        errors.append(f"unknown tag prefix: {tag}")
    elif tag[len(prefix):] != want[prefix]:
        errors.append(f"tag {tag} does not match package version {want[prefix]}")

print(f"engine {engine} | npm {', '.join(sorted(js_versions))}")
for e in errors:
    print("ERROR:", e)
sys.exit(1 if errors else 0)
