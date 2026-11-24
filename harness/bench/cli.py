from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from bench import runner
from bench.mcp_client import CALL_TIMEOUT_S, DEFAULT_MCP_COMMAND, split_command
from bench.providers import ProviderError, make_provider

PROVIDERS = ("anthropic", "openai", "gemini", "compat")
TASKS_ROOT = Path(__file__).resolve().parent / "tasks"
DEFAULT_OUT = "bench-out"
DEFAULT_MAX_TURNS = 12
DEFAULT_MAX_COST_USD = 5.0
TOOL_TIMEOUT_HELP = (
    "seconds to wait for each MCP tool call (default {default}). PNG and handwriting tasks need the full timeout: "
    "OCR on a PNG can take minutes and several GB of memory, so do not lower it for those tasks."
)
COST_HELP = (
    "hard stop on estimated spend (default {default}). Spend is estimated from a built-in approximate price table "
    "(USD per 1M tokens, matched by provider/model prefix); unknown models use a conservative default of 15 in / 75 out. "
    "The cap is checked after every model reply, so the last reply can overshoot it."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m bench", description="Run the Open Books agent benchmark.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run tasks against a model and write a result bundle")
    run.add_argument("--provider", required=True, choices=PROVIDERS)
    run.add_argument("--model", required=True)
    run.add_argument(
        "--api-key-env",
        required=True,
        metavar="VAR",
        help="name of the environment variable holding the API key; the key is never accepted as a flag",
    )
    run.add_argument("--base-url", default=None, help="base URL, required for the compat provider")
    run.add_argument("--tasks", default="all", help="comma-separated task ids, or all")
    run.add_argument("--out", default=DEFAULT_OUT, type=Path, help=f"output folder (default {DEFAULT_OUT})")
    run.add_argument(
        "--mcp-command",
        default=DEFAULT_MCP_COMMAND,
        help=f"command that starts the Open Books MCP server; --root <workspace> is appended (default: {DEFAULT_MCP_COMMAND!r})",
    )
    run.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS, help=f"model turns per task (default {DEFAULT_MAX_TURNS})")
    run.add_argument("--max-cost-usd", type=float, default=DEFAULT_MAX_COST_USD, help=COST_HELP.format(default=f"{DEFAULT_MAX_COST_USD:.2f}"))
    run.add_argument(
        "--tool-timeout",
        type=float,
        default=CALL_TIMEOUT_S,
        metavar="SECONDS",
        help=TOOL_TIMEOUT_HELP.format(default=f"{CALL_TIMEOUT_S:g}"),
    )

    score = commands.add_parser("score", help="re-score a result bundle in place and rewrite its results.md")
    score.add_argument("result", type=Path, help="path to bench-result.v1.json")

    commands.add_parser("list", help="list the tasks in the kit")
    return parser


def _parse_task_ids(raw: str) -> list[str] | None:
    if raw.strip().lower() == "all":
        return None
    ids = [item.strip() for item in raw.split(",") if item.strip()]
    if not ids:
        raise runner.BenchError("--tasks needs at least one id or 'all'")
    return ids


def _run(args: argparse.Namespace) -> int:
    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        raise runner.BenchError(f"environment variable {args.api_key_env} is not set")
    if args.max_turns < 1:
        raise runner.BenchError("--max-turns must be at least 1")
    if args.max_cost_usd <= 0:
        raise runner.BenchError("--max-cost-usd must be positive")
    if args.tool_timeout <= 0:
        raise runner.BenchError("--tool-timeout must be positive")
    argv = split_command(args.mcp_command)
    if not argv:
        raise runner.BenchError("--mcp-command is empty")
    provider = make_provider(args.provider, args.model, api_key, args.base_url)
    config = runner.RunConfig(
        provider_name=args.provider,
        model=args.model,
        api_key=api_key,
        api_key_env=args.api_key_env,
        tasks_root=TASKS_ROOT,
        out_dir=args.out,
        mcp_argv=argv,
        max_turns=args.max_turns,
        max_cost_usd=args.max_cost_usd,
        task_ids=_parse_task_ids(args.tasks),
        progress=lambda line: print(line, flush=True),
        tool_timeout_s=args.tool_timeout,
    )
    bundle, path = runner.run_bench(config, provider)
    print(f"scores: {json.dumps(bundle['scores'], sort_keys=True)}", flush=True)
    print(f"wrote {path} and {path.parent / runner.SCORECARD_FILE}", flush=True)
    return 0


def _score(args: argparse.Namespace) -> int:
    bundle = runner.rescore(args.result, TASKS_ROOT)
    print(json.dumps(bundle["scores"], indent=2, sort_keys=True))
    return 0


def _list() -> int:
    tasks = runner.load_all_tasks(TASKS_ROOT)
    if not tasks:
        print(f"no tasks found in {TASKS_ROOT}")
        return 0
    for task in tasks.values():
        expect = task.task.get("expect") if isinstance(task.task.get("expect"), dict) else {}
        print(f"{task.id:<28} {str(task.task.get('category', '')):<12} {str(expect.get('outcome', '')):<9} {task.task.get('prompt', '')[:60]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "score":
            return _score(args)
        return _list()
    except (runner.BenchError, ProviderError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
