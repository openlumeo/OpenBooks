import json
import math
import traceback
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from openbooks.core import Params, process
from openbooks.core.errors import EngineFault
from openbooks.statements import ocr_cloud as cloud
from openbooks.statements import ocr_providers as ocr
from openbooks.statements.pdf_words import Word

PAGE_SIZE = (612.0, 792.0)
FAKE_KEY = "test-fake-key-not-real-0123456789abcdef"
AZURE_ENDPOINT = "https://docs.example.test"
AZURE_LOCATION = f"{AZURE_ENDPOINT}/documentintelligence/documentModels/prebuilt-read/analyzeResults/1"
AZURE_ENV = {"AZURE_DOCINTEL_KEY": FAKE_KEY, "AZURE_DOCINTEL_ENDPOINT": AZURE_ENDPOINT}
AZURE_CFG = ocr.ProviderConfig("azure", "azure_docintel", {"key": "AZURE_DOCINTEL_KEY", "endpoint": "AZURE_DOCINTEL_ENDPOINT"}, {}, True)
AZURE_RESULT = {"status": "succeeded", "analyzeResult": {"pages": [{"unit": "pixel", "words": [
    {"content": "Opening", "polygon": [20, 40, 60, 40, 60, 60, 20, 60], "confidence": 0.98},
    {"content": "   ", "polygon": [0, 0, 1, 0, 1, 1, 0, 1], "confidence": 0.5},
]}]}}
TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


class FakeEngine:
    preferred_dpi = 300

    def __init__(self, engine_id: str, script: Callable[[int], list[Word]], remote: bool = False) -> None:
        self.id = engine_id
        self.remote = remote
        self.script = script
        self.calls: list[int] = []

    def read_page(self, image: Any, scale: float, page_number: int, page_size: tuple[float, float]) -> list[Word]:
        self.calls.append(page_number)
        return self.script(page_number)


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    monkeypatch.setattr(ocr, "_REGISTRY", dict(ocr._REGISTRY))


@pytest.fixture
def no_png(monkeypatch):
    monkeypatch.setattr(cloud, "encode_png", lambda image: b"\x89PNG-fake")


def add_engine(name: str, script: Callable[[int], list[Word]], remote: bool = False) -> FakeEngine:
    engine = FakeEngine(name, script, remote)
    ocr.register_engine(name, lambda config, environ: engine)
    return engine


def word(text: str, page: int = 1, x: float = 10.0) -> Word:
    return Word(text, x, 20.0, x + 40.0, 30.0, page, 0.9, *PAGE_SIZE)


def serve(prefix: str) -> Callable[[int], list[Word]]:
    return lambda page: [word(f"{prefix}{page}", page)]


def fails_on_page_two(page: int) -> list[Word]:
    if page == 2:
        raise ocr.ProviderError("boom")
    return [word(f"a{page}", page)]


def unavailable_on_page_two(page: int) -> list[Word]:
    if page == 2:
        raise ocr.ProviderUnavailable("down")
    return [word(f"a{page}", page)]


def always_unavailable(page: int) -> list[Word]:
    raise ocr.ProviderUnavailable("down")


def empty_page(page: int) -> list[Word]:
    return []


def pages(count: int) -> list[ocr.PageInput]:
    return [ocr.PageInput(None, 1.0, n, PAGE_SIZE) for n in range(1, count + 1)]


def cfg(provider_id: str, engine: str, *, remote: bool = False, env: dict[str, str] | None = None,
        options: dict[str, str] | None = None) -> ocr.ProviderConfig:
    return ocr.ProviderConfig(provider_id, engine, dict(env or {}), dict(options or {}), remote)


def settings(*configs: ocr.ProviderConfig, default: str = "a", fallback: str | None = None,
             allow_remote: bool = True) -> ocr.ProviderSettings:
    return ocr.ProviderSettings(default, fallback, allow_remote, {c.id: c for c in configs})


def primary_and_fallback() -> ocr.ProviderSettings:
    return settings(cfg("a", "fake_a"), cfg("b", "fake_b"), default="a", fallback="b")


