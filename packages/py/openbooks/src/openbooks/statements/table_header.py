"""Column detection for a statement table: header-line roles and which header column a word belongs to."""
from __future__ import annotations

import re

from openbooks.statements.pdf_words import _MONEY, Word


HEADER = {"date": {"date"}, "desc": {"description", "narration", "particulars", "details", "remarks"},
          "debit": {"debit", "debits", "withdrawal", "withdrawals", "dr"},
          "credit": {"credit", "credits", "deposit", "deposits", "cr"}, "balance": {"balance"},
          "amount": {"amount", "amt"}, "ind": {"crdr", "drcr", "dc", "cd", "type"}}
_IND = {"cr": "credit", "credit": "credit", "dr": "debit", "debit": "debit"}


def _header_cols(line: list[Word]):
    """(mode, {role: Word}) for a header line. mode 'split' = Debit and Credit columns; 'single' = one Amount column
    plus a Cr/Dr marker. None if the line is not a header."""
    if any(_MONEY.match(w.text) for w in line):
        return None
    found: dict[str, list[tuple[int, Word]]] = {}
    for i, w in enumerate(line):
        t = re.sub(r"[^a-z]", "", w.text.lower())
        for role, names in HEADER.items():
            if t in names:
                found.setdefault(role, []).append((i, w))
    split = {"date", "debit", "credit", "balance"} <= found.keys()
    single = {"date", "amount", "balance"} <= found.keys() and not ({"debit", "credit"} & found.keys())
    if not (split or single):
        return None
    cols = {}
    for role, hits in found.items():
        pick = hits[0][1]
        if role == "date":
            pick = next((w for i, w in hits if not (i and line[i - 1].text.lower() == "value")), pick)
        cols[role] = pick
    return ("split" if split else "single"), cols


def _near(w: Word, cols: dict[str, Word], roles: tuple[str, ...]) -> str:
    return min(roles, key=lambda r: min(abs(w.cx - cols[r].cx), abs(w.x1 - cols[r].x1)))


def find_header(lines: list[list[Word]]):
    """(line index, (mode, cols)) of the first line that is a table header, or None."""
    return next(((i, h) for i, ln in enumerate(lines) if (h := _header_cols(ln))), None)
