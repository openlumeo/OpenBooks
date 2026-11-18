"""Stable interfaces for optional Open Books layout providers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol


@dataclass(frozen=True)
class Layout:
    """One independently installable parser layout."""
    id: str
    priority: int
    distribution: str
    matches: Callable[[set[str]], bool]
    parse: Callable[[Any, Any], tuple[dict, dict]]
    gate: Callable[[dict], Iterable[tuple[str, str, str, bool]]] | None = None


class LayoutRegistry(Protocol):
    def layouts(self) -> list[Layout]: ...
    def get(self, layout_id: str) -> Layout | None: ...


class MissingLayoutProvider(ImportError):
    """A recognised file family has no installed provider."""
    def __init__(self, layout_id: str, distribution: str) -> None:
        self.layout_id = layout_id
        self.distribution = distribution
        super().__init__(
            f"Layout {layout_id!r} requires optional package {distribution!r}; "
            "install it to process this file."
        )


class UnknownLayout(LookupError):
    """No installed or declared layout matches the input."""


def ordered_layouts(layouts: Iterable[Layout]) -> list[Layout]:
    """Sort providers deterministically and reject duplicate layout identifiers."""
    ordered = sorted(layouts, key=lambda item: (item.priority, item.id))
    ids = [item.id for item in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Open Books layout id")
    return ordered


class InMemoryLayoutRegistry:
    """Deterministic registry useful for providers and isolated tests."""
    def __init__(self, layouts: Iterable[Layout] = ()) -> None:
        self._layouts = ordered_layouts(layouts)

    def layouts(self) -> list[Layout]:
        return list(self._layouts)

    def get(self, layout_id: str) -> Layout | None:
        return next((item for item in self._layouts if item.id == layout_id), None)

    def matching(self, headers: set[str]) -> Layout | None:
        return next((item for item in self._layouts if item.matches(headers)), None)
