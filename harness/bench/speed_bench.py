from __future__ import annotations

import argparse
import dataclasses
import importlib
import io
import json
import math
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

SCHEMA = "speed-bench.v1"
OUT_FILENAME = "speed-bench.v1.json"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "data" / "raw" / "agami_indian_bank_statements" / "train"
DEFAULT_OUT = ROOT / "harness" / "bench-out"
SCANNED_GLOB = "*Scanned*/*.pdf"
TESSERACT_ENV = "OPENBOOKS_TESSERACT_CMD"
DEFAULT_TESSERACT = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
PREP_MODULE = "openbooks.statements.ocr_prep"
PREP_FUNCTION = "prepare_for_ocr"
RENDER_DPIS = (200, 300)
OCR_DPI = 300
PDF_POINTS_PER_INCH = 72
MAX_RENDER_PX = 3200
PSM = "6"
TESSERACT_VARIANTS = (("tesseract_omp_default", False), ("tesseract_omp_1", True))
WORKER_COUNTS = (1, 2, 4)
TESSERACT_TIMEOUT_S = 120
MS = 1000.0

Runner = Callable[[list[str], dict[str, str]], bytes]


@dataclass(frozen=True)
class Stage:
    name: str
    count: int
    p50_ms: float
    p95_ms: float
    mean_ms: float


@dataclass(frozen=True)
class Throughput:
    workers: int
    pages: int
    wall_s: float
    pages_per_s: float


@dataclass(frozen=True)
class Report:
    schema: str
    created_at: str
    machine: dict[str, Any]
    settings: dict[str, Any]
    stages: tuple[Stage, ...]
    throughput: tuple[Throughput, ...]


def nearest_rank(ordered: Sequence[float], share: float) -> float:
    return ordered[max(1, math.ceil(share * len(ordered))) - 1]


def summarize(name: str, values: Sequence[float]) -> Stage:
    ordered = sorted(values)
    p50, p95 = nearest_rank(ordered, 0.5), nearest_rank(ordered, 0.95)
    return Stage(name, len(ordered), round(p50, 3), round(p95, 3), round(statistics.fmean(ordered), 3))


def record(values: dict[str, list[float]], name: str, ms: float) -> None:
    values.setdefault(name, []).append(ms)


def timed(fn: Callable[..., Any], *args: Any) -> tuple[float, Any]:
    started = time.perf_counter()
    value = fn(*args)
    return (time.perf_counter() - started) * MS, value


def subprocess_runner(command: list[str], env: dict[str, str]) -> bytes:
    return subprocess.run(command, capture_output=True, check=True, env=env, timeout=TESSERACT_TIMEOUT_S).stdout


def tesseract_command(binary: str, image: Path) -> list[str]:
    return [binary, str(image), "stdout", "--psm", PSM, "tsv"]


def tesseract_env(omp_limit: bool) -> dict[str, str]:
    env = dict(os.environ)
    if omp_limit:
        env["OMP_THREAD_LIMIT"] = "1"
    else:
        env.pop("OMP_THREAD_LIMIT", None)
    return env


def resolve_tesseract(environ: Mapping[str, str]) -> str | None:
    configured = environ.get(TESSERACT_ENV) or shutil.which("tesseract")
    if configured:
        return configured
    return str(DEFAULT_TESSERACT) if DEFAULT_TESSERACT.is_file() else None


def machine_info(binary: str | None, runner: Runner) -> dict[str, Any]:
    version = "unavailable"
    if binary is not None:
        try:
            output = runner([binary, "--version"], dict(os.environ)).decode("utf-8", "replace").strip()
            version = output.splitlines()[0] if output else "unknown"
        except (OSError, subprocess.SubprocessError):
            version = "unavailable"
    return {"cpu_count": os.cpu_count(), "python": platform.python_version(), "platform": platform.platform(), "tesseract": version}


def sample_pdfs(fixtures: Path, limit: int, seed: int) -> list[Path]:
    pool = sorted(fixtures.glob(SCANNED_GLOB))
    return sorted(random.Random(seed).sample(pool, min(limit, len(pool))))


def render_page(document: Any, index: int, dpi: int) -> Image.Image:
    page = document[index]
    width, height = page.get_size()
    scale = min(dpi / PDF_POINTS_PER_INCH, MAX_RENDER_PX / max(width, height))
    return page.render(scale=scale).to_pil().convert("RGB")


def encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def load_prepare() -> Callable[[Image.Image], Any] | None:
    try:
        return getattr(importlib.import_module(PREP_MODULE), PREP_FUNCTION, None)
    except ImportError:
        return None


def measure_page(document: Any, index: int, binary: str, workdir: Path, prepare: Any, runner: Runner, values: dict[str, list[float]]) -> Path:
    ocr_image, ocr_png = None, b""
    for dpi in RENDER_DPIS:
        render_ms, image = timed(render_page, document, index, dpi)
        record(values, f"render_{dpi}dpi", render_ms)
        encode_ms, png = timed(encode_png, image)
        record(values, f"png_encode_{dpi}dpi", encode_ms)
        if dpi == OCR_DPI:
            ocr_image, ocr_png = image, png
    if prepare is not None:
        prepare_ms, _ = timed(prepare, ocr_image)
        record(values, "prepare_for_ocr", prepare_ms)
    path = workdir / f"{uuid.uuid4().hex}.png"
    path.write_bytes(ocr_png)
    for label, omp_limit in TESSERACT_VARIANTS:
        ms, _ = timed(runner, tesseract_command(binary, path), tesseract_env(omp_limit))
        record(values, label, ms)
    return path