def write_toml(tmp_path: Path, text: str, name: str = "providers.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_empty_file_loads_documented_defaults(tmp_path):
    loaded = ocr.load_settings(write_toml(tmp_path, ""), {})
    assert (loaded.default, loaded.fallback, loaded.providers) == ("tesseract", None, {})


@pytest.mark.parametrize("value", ["sk-" + "a" * 40, "AIza" + "b" * 35, "xai-" + "c" * 30,
                                   "-----BEGIN PRIVATE KEY-----", "Q" * 40])
def test_secret_looking_value_in_toml_is_rejected_without_echoing_it(tmp_path, value):
    path = write_toml(tmp_path, f'[providers.azure.env]\nkey = "{value}"\n')
    with pytest.raises(ocr.ConfigError) as info:
        ocr.load_settings(path, {})
    assert value not in str(info.value)


def test_toml_in_working_directory_is_ignored(tmp_path, monkeypatch):
    write_toml(tmp_path, 'default = "azure"\nallow_remote = true\n', name=ocr.PROVIDERS_FILENAME)
    monkeypatch.chdir(tmp_path)
    loaded = ocr.load_settings(None, {})
    assert loaded.default == "tesseract" and loaded.allow_remote is False


def test_providers_file_named_by_environment_is_honoured(tmp_path):
    path = write_toml(tmp_path, 'default = "custom"\n')
    assert ocr.load_settings(None, {ocr.PROVIDERS_FILE_ENV: str(path)}).default == "custom"


def test_environment_provider_beats_toml_default():
    add_engine("fake_a", serve("a"))
    add_engine("fake_b", serve("b"))
    assert ocr.select_engine(primary_and_fallback(), {ocr.PROVIDER_ENV: "b"}).id == "fake_b"


def test_toml_default_is_used_when_environment_is_silent():
    add_engine("fake_a", serve("a"))
    assert ocr.select_engine(primary_and_fallback(), {}).id == "fake_a"


def test_tesseract_is_selected_when_nothing_is_configured(monkeypatch):
    monkeypatch.setattr(ocr, "_resolve_tesseract", lambda environ, cmd_env=ocr.TESSERACT_CMD_ENV: "tesseract-stub")
    selected = ocr.select_engine(settings(default="tesseract"), {})
    assert isinstance(selected, ocr.TesseractEngine) and selected.id == "tesseract"


def test_missing_env_variable_is_unavailable_and_names_only_the_variable():
    add_engine("fake_a", serve("a"))
    configured = settings(cfg("k", "fake_a", env={"key": "FAKE_KEY_NAME"}), default="k")
    with pytest.raises(ocr.ProviderUnavailable) as info:
        ocr.select_engine(configured, {})
    assert "FAKE_KEY_NAME" in str(info.value)


@pytest.mark.parametrize("options", [{"lang": "eng; rm -rf"}, {"lang": ""}, {"psm": "14"}, {"psm": "x"}])
def test_tesseract_lang_and_psm_outside_the_allowed_shape_are_refused(options):
    with pytest.raises(ocr.ConfigError):
        ocr.TesseractEngine(cfg("t", "tesseract", options=options), {})


def test_cloud_engine_is_refused_without_remote_env_even_when_toml_says_local():
    configured = settings(cfg("az", "azure_docintel", remote=False), default="az")
    with pytest.raises(ocr.CapabilityRefused):
        ocr.select_engine(configured, {})


@pytest.mark.parametrize("flag", ["", "0", "true", "yes"])
def test_remote_gate_only_opens_for_the_exact_value_one(flag):
    configured = settings(cfg("az", "azure_docintel", remote=True, env={"key": "AZURE_DOCINTEL_KEY"}), default="az")
    with pytest.raises(ocr.CapabilityRefused):
        ocr.select_engine(configured, {ocr.ALLOW_REMOTE_ENV: flag, **AZURE_ENV})


def test_toml_allow_remote_false_blocks_even_with_the_environment_opt_in():
    configured = settings(AZURE_CFG, default="azure", allow_remote=False)
    with pytest.raises(ocr.CapabilityRefused):
        ocr.select_engine(configured, {ocr.ALLOW_REMOTE_ENV: "1", **AZURE_ENV})


def test_cloud_engine_is_built_only_when_both_gates_and_its_env_are_open():
    configured = settings(AZURE_CFG, default="azure")
    assert isinstance(ocr.select_engine(configured, {ocr.ALLOW_REMOTE_ENV: "1", **AZURE_ENV}), cloud.AzureDocIntelEngine)


def test_provider_error_raises_engine_fault_with_no_partial_words_and_no_fallback():
    primary = add_engine("fake_a", fails_on_page_two)
    fallback = add_engine("fake_b", serve("b"))
    with pytest.raises(EngineFault):
        ocr.ocr_pages(pages(2), primary_and_fallback(), {})
    assert primary.calls == [1, 2] and fallback.calls == []


def test_unavailable_primary_after_first_page_fails_closed_and_never_mixes_engines():
    primary = add_engine("fake_a", unavailable_on_page_two)
    fallback = add_engine("fake_b", serve("b"))
    with pytest.raises(EngineFault):
        ocr.ocr_pages(pages(2), primary_and_fallback(), {})
    assert primary.calls == [1, 2] and fallback.calls == []


def test_capability_refusal_never_falls_back():
    def refuse(page: int) -> list[Word]:
        raise ocr.CapabilityRefused("not allowed")

    add_engine("fake_a", refuse)
    fallback = add_engine("fake_b", serve("b"))
    with pytest.raises(ocr.CapabilityRefused):
        ocr.ocr_pages(pages(1), primary_and_fallback(), {})
    assert fallback.calls == []


def test_unavailable_fallback_raises_engine_fault_and_releases_nothing():
    add_engine("fake_a", always_unavailable)
    add_engine("fake_b", always_unavailable)
    with pytest.raises(EngineFault):
        ocr.ocr_pages(pages(1), primary_and_fallback(), {})


def test_blank_page_returns_no_words_instead_of_faulting_the_document():
    add_engine("fake_a", empty_page)
    run = ocr.ocr_pages(pages(2), primary_and_fallback(), {})
    assert run.pages == [[], []]
    assert ocr.read_page_with(FakeEngine("fake_a", empty_page), None, 1.0, 1, PAGE_SIZE) == []


def test_slightly_negative_edge_coordinates_are_accepted():
    edge = replace(word("x"), x0=-0.5, y0=-0.5)
    words = ocr.read_page_with(FakeEngine("fake_a", lambda page: [edge]), None, 1.0, 1, PAGE_SIZE)
    assert words == [edge]


def test_local_engines_run_one_page_at_a_time_by_default():
    slot = ocr._engine_slot("local_only_engine", False, {})
    assert slot.acquire(blocking=False) is True
    assert slot.acquire(blocking=False) is False
    slot.release()


@pytest.mark.parametrize("bad", [replace(word("x"), x1=5.0), replace(word("x"), conf=1.5),
                                 replace(word("x"), x0=math.nan)])
def test_malformed_ocr_word_is_refused(bad):
    with pytest.raises(ocr.ProviderError):
        ocr.read_page_with(FakeEngine("fake_a", lambda page: [bad]), None, 1.0, 1, PAGE_SIZE)


def test_key_never_appears_in_exception_text_repr_or_traceback():
    def leaking(page: int) -> list[Word]:
        raise RuntimeError(f"upstream echoed {FAKE_KEY}")

    add_engine("fake_a", leaking)
    configured = settings(cfg("k", "fake_a", env={"key": "FAKE_KEY_NAME"}), default="k")
    with pytest.raises(EngineFault) as info:
        ocr.ocr_pages(pages(1), configured, {"FAKE_KEY_NAME": FAKE_KEY})
    assert FAKE_KEY not in str(info.value) and FAKE_KEY not in repr(info.value)
    assert FAKE_KEY not in "".join(traceback.format_exception(info.value))


def test_redact_secrets_replaces_every_occurrence_longest_secret_first():
    assert ocr.redact_secrets("abc-secret-long and secret", ["secret", "abc-secret-long", ""]) == "[REDACTED] and [REDACTED]"


@pytest.mark.parametrize("value,expected", [
    ("sk-" + "a" * 30, True), ("AIza" + "b" * 30, True), ("-----BEGIN RSA PRIVATE KEY", True),
    ("A" * 40, True), ("AZURE_DOCINTEL_KEY", False), ("https://docs.example.test", False), ("eng", False),
])
def test_looks_like_secret_recognises_key_shapes(value, expected):
    assert ocr.looks_like_secret(value) is expected


def tsv_row(left: float, top: int, width: int, height: int, conf: int, text: str) -> str:
    return f"5\t1\t1\t1\t1\t1\t{left}\t{top}\t{width}\t{height}\t{conf}\t{text}"


def test_tesseract_tsv_keeps_word_rows_divides_boxes_by_scale_and_scales_confidence():
    tsv = "\n".join([TSV_HEADER, tsv_row(100, 200, 50, 20, 96, "1000.00"), "4\t1\t1\t1\t1\t0\t0\t0\t0\t0\t-1\t"])
    words = ocr.parse_tesseract_tsv(tsv, 2.0, 3, PAGE_SIZE)
    assert [(w.text, w.x0, w.y0, w.x1, w.y1, w.page) for w in words] == [("1000.00", 50.0, 100.0, 75.0, 110.0, 3)]
    assert words[0].conf == pytest.approx(0.96)


def test_tesseract_tsv_drops_negative_confidence_and_blank_text_rows():
    tsv = "\n".join([TSV_HEADER, tsv_row(0, 0, 10, 10, -1, "ghost"), tsv_row(0, 0, 10, 10, 90, "  "),
                     tsv_row(20, 0, 10, 10, 50, "kept")])
    words = ocr.parse_tesseract_tsv(tsv, 1.0, 1, PAGE_SIZE)
    assert [w.text for w in words] == ["kept"] and words[0].conf == pytest.approx(0.5)


class AzureTransport:
    def __init__(self, location: str, result: dict[str, Any]) -> None:
        self.location = location
        self.result = result
        self.requests: list[cloud.HttpRequest] = []

    def __call__(self, request: cloud.HttpRequest) -> cloud.HttpResponse:
        self.requests.append(request)
        if request.method == "POST":
            return cloud.HttpResponse(202, {"operation-location": self.location}, b"")
        return cloud.HttpResponse(200, {}, json.dumps(self.result).encode())


@pytest.mark.parametrize("model", ["prebuilt-read", "prebuilt-layout"])
def test_azure_canned_response_maps_pixel_polygons_to_point_boxes(no_png, model):
    transport = AzureTransport(AZURE_LOCATION, AZURE_RESULT)
    config = ocr.ProviderConfig(AZURE_CFG.id, AZURE_CFG.engine, AZURE_CFG.env, {"model": model}, remote=True)
    words = cloud.AzureDocIntelEngine(config, AZURE_ENV, transport).read_page(None, 2.0, 3, PAGE_SIZE)
    assert [(w.text, w.x0, w.y0, w.x1, w.y1, w.page, w.conf) for w in words] == [("Opening", 10.0, 20.0, 30.0, 30.0, 3, 0.98)]
    assert transport.requests[0].headers["Ocp-Apim-Subscription-Key"] == FAKE_KEY
    assert f"/documentModels/{model}:analyze?" in transport.requests[0].url


def test_azure_operation_location_on_another_host_is_rejected_before_polling(no_png):
    transport = AzureTransport("https://attacker.example.net/poll", AZURE_RESULT)
    with pytest.raises(ocr.ProviderError, match="outside the configured endpoint"):
        cloud.AzureDocIntelEngine(AZURE_CFG, AZURE_ENV, transport).read_page(None, 2.0, 1, PAGE_SIZE)
    assert [r.method for r in transport.requests] == ["POST"]
    assert all(FAKE_KEY not in r.url for r in transport.requests)


def test_azure_error_text_traceback_and_status_never_contain_the_key(no_png):
    def leaking(request: cloud.HttpRequest) -> cloud.HttpResponse:
        raise RuntimeError(f"upstream echoed {FAKE_KEY}")

    def unauthorised(request: cloud.HttpRequest) -> cloud.HttpResponse:
        return cloud.HttpResponse(401, {}, FAKE_KEY.encode())

    with pytest.raises(ocr.ProviderError) as leaked:
        cloud.AzureDocIntelEngine(AZURE_CFG, AZURE_ENV, leaking).read_page(None, 2.0, 1, PAGE_SIZE)
    assert FAKE_KEY not in str(leaked.value) and FAKE_KEY not in "".join(traceback.format_exception(leaked.value))
    with pytest.raises(ocr.ProviderError, match="HTTP 401") as status:
        cloud.AzureDocIntelEngine(AZURE_CFG, AZURE_ENV, unauthorised).read_page(None, 2.0, 1, PAGE_SIZE)
    assert FAKE_KEY not in str(status.value)


def test_google_canned_response_maps_normalised_and_pixel_vertices_to_points(no_png):
    document = {"text": "Opening 1000.00", "pages": [{"tokens": [
        {"layout": {"textAnchor": {"textSegments": [{"startIndex": 0, "endIndex": 7}]},
                    "boundingPoly": {"normalizedVertices": [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.1},
                                                            {"x": 0.2, "y": 0.12}, {"x": 0.1, "y": 0.12}]},
                    "confidence": 0.97}},
        {"layout": {"textAnchor": {"textSegments": [{"startIndex": 8, "endIndex": 15}]},
                    "boundingPoly": {"vertices": [{"x": 100, "y": 200}, {"x": 160, "y": 200},
                                                  {"x": 160, "y": 220}, {"x": 100, "y": 220}]},
                    "confidence": 0.9}},
    ]}]}
    engine = cloud.GoogleDocAiEngine(
        cfg("google", "google_docai", remote=True, options={"location": "us", "project": "proj-p1", "processor": "x1"}),
        {"GOOGLE_DOCAI_ACCESS_TOKEN": FAKE_KEY},
        lambda request: cloud.HttpResponse(200, {}, json.dumps({"document": document}).encode()))
    words = engine.read_page(None, 2.0, 1, PAGE_SIZE)
    assert [w.text for w in words] == ["Opening", "1000.00"]
    assert (words[0].x0, words[0].y0, words[0].x1, words[0].y1) == pytest.approx((61.2, 79.2, 122.4, 95.04))
    assert (words[1].x0, words[1].y0, words[1].x1, words[1].y1) == (50.0, 100.0, 80.0, 110.0)
    assert words[1].conf == pytest.approx(0.9)


