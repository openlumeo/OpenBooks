"""Prometheus text exposition, hand-rolled: counters, cumulative histograms and gauges read at scrape time."""
from __future__ import annotations

import os
import sys
import threading
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import TypeVar

from fastapi.responses import Response

from . import admission as adm

HISTOGRAM_BUCKETS = (.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60, 120, 300)
PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
_PROC_STATM = Path("/proc/self/statm")  # ponytail: Linux only; add psutil if Windows or macOS hosts matter
_LABEL_DROP = str.maketrans("", "", '\\"\n')  # backslash, quote and newline would corrupt the exposition
LabelKey = tuple[tuple[str, str], ...]
V = TypeVar("V")


def sanitise_label(value: object) -> str:
    """Make a label value safe to embed in quotes: drops backslashes, double quotes and newlines."""
    return str(value).translate(_LABEL_DROP)


def _label_block(pairs: Iterable[tuple[str, str]]) -> str:
    items = [f'{k}="{sanitise_label(v)}"' for k, v in pairs]
    return "{" + ",".join(items) + "}" if items else ""


@dataclass
class _Histogram:
    """Cumulative bucket counts (bucket i counts observations <= HISTOGRAM_BUCKETS[i]), total count and sum."""

    cumulative: list[float] = field(default_factory=lambda: [0.0] * len(HISTOGRAM_BUCKETS))
    count: float = 0.0
    total: float = 0.0

    def observe(self, seconds: float) -> None:
        for i, bound in enumerate(HISTOGRAM_BUCKETS):
            if seconds <= bound:
                self.cumulative[i] += 1
        self.count += 1
        self.total += seconds


def _grouped_by_name(series: Mapping[tuple[str, LabelKey], V]) -> Iterator[tuple[str, list[tuple[LabelKey, V]]]]:
    """Yield (metric name, its label sets) in sorted order."""
    ordered = sorted(series.items())
    for name, group in groupby(ordered, key=lambda item: item[0][0]):
        yield name, [(labels, value) for (_, labels), value in group]


class Metrics:
    """Thread-safe store of counters and histograms. Label sets are sorted tuples so output order is stable."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, LabelKey], float] = {}
        self._hists: dict[tuple[str, LabelKey], _Histogram] = {}

    def inc(self, name: str, **labels: str) -> None:
        """Add one to a counter."""
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1

    def observe(self, name: str, seconds: float, **labels: str) -> None:
        """Record one duration sample in a histogram."""
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._hists.setdefault(key, _Histogram()).observe(seconds)

    def render(self, gauges: dict[str, float]) -> str:
        """The full scrape body: counters, histograms, then the given gauges."""
        with self._lock:
            lines = self._counter_lines() + self._histogram_lines()
        for name, value in sorted(gauges.items()):
            lines += [f"# TYPE {name} gauge", f"{name} {value:g}"]
        return "\n".join(lines) + "\n"

    def _counter_lines(self) -> list[str]:
        lines: list[str] = []
        for name, series in _grouped_by_name(self._counters):
            lines.append(f"# TYPE {name} counter")
            lines += [f"{name}{_label_block(labels)} {value:g}" for labels, value in series]
        return lines

    def _histogram_lines(self) -> list[str]:
        lines: list[str] = []
        for name, series in _grouped_by_name(self._hists):
            lines.append(f"# TYPE {name} histogram")
            for labels, hist in series:
                lines += _histogram_series(name, labels, hist)
        return lines


def _histogram_series(name: str, labels: LabelKey, hist: _Histogram) -> list[str]:
    lines = [f"{name}_bucket{_label_block([*labels, ('le', f'{bound:g}')])} {count:g}"
             for bound, count in zip(HISTOGRAM_BUCKETS, hist.cumulative)]
    lines.append(f"{name}_bucket{_label_block([*labels, ('le', '+Inf')])} {hist.count:g}")
    lines.append(f"{name}_sum{_label_block(labels)} {hist.total:.6f}")
    lines.append(f"{name}_count{_label_block(labels)} {hist.count:g}")
    return lines


registry = Metrics()


def observe_stages(kind: str, stages: dict[str, float]) -> None:
    """Record each pipeline stage duration under the input kind; negative clock noise is clamped to zero."""
    for stage, seconds in stages.items():
        registry.observe("openbooks_stage_seconds", max(seconds, 0.0), stage=stage, input_kind=kind)


_SUFFIX_KINDS = {".pdf": "pdf_text", ".png": "ocr", ".jpg": "ocr", ".jpeg": "ocr"}


def input_kind(method: str | None, suffix: str) -> str:
    """pdf_text | ocr | other. The engine's own method wins; the file suffix is the fallback (refusals)."""
    if method in ("pdf_text", "ocr"):
        return method
    return _SUFFIX_KINDS.get(suffix.lower(), "other")


def _process_gauges() -> dict[str, float]:
    gauges: dict[str, float] = {}
    try:
        resident_pages = int(_PROC_STATM.read_text().split()[1])
        gauges["process_resident_memory_bytes"] = resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, AttributeError):
        pass
    torch = sys.modules.get("torch")  # only report CUDA if torch is already loaded; never import it here
    if torch is not None and torch.cuda.is_available():
        gauges["openbooks_cuda_max_allocated_bytes"] = torch.cuda.max_memory_allocated()
    return gauges


def gauges() -> dict[str, float]:
    """Point-in-time values: admission counters, drain flag and process memory."""
    gate = adm.current
    return {"openbooks_inflight_jobs": gate.running, "openbooks_queued_jobs": gate.queued,
            "openbooks_inflight_bytes": gate.bytes, "openbooks_inflight_ocr_pages": gate.pages,
            "openbooks_draining": int(gate.draining), **_process_gauges()}


def metrics_response() -> Response:
    """The /metrics response in Prometheus text format."""
    return Response(registry.render(gauges()), media_type=PROMETHEUS_CONTENT_TYPE)
