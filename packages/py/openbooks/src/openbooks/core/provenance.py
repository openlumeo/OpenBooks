from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum


class Provenance(Enum):
    SOURCE_OBSERVED = "SOURCE_OBSERVED"
    CALLER_SUPPLIED = "CALLER_SUPPLIED"
    DETERMINISTICALLY_DERIVED = "DETERMINISTICALLY_DERIVED"
    MODEL_PREDICTED = "MODEL_PREDICTED"
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"


INDEPENDENT = frozenset({Provenance.SOURCE_OBSERVED, Provenance.EXTERNALLY_VERIFIED})


def weakest(*operands: Provenance) -> Provenance:
    return next((p for p in operands if p not in INDEPENDENT), operands[0])


def circular_dependencies(edges: Mapping[str, Iterable[str]]) -> tuple[str, ...]:
    graph = {node: frozenset(deps) for node, deps in edges.items()}

    def reaches_itself(start: str) -> bool:
        seen, stack = set(), list(graph.get(start, ()))
        while stack:
            node = stack.pop()
            if node == start:
                return True
            if node not in seen:
                seen.add(node)
                stack.extend(graph.get(node, ()))
        return False

    return tuple(sorted(node for node in graph if reaches_itself(node)))
