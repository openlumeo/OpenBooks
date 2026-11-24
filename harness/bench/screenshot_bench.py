"""Measure screenshot verification on generated bank transactions with known ground truth."""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path

from openbooks.core import Params, process
from openbooks.statements.pdf_front import last_ocr_engines
from openbooks.statements.ocr_providers import ALLOW_REMOTE_ENV, PROVIDER_ENV, tesseract_available
from PIL import Image, ImageDraw, ImageFont

ROWS = (
    ("2026-11-01", "Groceries", "debit", "50.00", "950.00"),
    ("2026-11-02", "Deposit", "credit", "250.00", "1200.00"),
    ("2026-11-04", "Transport", "debit", "20.00", "1180.00"),
    ("2026-11-05", "Electricity", "debit", "80.00", "1100.00"),
)
CASES = ("desktop", "cropped", "dark", "downscaled", "tampered")
EXPECTED_REFUSALS = {"cropped", "tampered"}


def screenshot(case: str, path: Path) -> None:
    background, text, header = ("#131919", "#f5f9f7", "#263733") if case == "dark" else ("#ffffff", "#192724", "#e4ece8")
    image = Image.new("RGB", (1420, 570), background)
    canvas = ImageDraw.Draw(image)
    normal, title = ImageFont.load_default(size=28), ImageFont.load_default(size=42)
    canvas.text((48, 32), "Account activity", font=title, fill=text)
    if case != "cropped":
        canvas.text((48, 105), "USD   Opening Balance 1000.00", font=normal, fill=text)
    canvas.rectangle((32, 166, 1388, 218), fill=header)
    columns = (48, 260, 700, 940, 1180)
    for x, heading in zip(columns, ("Date", "Description", "Debit", "Credit", "Balance")):
        canvas.text((x, 175), heading, font=normal, fill=text)
    for number, (date, description, direction, amount, balance) in enumerate(ROWS):
        y = 242 + number * 64
        shown_balance = "1101.00" if case == "tampered" and number == len(ROWS) - 1 else balance
        for x, cell in zip(columns, (date, description, amount if direction == "debit" else "",
                                      amount if direction == "credit" else "", shown_balance)):
            canvas.text((x, y), cell, font=normal, fill=text)
    if case != "cropped":
        canvas.text((48, 510), "Closing Balance 1100.00", font=normal, fill=text)
    if case == "downscaled":
        image = image.resize((710, 285), Image.Resampling.LANCZOS)
    image.save(path)


def exact_fields(document: dict) -> tuple[int, int]:
    data = document.get("data", {})
    batch = next(iter(data.get("batches", [])), {})
    actual = [batch.get("opening", {}).get("amount"), batch.get("closing", {}).get("amount"), batch.get("currency")]
    expected = ["1000.00", "1100.00", "USD"]
    transactions = data.get("transactions", [])
    for index, (date, _description, direction, amount, balance) in enumerate(ROWS):
        row = transactions[index] if index < len(transactions) else {}
        actual.extend((row.get("date"), row.get("direction"), row.get("amount", {}).get("amount"),
                       row.get("balance_after", {}).get("amount")))
        expected.extend((date, direction, amount, balance))
    return sum(a == b for a, b in zip(actual, expected)) + (len(transactions) == len(ROWS)), len(expected) + 1


def run_case(case: str, path: Path, model: bool) -> dict:
    start = time.perf_counter()
    doc = process(path, Params(currency="USD", model=model))
    elapsed = time.perf_counter() - start
    expected_release = case not in EXPECTED_REFUSALS
    released = doc.get("status") == "ok"
    matched, total = exact_fields(doc) if expected_release else (0, 0)
    return {"case": case, "status": "released" if released else "refused",
            "reason": (doc.get("error") or {}).get("code"), "expected": "released" if expected_release else "refused",
            "wrong_release": released and (not expected_release or matched != total),
            "matched_fields": matched, "expected_fields": total, "seconds": round(elapsed, 4),
            "ocr_engines": last_ocr_engines()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--model", action="store_true", help="enable the package's typed-role model cross-check")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "bench-out")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    os.environ[PROVIDER_ENV] = "tesseract"
    os.environ.pop(ALLOW_REMOTE_ENV, None)
    available, engine_version = tesseract_available()
    if not available:
        parser.exit(1, f"{engine_version}\n")
    with tempfile.TemporaryDirectory(prefix="openbooks-screen-") as directory:
        paths = {case: Path(directory) / f"{case}.png" for case in CASES}
        for case, path in paths.items():
            screenshot(case, path)
        observations = [run_case(case, path, args.model) for _ in range(args.repeats) for case, path in paths.items()]
    if not all(row["ocr_engines"] == ("tesseract",) for row in observations):
        parser.exit(1, "one or more screenshot runs did not reach the OCR engine\n")
    times = sorted(row["seconds"] for row in observations)
    correct = sum(row["status"] == row["expected"] and not row["wrong_release"] for row in observations)
    report = {"schema": "screenshot-bench.v1", "corpus": "synthetic bank transaction screenshots", "model": args.model,
              "tesseract": engine_version, "os": platform.system(), "logical_cpus": os.cpu_count(),
              "repeats": args.repeats, "observations": observations, "summary": {
                  "runs": len(observations), "correct_decisions": correct,
                  "wrong_releases": sum(row["wrong_release"] for row in observations),
                  "matched_fields": sum(row["matched_fields"] for row in observations),
                  "expected_fields": sum(row["expected_fields"] for row in observations),
                  "p50_s": statistics.median(times), "p95_s": times[math.ceil(.95 * len(times)) - 1],
                  "serial_images_per_second": round(len(times) / max(sum(times), 1e-9), 3)}}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "screenshot-bench.v1.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
