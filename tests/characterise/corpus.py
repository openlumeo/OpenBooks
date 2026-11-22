"""Characterisation corpus: a deterministic set of inputs whose (status, code, output hash) is frozen before the
package split and must not change during it. Nothing here asserts that the engine is *right*; it asserts that the
refactor did not change what the engine does. Correctness is the job of the existing suite.

Two sections:
  main  built without PDF generation, so it is identical on every machine (no PyMuPDF needed).
  pdf   the golden text-layer PDFs; only built where PyMuPDF imports. Recorded and verified in CI.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import itertools
import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARAM_VARIANTS = {
    "default": {},
    "usd": {"currency": "USD"},
    "mdy": {"date_order": "mdy"},
    "derived": {"allow_derived_opening": True, "currency": "INR"},
}


@dataclass
class Case:
    id: str
    path: Path
    params: dict = field(default_factory=dict)


def have_fitz() -> bool:
    try:
        import fitz  # noqa: F401
    except Exception:
        return False
    return True


def _more_parsers_fixtures() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("_more_fx", HERE.parent / "test_more_parsers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {"PAYPAL": mod.PAYPAL, "WISE": mod.WISE, "B1099": mod.B1099}


def _write(root: Path, name: str, content: str | bytes, ext: str = "csv") -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"in.{ext}"
    p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return p


def _golden(root: Path, which: str) -> list[Case]:
    try:
        from openbooks_lab import golden_docs
        from openbooks_lab.golden import build
    except ModuleNotFoundError:
        from openbooks import golden_docs
        from openbooks.golden import build

    gdir = root / "_golden"
    if which == "main":
        saved = golden_docs.build_pdfs
        golden_docs.build_pdfs = lambda *a, **k: None
        try:
            build(gdir, seed=7, n_random=12, scans=False)
        finally:
            golden_docs.build_pdfs = saved
    else:
        gdir.mkdir(parents=True, exist_ok=True)
        golden_docs.build_pdfs(gdir, random.Random(7), False)
    import json

    out = []
    for d in sorted(p for p in gdir.iterdir() if p.is_dir()):
        src = next(f for f in d.iterdir() if f.name != "expected.json")
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        out.append(Case(f"golden/{d.name}", src, exp.get("params", {})))
    return out


def _layout_headers() -> dict[str, list[str]]:
    from openbooks import pipeline as p

    return {"stripe": sorted(p.STRIPE_REQ), "razorpay": sorted(p.RAZORPAY_REQ), "paypal": sorted(p.PAYPAL_REQ),
            "wise": sorted(p.WISE_REQ), "b1099": sorted(p.B1099_REQ), "tds": sorted(p.TDS_REQ), "ais": sorted(p.AIS_REQ),
            "fira": sorted(p.FIRA_REQ), "bank": ["date", "narration", "withdrawal_amt", "deposit_amt", "closing_balance"],
            "tb": sorted(p.TB_REQ)}


def _csv_text(rows: list[list[str]], delim: str = ",") -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter=delim, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def _extra(root: Path) -> list[Case]:
    cases: list[Case] = []
    fx = _more_parsers_fixtures()
    for name, text in fx.items():
        cases.append(Case(f"extra/{name.lower()}", _write(root, f"x_{name}", text)))
    for k, (old, new) in enumerate([("1,096.80", "1,096.81"), ("-3.20", "-3.10"), ("USD", "EUR")]):
        cases.append(Case(f"extra/paypal_tamper{k}", _write(root, f"x_pp{k}", fx["PAYPAL"].replace(old, new))))
    cases.append(Case("extra/wise_tamper", _write(root, "x_wi", fx["WISE"].replace("1074.50", "1074.51")), {"opening": None}))
    cases.append(Case("extra/b1099_tamper", _write(root, "x_b", fx["B1099"].replace("425.00", "425.01"))))

    heads = _layout_headers()
    names = list(heads)
    for a in names:
        cases.append(Case(f"precedence/single_{a}", _write(root, f"pr_s_{a}", _csv_text([heads[a], ["1"] * len(heads[a])]))))
    for a, b in itertools.combinations(names, 2):
        union = heads[a] + [h for h in heads[b] if h not in heads[a]]
        cases.append(Case(f"precedence/union_{a}_{b}",
                          _write(root, f"pr_u_{a}_{b}", _csv_text([union, ["1"] * len(union)]), "csv")))
    for a, b in itertools.permutations(["stripe", "bank", "tds", "tb"], 2):
        rows = [heads[a], ["1"] * len(heads[a]), [], heads[b], ["1"] * len(heads[b])]
        cases.append(Case(f"precedence/rows_{a}_then_{b}", _write(root, f"pr_r_{a}_{b}", _csv_text(rows))))
    cases.append(Case("precedence/preamble_bank", _write(
        root, "pr_pre", "Statement for account 123\nGenerated 01/01/2026\n\n" + _csv_text([heads["bank"], ["01/01/2026", "x", "", "5.00", "1005.00"]])),
        {"opening": "1000.00", "currency": "INR"}))
    cases.append(Case("precedence/header_beyond_scan_window", _write(
        root, "pr_far", "\n" * 40 + _csv_text([heads["bank"], ["01/01/2026", "x", "", "5.00", "1005.00"]])),
        {"opening": "1000.00", "currency": "INR"}))

    ok_bank = next(c for c in _golden(root, "main") if c.id == "golden/ok_bank_csv")
    text = ok_bank.path.read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    base = {"opening": "1000.00", "currency": "INR"}
    for delim, label in ((";", "semicolon"), ("\t", "tab")):
        cases.append(Case(f"delim/{label}", _write(root, f"d_{label}", _csv_text(rows, delim)), base))
    cases.append(Case("input/cp1252", _write(root, "i_cp", text.replace("Rent", "Café").encode("cp1252")), base))
    cases.append(Case("input/bom", _write(root, "i_bom", b"\xef\xbb\xbf" + text.encode("utf-8")), base))
    cases.append(Case("input/crlf", _write(root, "i_crlf", text.replace("\n", "\r\n")), base))
    cases.append(Case("input/nul", _write(root, "i_nul", b"a,b\n\x00\n"), base))
    cases.append(Case("input/empty", _write(root, "i_empty", ""), base))
    cases.append(Case("input/only_header", _write(root, "i_hdr", _csv_text([rows[0]])), base))
    cases.append(Case("input/short_row", _write(root, "i_short", _csv_text([rows[0], rows[1][:2]])), base))
    cases.append(Case("input/bad_ext", _write(root, "i_ext", text, "exe"), base))

    amount_cols = [i for i, h in enumerate(rows[0]) if any(k in h.lower() for k in ("withdrawal", "deposit", "balance"))]
    for r in range(1, len(rows)):
        for c in amount_cols:
            if not rows[r][c]:
                continue
            for tag, val in (("plus", rows[r][c] + "1"), ("blank", ""), ("neg", "-" + rows[r][c]), ("comma", "1,00.00")):
                m = [row[:] for row in rows]
                m[r][c] = val
                cases.append(Case(f"mutate/r{r}c{c}_{tag}", _write(root, f"m_{r}_{c}_{tag}", _csv_text(m)), base))
    return cases


def build_corpus(section: str, root: Path | None = None) -> list[Case]:
    root = root or Path(tempfile.mkdtemp(prefix="ob-char-"))
    if section == "main":
        return _golden(root, "main") + _extra(root)
    if section == "pdf":
        return _golden(root, "pdf")
    raise ValueError(section)