def test_google_out_of_range_normalised_coordinate_raises(no_png):
    document = {"text": "x", "pages": [{"tokens": [{"layout": {
        "textAnchor": {"textSegments": [{"startIndex": 0, "endIndex": 1}]},
        "boundingPoly": {"normalizedVertices": [{"x": 1.5, "y": 0.1}, {"x": 0.2, "y": 0.1}]},
        "confidence": 0.9}}]}]}
    engine = cloud.GoogleDocAiEngine(
        cfg("google", "google_docai", remote=True, options={"location": "us", "project": "proj-p1", "processor": "x1"}),
        {"GOOGLE_DOCAI_ACCESS_TOKEN": FAKE_KEY},
        lambda request: cloud.HttpResponse(200, {}, json.dumps({"document": document}).encode()))
    with pytest.raises(ocr.ProviderError):
        engine.read_page(None, 1.0, 1, PAGE_SIZE)


class FakeTextract:
    def __init__(self, blocks: list[dict[str, Any]]) -> None:
        self.blocks = blocks

    def detect_document_text(self, Document: dict[str, Any]) -> dict[str, Any]:
        return {"Blocks": self.blocks}


def textract_block(block_type: str, text: str, left: float, top: float, width: float, height: float) -> dict[str, Any]:
    return {"BlockType": block_type, "Text": text, "Confidence": 99.0,
            "Geometry": {"BoundingBox": {"Left": left, "Top": top, "Width": width, "Height": height}}}


