"""Repair comma-for-decimal misreads in OCR transaction amounts, using the printed table's own decimal convention."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace

from openbooks.statements.pdf_words import _EU, _MONEY, Word, _date_spans, _lines
from openbooks.statements.table_header import _near, find_header


_OCR_COMMA_DECIMAL = re.compile(r"\d{1,3},\d{2}")


def _repair_scan_decimal_commas(words: list[Word]) -> list[Word]:
    """Use the printed table's decimal convention to repair a comma misread in an OCR transaction amount."""
    lines = _lines(words)
    heading = find_header(lines)
    if heading is None:
        return words
    i, (mode, cols) = heading
    amounts = ("debit", "credit") if mode == "split" else ("amount",)
    roles = (*amounts, "balance")
    tolerance = {r: min(abs(cols[r].cx - cols[other].cx) for other in roles if r != other) / 3 for r in amounts}
    examples: Counter[str] = Counter()
    candidates: list[tuple[Word, str]] = []
    for line in lines[i + 1:]:
        if not _date_spans(line):
            continue
        if any(_EU.fullmatch(w.text) for w in line):
            return words
        dotted = [_near(w, cols, roles) for w in line if _MONEY.fullmatch(w.text)]
        if dotted.count("balance") != 1:
            continue
        present = [r for r in dotted if r in amounts]
        if present:
            if len(present) == 1:
                examples.update(present)
            continue
        matches = [(w, r) for w in line if _OCR_COMMA_DECIMAL.fullmatch(w.text)
                   for r in amounts if abs(w.cx - cols[r].cx) < tolerance[r]]
        if len(matches) == 1:
            candidates.extend(matches)
    repaired = {w: replace(w, text=w.text.replace(",", "."), orig=w.orig or w.text)
                for w, role in candidates if examples[role] >= 2}
    return [repaired.get(w, w) for w in words] if repaired else words
