from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "0": ("8",),
    "8": ("0", "3", "6"),
    "1": ("7",),
    "7": ("1", "2"),
    "5": ("6",),
    "6": ("5", "8"),
    "3": ("8",),
    "2": ("7",),
}
_SHIFTS: tuple[int, ...] = (-2, -1, 1, 2)
_FIELDS: tuple[str, ...] = ("debit", "credit", "balance")


@dataclass(frozen=True)
class Row:
    debit: str | None
    credit: str | None
    balance: str | None


@dataclass(frozen=True)
class Repair:
    row_index: int
    field: str
    original: str
    repaired: str


def _amount(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except (InvalidOperation, TypeError):
        raise ValueError(f"invalid decimal amount: {text!r}") from None
    if not value.is_finite():
        raise ValueError(f"non-finite decimal amount: {text!r}")
    return value


def _net(row: Row) -> Decimal:
    credit = Decimal(0) if row.credit is None else _amount(row.credit)
    debit = Decimal(0) if row.debit is None else _amount(row.debit)
    return credit - debit


def _chain_holds(opening: Decimal, closing: Decimal, rows: Sequence[Row]) -> bool:
    parsed = [(_net(row), None if row.balance is None else _amount(row.balance)) for row in rows]
    running = opening
    for net, balance in parsed:
        running += net
        if balance is not None and balance != running:
            return False
    return running == closing


def _variants(text: str) -> Iterator[str]:
    for position, char in enumerate(text):
        for partner in _CONFUSIONS.get(char, ()):
            yield text[:position] + partner + text[position + 1:]
    value = _amount(text)
    for shift in _SHIFTS:
        yield format(value.scaleb(shift), "f")


def _single_edits(rows: Sequence[Row]) -> Iterator[Repair]:
    for index, row in enumerate(rows):
        for field in _FIELDS:
            original = getattr(row, field)
            if original is None:
                continue
            for repaired in sorted(set(_variants(original)) - {original}):
                yield Repair(index, field, original, repaired)


def _with_edit(rows: Sequence[Row], edit: Repair) -> list[Row]:
    edited = replace(rows[edit.row_index], **{edit.field: edit.repaired})
    return [*rows[: edit.row_index], edited, *rows[edit.row_index + 1 :]]


def repair_by_running_balance(
    opening: str, closing: str, rows: Sequence[Row], max_edits: int = 1
) -> Repair | None:
    if max_edits != 1:
        raise ValueError("only max_edits=1 is supported")
    start = _amount(opening)
    end = _amount(closing)
    if _chain_holds(start, end, rows):
        return None
    fixes = [edit for edit in _single_edits(rows) if _chain_holds(start, end, _with_edit(rows, edit))]
    return fixes[0] if len(fixes) == 1 else None
