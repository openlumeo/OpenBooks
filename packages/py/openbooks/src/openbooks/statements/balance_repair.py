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
_SCALE_EXPONENT = -10
_SCALED_DIGITS = 27
_SCALED_LIMIT = 10**_SCALED_DIGITS
_FALLBACK_ROW_CHECKS = 5_000_000
_EMPTY = object()
_MIXED = object()


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


def _scaled_value(value: Decimal) -> int | None:
    sign, digits, exponent = value.as_tuple()
    shift = exponent - _SCALE_EXPONENT
    if shift < 0 or len(digits) + shift > _SCALED_DIGITS:
        return None
    magnitude = int("".join(map(str, digits))) * 10**shift
    return -magnitude if sign else magnitude


def _scaled_fields(row: Row) -> tuple[int | None, ...] | None:
    fields: list[int | None] = []
    for text in (row.debit, row.credit, row.balance):
        if text is None:
            fields.append(None)
            continue
        scaled = _scaled_value(_amount(text))
        if scaled is None:
            return None
        fields.append(scaled)
    return tuple(fields)


def _scaled_net(fields: tuple[int | None, ...]) -> int:
    debit, credit, _ = fields
    return (credit or 0) - (debit or 0)


def _is_mismatch(offset: int | None) -> bool:
    return offset is not None and offset != 0


def _combine(state: object, offset: int) -> object:
    if state is _EMPTY:
        return offset
    if state is _MIXED or state != offset:
        return _MIXED
    return state


class _ChainIndex:
    def __init__(self, start: int, end: int, fields: Sequence[tuple[int | None, ...]]) -> None:
        self._end = end
        self._fields = list(fields)
        self._nets = [_scaled_net(row) for row in fields]
        self._running: list[int] = []
        total = start
        for net in self._nets:
            total += net
            self._running.append(total)
        self._total = total
        self._offsets = [
            None if row[2] is None else row[2] - running for row, running in zip(fields, self._running)
        ]
        self._mismatches = sum(1 for offset in self._offsets if _is_mismatch(offset))
        self._first_mismatch = next((i for i, offset in enumerate(self._offsets) if _is_mismatch(offset)), len(fields))
        self._suffix: list[object] = [_EMPTY] * (len(fields) + 1)
        for i in range(len(fields) - 1, -1, -1):
            offset = self._offsets[i]
            self._suffix[i] = self._suffix[i + 1] if offset is None else _combine(self._suffix[i + 1], offset)

    @classmethod
    def build(cls, start: int, end: int, fields: Sequence[tuple[int | None, ...]]) -> _ChainIndex | None:
        index = cls(start, end, fields)
        if any(abs(total) >= _SCALED_LIMIT for total in index._running):
            return None
        return index

    def fits(self, edit: Repair) -> bool | None:
        value = _scaled_value(_amount(edit.repaired))
        if value is None:
            return None
        if edit.field == "balance":
            return self._balance_fits(edit.row_index, value)
        position = _FIELDS.index(edit.field)
        fields = self._fields[edit.row_index]
        candidate = (*fields[:position], value, *fields[position + 1 :])
        return self._shift_fits(edit.row_index, _scaled_net(candidate) - self._nets[edit.row_index])

    def _balance_fits(self, index: int, value: int) -> bool:
        if self._total != self._end:
            return False
        others = self._mismatches - (1 if _is_mismatch(self._offsets[index]) else 0)
        return others == 0 and value == self._running[index]

    def _shift_fits(self, index: int, delta: int) -> bool:
        needed = self._end - self._total
        if delta != needed or self._first_mismatch < index:
            return False
        state = self._suffix[index]
        return state is _EMPTY or (state is not _MIXED and state == needed)


def _exact_index(start: Decimal, end: Decimal, rows: Sequence[Row]) -> _ChainIndex | None:
    start_scaled = _scaled_value(start)
    end_scaled = _scaled_value(end)
    if start_scaled is None or end_scaled is None:
        return None
    fields = []
    for row in rows:
        scaled = _scaled_fields(row)
        if scaled is None:
            return None
        fields.append(scaled)
    return _ChainIndex.build(start_scaled, end_scaled, fields)


def repair_by_running_balance(
    opening: str, closing: str, rows: Sequence[Row], max_edits: int = 1
) -> Repair | None:
    if max_edits != 1:
        raise ValueError("only max_edits=1 is supported")
    start = _amount(opening)
    end = _amount(closing)
    if _chain_holds(start, end, rows):
        return None
    index = _exact_index(start, end, rows)
    fixes: list[Repair] = []
    spent = 0
    for edit in _single_edits(rows):
        verdict = None if index is None else index.fits(edit)
        if verdict is None:
            spent += len(rows)
            if spent > _FALLBACK_ROW_CHECKS:
                raise ValueError("balance repair work budget exceeded; statement is too large for exact checking")
            verdict = _chain_holds(start, end, _with_edit(rows, edit))
        if verdict:
            fixes.append(edit)
            if len(fixes) == 2:
                return None
    return fixes[0] if len(fixes) == 1 else None
