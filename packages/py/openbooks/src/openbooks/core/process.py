"""process(): guard -> detect -> parse -> normalise -> gate -> validate, one file in, one document or typed refusal out."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .evidence import sha256_file
from .gates import coverage, require_balance, run_gate
from .guard import DOC_EXT, MAX_BYTES, check_input, decode, read_text_input
from .errors import EngineFault, Refusal
from .frontends.xlsx import parse_xlsx
from .params import Params
from .registry import Registry, default_registry, detect
from .schema import SCHEMA_VERSION, refusal_doc, validate_output

STAGES = ("detect", "parse", "normalise", "balance", "validate")


def _extract(path: Path, p: Params, reg: Registry, stage: Callable[[str], None]) -> tuple:
    """Detect the format and parse the file. Returns (data, evidence, format name, layout, method)."""
    ext = path.suffix.lower()
    method = "parser"
    if ext in DOC_EXT:
        data, ev, fmt_name, layout, method = reg.frontend("document").extract(path, p)
        stage("detect")
    elif ext == ".xlsx":
        data, ev, fmt_name, layout = parse_xlsx(path, p, reg)
        stage("detect")
    else:
        text = decode(read_text_input(path))
        det = detect(text)
        fmt_name, layout = det.format, det.layout
        stage("detect")
        if det.args is None:
            data, ev = reg.sniffer_parser(layout)(text, p)
        else:
            data, ev = reg.run_layout(layout, det.args, p)
    return data, ev, fmt_name, layout, method


def process(path: str | Path, params: Params | None = None, on_stage: Callable[[str], None] | None = None,
            *, registry: Registry | None = None, strict: bool = False, max_bytes: int = MAX_BYTES) -> dict:
    """on_stage, if given, is called with each name in STAGES once that stage has succeeded.
    Parsers normalise as they read, so "parse" and "normalise" are reported together.
    registry is for tests (a view with some providers removed); normally the installed providers are used.
    strict=True (the CLI) raises EngineFault for environment problems (missing library, unreadable file, out of memory)
    instead of reporting them as a document refusal. Default False keeps the 0.1 behaviour for API callers."""
    path, p = Path(path), params or Params()
    stage = on_stage or (lambda _name: None)
    sha = sha256_file(path)
    try:
        reg = registry or default_registry()
        check_input(path, max_bytes=max_bytes)
        ext = path.suffix.lower()
        data, ev, fmt_name, layout, method = _extract(path, p, reg, stage)
        stage("parse")
        stage("normalise")
        assertions = run_gate(data, reg.gates({b["kind"] for b in data["batches"]}))
        verification = require_balance(data, assertions)
        stage("balance")
        model_id = None
        if p.model and ext in DOC_EXT:
            model_id = reg.frontend("document").identity(p)
        doc = {"schema_version": SCHEMA_VERSION, "status": "ok",
               "file": {"sha256": sha, "name": path.name, "detected_format": fmt_name,
                        "layout_version": layout, "method": method, **({"model": model_id} if model_id else {})},
               "data": data, "evidence": ev, "assertions": assertions,
               "verification": verification, "coverage": coverage(data)}
        validate_output(doc)
        stage("validate")
        return doc
    except Refusal as r:
        return refusal_doc(r.code, r.message, sha)
    except Exception as e:
        if strict and isinstance(e, EngineFault):
            raise
        if strict and isinstance(e, (ImportError, MemoryError, OSError)):
            raise EngineFault(f"{type(e).__name__}: {e}") from e
        return refusal_doc("PARSE_ERROR", f"unexpected {type(e).__name__}: {e}", sha, internal=True)


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