def test_textract_canned_blocks_map_ratios_to_points_and_skip_non_word_blocks(no_png):
    blocks = [textract_block("WORD", "Opening", 0.1, 0.2, 0.1, 0.05),
              textract_block("LINE", "Opening 1000.00", 0.1, 0.2, 0.3, 0.05)]
    engine = cloud.TextractEngine(cfg("aws", "aws_textract", remote=True), {}, client=FakeTextract(blocks))
    words = engine.read_page(None, 1.0, 2, PAGE_SIZE)
    assert [w.text for w in words] == ["Opening"] and words[0].page == 2
    assert (words[0].x0, words[0].y0, words[0].x1, words[0].y1) == pytest.approx((61.2, 158.4, 122.4, 198.0))
    assert words[0].conf == pytest.approx(0.99)


def test_textract_out_of_range_ratio_raises(no_png):
    blocks = [textract_block("WORD", "Opening", 1.2, 0.2, 0.1, 0.05)]
    engine = cloud.TextractEngine(cfg("aws", "aws_textract", remote=True), {}, client=FakeTextract(blocks))
    with pytest.raises(ocr.ProviderError):
        engine.read_page(None, 1.0, 1, PAGE_SIZE)


@pytest.mark.parametrize("engine_name,env_name", [("mistral_ocr", "MISTRAL_API_KEY"),
                                                  ("llamaparse", "LLAMA_CLOUD_API_KEY")])
