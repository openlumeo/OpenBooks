"""Word boxes read from a statement page, with the line grouping and date-span helpers that work on them."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_MONEY = re.compile(r"^\(?-?\d[\d,]*\.\d{2}\)?(?:Dr|Cr|DR|CR)?$")
_EU = re.compile(r"^\d{1,3}(\.\d{3})+,\d{2}$")
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE_LIKE = re.compile(rf"^(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[ -][A-Za-z]{{3}}[ -]\d{{2,4}}"
                        rf"|\d{{1,2}}[ -](?:{_MONTHS})[ -]\d{{4}})$")


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    conf: float | None = None
    pw: float = 1.0
    ph: float = 1.0
    orig: str | None = None

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return max(self.y1 - self.y0, 1.0)


def _lines(words: list[Word]) -> list[list[Word]]:
    if not words:
        return []
    heights = sorted(w.h for w in words)
    tol = 0.5 * heights[len(heights) // 2]
    lines: list[list[Word]] = []
    cy_sum = 0.0
    cy_abs_sum = 0.0
    for w in sorted(words, key=lambda w: (w.cy, w.x0)):
        cy = w.cy
        if lines:
            mean = cy_sum / len(lines[-1])
            distance = abs(cy - mean)
            # Built-in sum may use compensated floating-point arithmetic. Recompute
            # near the threshold so rounding cannot change line membership.
            error = 4 * math.ulp(1.0) * cy_abs_sum + 4 * math.ulp(max(abs(cy), abs(mean), abs(tol), 1.0))
            if not math.isfinite(distance) or not math.isfinite(error) or abs(distance - tol) <= error:
                distance = abs(cy - sum(x.cy for x in lines[-1]) / len(lines[-1]))
        if lines and distance <= tol:
            lines[-1].append(w)
            cy_sum += cy
            cy_abs_sum += abs(cy)
        else:
            lines.append([w])
            cy_sum = cy
            cy_abs_sum = abs(cy)
    return [sorted(ln, key=lambda w: w.x0) for ln in lines]


def _date_spans(line: list[Word]) -> list[tuple[int, int, str]]:
    """Every date-like span in a line as (first word, word count, raw text)."""
    out, i = [], 0
    while i < len(line):
        for n in (3, 2, 1):
            raw = " ".join(w.text for w in line[i:i + n])
            if i + n <= len(line) and _DATE_LIKE.match(raw):
                out.append((i, n, raw))
                i += n - 1
                break
        i += 1
    return out