def collect(pdfs: Sequence[Path], pages_per_doc: int, binary: str, workdir: Path, runner: Runner) -> tuple[dict[str, list[float]], list[Path]]:
    import pypdfium2 as pdfium

    values: dict[str, list[float]] = {}
    pngs: list[Path] = []
    prepare = load_prepare()
    for pdf in pdfs:
        document = pdfium.PdfDocument(str(pdf))
        for index in range(min(len(document), pages_per_doc)):
            pngs.append(measure_page(document, index, binary, workdir, prepare, runner, values))
        document.close()
    return values, pngs


def run_throughput(binary: str, pngs: Sequence[Path], worker_counts: Sequence[int], runner: Runner) -> tuple[Throughput, ...]:
    env = tesseract_env(True)
    results = []
    for workers in worker_counts:
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda image: runner(tesseract_command(binary, image), env), pngs))
        wall = max(time.perf_counter() - started, 1e-9)
        results.append(Throughput(workers, len(pngs), round(wall, 3), round(len(pngs) / wall, 3)))
    return tuple(results)


def build_report(settings: dict[str, Any], machine: dict[str, Any], values: Mapping[str, list[float]], throughput: tuple[Throughput, ...]) -> Report:
    stages = tuple(summarize(name, values[name]) for name in values)
    return Report(SCHEMA, datetime.now(timezone.utc).isoformat(timespec="seconds"), machine, settings, stages, throughput)


def render_markdown(report: Report) -> str:
    machine = report.machine
    head = f"Machine: {machine['cpu_count']} CPUs, Python {machine['python']}, {machine['tesseract']}"
    lines = [head, f"Pages: {report.settings['pages']} from {len(report.settings['documents'])} document(s), psm {PSM}", "", "| Stage | Count | p50 ms | p95 ms | mean ms |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {s.name} | {s.count} | {s.p50_ms} | {s.p95_ms} | {s.mean_ms} |" for s in report.stages]
    lines += ["", "| Workers | Pages | Wall s | Pages/s |", "|---:|---:|---:|---:|"]
    lines += [f"| {t.workers} | {t.pages} | {t.wall_s} | {t.pages_per_s} |" for t in report.throughput]
    return "\n".join(lines)


def write_report(report: Report, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / OUT_FILENAME
    path.write_text(json.dumps(dataclasses.asdict(report), indent=2) + "\n", encoding="utf-8")
    return path


def self_check() -> int:
    fake_tsv = b"level\tpage_num\ttext\n5\t1\tTOTAL\n"

    def fake_runner(command: list[str], env: dict[str, str]) -> bytes:
        assert command[command.index("--psm") + 1] == PSM and "tsv" in command
        return fake_tsv

    assert summarize("x", [1.0, 2.0, 3.0]).p50_ms == 2.0
    assert summarize("x", [float(v) for v in range(1, 21)]).p95_ms == 19.0
    assert tesseract_env(True)["OMP_THREAD_LIMIT"] == "1"
    assert tesseract_env(False).get("OMP_THREAD_LIMIT") is None
    values: dict[str, list[float]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "synthetic.png"
        ms, png = timed(encode_png, Image.new("RGB", (800, 1000), "white"))
        record(values, "png_encode_300dpi", ms)
        path.write_bytes(png)
        for _ in range(3):
            for label, omp_limit in TESSERACT_VARIANTS:
                ms, _ = timed(fake_runner, tesseract_command("tesseract", path), tesseract_env(omp_limit))
                record(values, label, ms)
        throughput = run_throughput("tesseract", [path] * 4, WORKER_COUNTS, fake_runner)
        assert len(throughput) == len(WORKER_COUNTS) and all(t.pages == 4 for t in throughput)
        settings = {"documents": ["synthetic/synthetic.png"], "pages": 1, "dpi": list(RENDER_DPIS), "psm": PSM}
        report = build_report(settings, machine_info(None, fake_runner), values, throughput)
        text = render_markdown(report)
        assert "| tesseract_omp_1 |" in text and "| Workers |" in text
        written = write_report(report, Path(tmp))
        assert json.loads(written.read_text(encoding="utf-8"))["schema"] == SCHEMA
    print("speed_bench self-check ok")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m bench.speed_bench", description="Stage timings for the scanned-PDF OCR path (no network).")
    parser.add_argument("--self-check", action="store_true", help="run a fake-runner check on a synthetic image and exit")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pages-per-doc", type=int, default=2)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="directory for speed-bench.v1.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_check:
        return self_check()
    binary = resolve_tesseract(os.environ)
    if binary is None:
        sys.stderr.write(f"tesseract not found; set {TESSERACT_ENV} or add it to PATH\n")
        return 2
    pdfs = sample_pdfs(args.fixtures, args.limit, args.seed)
    if not pdfs:
        sys.stderr.write("no scanned PDFs found under the fixtures directory\n")
        return 2
    try:
        with tempfile.TemporaryDirectory() as tmp:
            values, pngs = collect(pdfs, args.pages_per_doc, binary, Path(tmp), subprocess_runner)
            throughput = run_throughput(binary, pngs, WORKER_COUNTS, subprocess_runner)
    except (OSError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"tesseract call failed: {type(error).__name__}\n")
        return 1
    documents = [f"{pdf.parent.name}/{pdf.name}" for pdf in pdfs]
    settings = {"documents": documents, "pages": len(pngs), "pages_per_doc": args.pages_per_doc, "limit": args.limit, "seed": args.seed}
    settings |= {"dpi": list(RENDER_DPIS), "max_long_side_px": MAX_RENDER_PX, "psm": PSM, "throughput_omp_thread_limit": 1}
    report = build_report(settings, machine_info(binary, subprocess_runner), values, throughput)
    path = write_report(report, args.out)
    sys.stdout.write(render_markdown(report) + f"\n\nwrote {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