def test_mistral_and_llamaparse_refuse_word_boxes_and_never_fall_back(engine_name, env_name):
    configured = settings(cfg("m", engine_name, remote=True, env={"key": env_name}),
                          cfg("b", "fake_b"), default="m", fallback="b")
    fallback = add_engine("fake_b", serve("b"))
    with pytest.raises(ocr.CapabilityRefused):
        ocr.ocr_pages(pages(1), configured, {ocr.ALLOW_REMOTE_ENV: "1", env_name: FAKE_KEY})
    assert fallback.calls == []


def test_tampered_figure_from_fake_ocr_ends_in_balance_mismatch_not_release(tmp_path, monkeypatch):
    pytest.importorskip("pypdfium2")
    from openbooks.statements.pdf_backend import PdfPage, open_document
    from pdfmaker import pdf_bytes, statement_pdf

    genuine_pdf = tmp_path / "genuine.pdf"
    genuine_pdf.write_bytes(statement_pdf(closing="1295.00"))
    doc = open_document(genuine_pdf)
    try:
        layer = next(iter(doc.pages())).words()
    finally:
        doc.close()
    genuine_words = [Word(t, x0, y0, x1, y1, 1, 0.9, *PAGE_SIZE) for t, x0, y0, x1, y1 in layer]
    tampered_words = [replace(w, text="200.51") if w.text == "200.50" else w for w in genuine_words]
    assert tampered_words != genuine_words

    monkeypatch.setattr(PdfPage, "render_rgb", lambda self, scale: None)
    served: dict[str, list[Word]] = {"words": genuine_words}
    add_engine("fake_ocr", lambda page: served["words"] if page == 1 else [])
    toml = write_toml(tmp_path, 'default = "fake"\n\n[providers.fake]\nengine = "fake_ocr"\nremote = false\n')
    monkeypatch.setenv(ocr.PROVIDERS_FILE_ENV, str(toml))
    monkeypatch.delenv(ocr.PROVIDER_ENV, raising=False)
    monkeypatch.delenv(ocr.ALLOW_REMOTE_ENV, raising=False)
    scan = tmp_path / "scan.pdf"
    scan.write_bytes(pdf_bytes([b""]))

    control = process(scan, Params(currency="INR", date_order="dmy"))
    assert control["status"] == "ok", control.get("error")

    served["words"] = tampered_words
    refused = process(scan, Params(currency="INR", date_order="dmy"))
    assert refused["status"] == "refused" and refused["error"]["code"] == "BALANCE_MISMATCH"
