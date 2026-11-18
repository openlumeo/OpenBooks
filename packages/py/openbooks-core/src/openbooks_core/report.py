"""openbooks report: every supported file in a folder through process(), then cross-file links if a linker is installed."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

from .evidence import sha256_file
from .guard import ALLOWED_EXT
from .output import write_atomic
from .params import Params
from .process import dumps, process
from .registry import Registry, default_registry


def run_report(folder: Path, out: Path, p: Params, registry: Registry | None = None) -> int:
    """End to end: every supported file -> openbooks.v1 JSON (or typed refusal) -> cross-file links -> report.json."""
    from collections import Counter

    linker = (registry or default_registry()).linker()
    files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in ALLOWED_EXT)
    if not files:  # nothing to process is not a clean "0 of 0 released"
        sys.stderr.write(f"openbooks: no supported files in {folder} (looked for {', '.join(sorted(ALLOWED_EXT))})\n")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    per_file = json.loads((folder / "params.json").read_text(encoding="utf-8")) if (folder / "params.json").exists() else {}
    docs, rows, seen = [], [], set()
    for f in files:
        sha = sha256_file(f)
        if sha in seen:
            rows.append({"file": f.name, "status": "duplicate", "code": None, "format": None, "method": None, "message": "same bytes as an earlier file"})
            continue
        seen.add(sha)
        q = per_file.get(f.name, {})
        doc = process(f, Params(q.get("currency", p.currency), Decimal(q["opening"]) if "opening" in q else p.opening,
                                q.get("account", p.account), q.get("allow_derived_opening", p.allow_derived_opening), p.ocr, p.model,
                                q.get("date_order", p.date_order)), registry=registry)
        write_atomic(out / f"{doc['file']['sha256'] if doc['status'] == 'ok' else sha256_file(f)}.json", dumps(doc))
        docs.append(doc)
        rows.append({"file": f.name, "status": doc["status"], "code": doc.get("error", {}).get("code"),
                     "format": doc.get("file", {}).get("detected_format"), "method": doc.get("file", {}).get("method"),
                     "message": doc.get("error", {}).get("message")})
    links = linker.link(docs) if linker else None
    report = {"files": rows, "released": sum(r["status"] == "ok" for r in rows),
              "refused": dict(Counter(r["code"] for r in rows if r["status"] == "refused"))}
    if links:
        report.update({"links": links["links"], "ambiguous": links["ambiguous"],
                       "unlinked_sources": links["unlinked_sources"], "unlinked_credits": links["unlinked_credits"]})
    write_atomic(out / "report.json", json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    for r in rows:
        sys.stdout.write(f"{r['file']}: {r['status']} {r['code'] or r['format'] or ''}\n")
    tail = (f" links={len(links['links'])} ambiguous={len(links['ambiguous'])}" if links
            else " (no linker installed, so files were not linked)")
    sys.stdout.write(f"released={report['released']}/{len(rows)} refused={report['refused']}{tail} -> {out / 'report.json'}\n")
    return 1 if any(r["status"] == "refused" for r in rows) else 0
