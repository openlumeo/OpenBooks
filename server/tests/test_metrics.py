"""Prometheus text rendering: counters, cumulative histograms, gauges, label sanitising and the stage/kind helpers."""
import os
import sys

import pytest

from openbooks_server import admission as adm
from openbooks_server import metrics
from openbooks_server.admission import Admission
from openbooks_server.metrics import Metrics, input_kind, metrics_response, observe_stages


def test_histogram_buckets_are_cumulative_with_inf_sum_and_count():
    reg = Metrics()
    for seconds in (0.001, 0.2, 1000):
        reg.observe("h", seconds, stage="x")

    lines = reg.render({}).splitlines()

    assert 'h_bucket{stage="x",le="0.005"} 1' in lines
    assert 'h_bucket{stage="x",le="0.25"} 2' in lines
    assert 'h_bucket{stage="x",le="300"} 2' in lines
    assert 'h_bucket{stage="x",le="+Inf"} 3' in lines
    assert 'h_sum{stage="x"} 1000.201000' in lines
    assert 'h_count{stage="x"} 3' in lines


def test_histogram_declares_its_type_once_per_metric_name():
    reg = Metrics()
    reg.observe("h", 0.1, stage="a")
    reg.observe("h", 0.1, stage="b")

    text = reg.render({})

    assert text.count("# TYPE h histogram") == 1
    assert 'h_count{stage="a"} 1' in text and 'h_count{stage="b"} 1' in text


def test_counter_renders_its_total_with_a_counter_type():
    reg = Metrics()
    reg.inc("c_total", route="/v1/runs")
    reg.inc("c_total", route="/v1/runs")

    assert reg.render({}).splitlines()[:2] == ["# TYPE c_total counter", 'c_total{route="/v1/runs"} 2']


def test_label_names_are_rendered_in_sorted_order():
    reg = Metrics()
    reg.inc("c", zeta="1", alpha="2")

    assert 'c{alpha="2",zeta="1"} 1' in reg.render({})


@pytest.mark.parametrize("raw, expected", [
    ('a"b', "ab"),
    ("a\\b", "ab"),
    ("a\nb", "ab"),
    ('x"\\\n', "x"),
    ("plain-value_1", "plain-value_1"),
])
def test_label_values_are_sanitised_so_the_exposition_stays_valid(raw, expected):
    reg = Metrics()
    reg.inc("c", v=raw)

    assert f'c{{v="{expected}"}} 1' in reg.render({})


def test_gauges_render_after_metrics_with_a_gauge_type():
    text = Metrics().render({"g_b": 2.5, "g_a": 1})

    assert text == "# TYPE g_a gauge\ng_a 1\n# TYPE g_b gauge\ng_b 2.5\n"


def test_empty_registry_renders_a_single_newline():
    assert Metrics().render({}) == "\n"


def test_observed_stage_seconds_are_clamped_to_zero_when_negative():
    observe_stages("ocr", {"extract": -0.5})

    text = metrics.registry.render({})

    assert 'openbooks_stage_seconds_sum{input_kind="ocr",stage="extract"} 0.000000' in text


@pytest.mark.parametrize("method, suffix, expected", [
    ("pdf_text", ".csv", "pdf_text"),
    ("ocr", ".pdf", "ocr"),
    (None, ".PDF", "pdf_text"),
    (None, ".JPEG", "ocr"),
    ("something_else", ".csv", "other"),
    (None, "", "other"),
])
def test_input_kind_prefers_the_engine_method_then_the_suffix(method, suffix, expected):
    assert input_kind(method, suffix) == expected


def test_gauges_report_admission_counters_and_draining_flag(monkeypatch):
    gate = Admission(max_inflight=1, max_queue=2)
    gate.try_start(gate.admit(5, 2))
    gate.admit(3, 0)
    gate.start_drain()
    monkeypatch.setattr(adm, "current", gate)

    values = metrics.gauges()

    assert (values["openbooks_inflight_jobs"], values["openbooks_queued_jobs"]) == (1, 1)
    assert (values["openbooks_inflight_bytes"], values["openbooks_inflight_ocr_pages"]) == (8, 2)
    assert values["openbooks_draining"] == 1


def test_process_memory_is_read_from_proc_statm(monkeypatch, tmp_path):
    statm = tmp_path / "statm"
    statm.write_text("100 25 3 1 0 2 0\n")
    monkeypatch.setattr(metrics, "_PROC_STATM", statm)
    monkeypatch.setattr(os, "sysconf", lambda name: 4096, raising=False)

    gauges = metrics._process_gauges()

    assert gauges["process_resident_memory_bytes"] == 25 * 4096


def test_process_memory_gauge_is_omitted_when_statm_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(metrics, "_PROC_STATM", tmp_path / "absent")

    assert "process_resident_memory_bytes" not in metrics._process_gauges()


def test_cuda_gauge_is_omitted_when_torch_was_never_imported(monkeypatch):
    monkeypatch.delitem(sys.modules, "torch", raising=False)

    assert "openbooks_cuda_max_allocated_bytes" not in metrics._process_gauges()


def test_metrics_response_has_the_prometheus_content_type():
    response = metrics_response()

    assert response.media_type == "text/plain; version=0.0.4; charset=utf-8"
