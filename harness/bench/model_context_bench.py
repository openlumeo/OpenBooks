"""Compare model token use on identical screenshot tasks using Open Books and LiteParse context."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from functools import partial
from pathlib import Path

from openbooks.core import Params, process
from openbooks.statements.ocr_providers import ALLOW_REMOTE_ENV, PROVIDER_ENV

from .screenshot_bench import CASES, EXPECTED_REFUSALS, screenshot

QUESTION = (
    'Return status, currency, opening, closing and count as JSON. '
    'If the evidence already supplies a verified JSON result, copy its five fields exactly. '
    'Otherwise, summarize the statement using its printed opening, closing, currency and transaction count. '
    'For the count, include only rows starting with a YYYY-MM-DD date. Exclude balance summaries and headers. '
    'If opening is missing or the running and stated closing balances disagree, set status to refused and all other fields to null. '
    'Otherwise set status to released.\n\nEvidence:\n'
)
REFUSED = {"status": "refused", "currency": None, "opening": None, "closing": None, "count": None}
RELEASED = {"status": "released", "currency": "USD", "opening": "1000.00", "closing": "1100.00", "count": 4}
TARGET_SAVINGS = 0.20
CLOSING_QUESTION = 'Return the statement closing balance as JSON with one numeric key, closing. Read the printed Closing Balance.\n\nEvidence:\n'
CLOSING_SCHEMA = {"type": "object", "properties": {"closing": {"type": "number"}},
                  "required": ["closing"], "additionalProperties": False}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"status": {"enum": ["released", "refused"]}, "currency": {"type": ["string", "null"]},
                   "opening": {"type": ["number", "null"]}, "closing": {"type": ["number", "null"]},
                   "count": {"type": ["integer", "null"]}},
    "required": ["status", "currency", "opening", "closing", "count"],
    "additionalProperties": False,
}


def compact(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def openbooks_context(path: Path) -> str:
    doc = process(path, Params(currency="USD"))
    if doc.get("status") != "ok":
        return compact(REFUSED)
    data = doc["data"]
    batch = data["batches"][0]
    return compact({"status": "released", "currency": batch["currency"], "opening": float(batch["opening"]["amount"]),
                    "closing": float(batch["closing"]["amount"]), "count": len(data["transactions"])})


def liteparse_context(command: str, path: Path, tessdata: Path | None, output_format: str) -> str:
    argv = [command, "parse", str(path), "--quiet", "--format", output_format, "--ocr-backend", "tesseract",
            "--num-workers", "1"]
    if output_format == "markdown":
        argv.extend(["--image-mode", "off"])
    if tessdata is not None:
        argv.extend(["--tessdata-path", str(tessdata)])
    result = subprocess.run(argv, capture_output=True, encoding="utf-8", timeout=60, check=True)
    if not result.stdout.strip():
        raise RuntimeError("LiteParse returned empty context")
    return result.stdout.strip()


def hosted_llamaparse(client, path: Path, version: str) -> str:
    """Parse one generated fixture. Hosted calls are enabled explicitly by the runner."""
    try:
        uploaded = client.files.create(file=path, purpose="parse")
        result = client.parsing.parse(file_id=uploaded.id, tier="agentic", version=version, expand=["markdown"])
        context = "\n\n".join(page.markdown for page in result.markdown.pages if page.markdown).strip()
    except Exception as error:
        raise RuntimeError(f"LlamaParse fixture request failed ({type(error).__name__})") from None
    if not context:
        raise RuntimeError("LlamaParse returned empty context")
    return context


def correct_answer(raw: str, expected: dict) -> bool:
    try:
        actual = json.loads(raw)
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            return False
        for field in (expected.keys() & {"opening", "closing"}):
            if actual[field] is not None:
                if expected[field] is None or Decimal(str(actual[field])) != Decimal(expected[field]):
                    return False
                actual[field] = expected[field]
        return actual == expected and (actual.get("count") is None or type(actual["count"]) is int)
    except (ValueError, TypeError, InvalidOperation):
        return False


def run_pair(model, path: Path, case: str, liteparse: str, tessdata: Path | None,
             hosted: Callable[[Path], str] | None, task: str) -> list[dict]:
    contexts = {"openbooks": openbooks_context(path), **{
        f"liteparse_{fmt}": liteparse_context(liteparse, path, tessdata, fmt) for fmt in ("markdown", "text")}}
    if hosted is not None:
        contexts["llamaparse_agentic"] = hosted(path)
    expected = REFUSED if case in EXPECTED_REFUSALS else RELEASED
    question, schema = QUESTION, ANSWER_SCHEMA
    if task == "closing":
        question, schema, expected = CLOSING_QUESTION, CLOSING_SCHEMA, {"closing": RELEASED["closing"]}
        contexts["openbooks"] = compact({"closing": json.loads(contexts["openbooks"]).get("closing")})
    rows = []
    for arm, context in contexts.items():
        model.reset()
        result = model.create_chat_completion(
            messages=[{"role": "user", "content": question + context}],
            response_format={"type": "json_object", "schema": schema}, temperature=0, max_tokens=160,
        )
        answer = result["choices"][0]["message"]["content"] or ""
        rows.append({"case": case, "arm": arm, "document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "input_tokens": result["usage"]["prompt_tokens"], "output_tokens": result["usage"]["completion_tokens"],
                     "correct": correct_answer(answer, expected), "context": context, "expected": expected, "answer": answer})
    return rows


def summarize(rows: list[dict]) -> dict:
    correct = sum(row["correct"] for row in rows)
    prompt = sum(row["input_tokens"] for row in rows)
    completion = sum(row["output_tokens"] for row in rows)
    return {"cases": len(rows), "correct_answers": correct, "input_tokens": prompt, "output_tokens": completion,
            "total_tokens": prompt + completion, "tokens_per_correct_answer": (prompt + completion) / correct if correct else None}


def compare(openbooks: dict, baseline: dict, compact_rows: list[dict], baseline_rows: list[dict]) -> dict:
    compact_cost = openbooks["tokens_per_correct_answer"]
    baseline_cost = baseline["tokens_per_correct_answer"]
    reduction = 1 - compact_cost / baseline_cost if compact_cost is not None and baseline_cost else None
    common = [(first, second) for first, second in zip(compact_rows, baseline_rows)
              if first["case"] == second["case"] and first["correct"] and second["correct"]]
    compact_common = sum(first["input_tokens"] + first["output_tokens"] for first, _ in common)
    baseline_common = sum(second["input_tokens"] + second["output_tokens"] for _, second in common)
    return {"total_token_reduction": 1 - openbooks["total_tokens"] / baseline["total_tokens"],
            "token_reduction_per_correct_answer": reduction,
            "cases_both_correct": len(common),
            "token_reduction_on_cases_both_correct": 1 - compact_common / baseline_common if baseline_common else None,
            "meets_target": reduction is not None and reduction >= TARGET_SAVINGS
            and openbooks["correct_answers"] >= baseline["correct_answers"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="local Qwen GGUF file")
    parser.add_argument("--liteparse", default="lit", help="path to the LiteParse executable")
    parser.add_argument("--tessdata", type=Path)
    parser.add_argument("--task", choices=("summary", "closing"), default="summary")
    parser.add_argument("--llamaparse-version", help="opt in to sending generated fixtures to LlamaParse Agentic using a pinned version")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "bench-out")
    args = parser.parse_args()

    from llama_cpp import Llama

    hosted: Callable[[Path], str] | None = None
    if args.llamaparse_version:
        if args.llamaparse_version.lower() == "latest" or not os.environ.get("LLAMA_CLOUD_API_KEY"):
            parser.error("hosted LlamaParse needs a pinned version and LLAMA_CLOUD_API_KEY")
        from llama_cloud import LlamaCloud

        hosted = partial(hosted_llamaparse, LlamaCloud(), version=args.llamaparse_version)

    os.environ[PROVIDER_ENV] = "tesseract"
    os.environ.pop(ALLOW_REMOTE_ENV, None)
    version = subprocess.run([args.liteparse, "--version"], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    with args.model.open("rb") as weights:
        model_hash = hashlib.file_digest(weights, "sha256").hexdigest()
    model = Llama(str(args.model), n_ctx=2048, n_threads=4, n_gpu_layers=0, chat_format="chatml", seed=7, verbose=False)
    rows = []
    with tempfile.TemporaryDirectory(prefix="openbooks-model-context-") as directory:
        for case in CASES:
            if args.task == "closing" and case in EXPECTED_REFUSALS:
                continue
            path = Path(directory) / f"{case}.png"
            screenshot(case, path)
            rows.extend(run_pair(model, path, case, args.liteparse, args.tessdata, hosted, args.task))

    arms = ("openbooks", "liteparse_markdown", "liteparse_text")
    if hosted is not None:
        arms += ("llamaparse_agentic",)
    by_arm = {arm: [row for row in rows if row["arm"] == arm] for arm in arms}
    summary = {arm: summarize(samples) for arm, samples in by_arm.items()}
    comparisons = {arm: compare(summary["openbooks"], summary[arm], by_arm["openbooks"], by_arm[arm]) for arm in arms[1:]}
    report = {"schema": "model-context-bench.v1", "model": args.model.name, "model_sha256": model_hash, "liteparse": version,
              "task": args.task, "instructions": CLOSING_QUESTION if args.task == "closing" else QUESTION,
              "answer_schema": CLOSING_SCHEMA if args.task == "closing" else ANSWER_SCHEMA,
              "generation": {"temperature": 0, "max_tokens": 160, "format": "json_object"},
              "target_savings": TARGET_SAVINGS, "llamaparse_version": args.llamaparse_version,
              "summary": summary, "comparisons": comparisons, "observations": rows}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "model-context-bench.v1.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "comparisons": comparisons}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
