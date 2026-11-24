from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
DEFAULT_REPORT = HERE / "report.json"
DEFAULT_COMMAND = "npx -y -p @lumeo_hq/openbooks openbooks-mcp"
RESPONSE_BYTES = 48 * 1024
UPLOAD_BYTES = 1024 * 1024
EXPECTED_TOOLS = {"search", "execute"}
EXPECTED_RESOURCES = {
    "openbooks://schema/released",
    "openbooks://guide/refusals",
    "openbooks://samples/statement.csv",
}
EXPECTED_PROMPTS = {"verify_document", "explain_refusal", "try_sample"}
UPLOAD_ARGS = {"currency": "INR", "date_order": "dmy"}
Verdict = tuple[str, str, bool]
Check = tuple[str, str, Callable[[ClientSession, Path | None], Awaitable[Verdict]]]


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def encode(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def step(step_id: str, operation: str, **arguments: Any) -> dict[str, Any]:
    return {"id": step_id, "operation": operation, "arguments": arguments}


def server_parameters(command: str, extra: list[str]) -> StdioServerParameters:
    parts = shlex.split(command, posix=sys.platform != "win32")
    if not parts:
        raise ValueError("--command must not be empty")
    executable = shutil.which(parts[0]) or parts[0]
    return StdioServerParameters(command=executable, args=[*parts[1:], *extra])


async def execute(session: ClientSession, steps: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    result = await session.call_tool("execute", {"steps": steps, "stop_on_error": False})
    if result.is_error:
        raise RuntimeError("execute returned a tool error")
    text = result.content[0].text
    return json.loads(text), text


def result_code(item: dict[str, Any]) -> str:
    if "error" in item:
        return item["error"]["code"]
    result = item["result"]
    if result["status"] == "refused":
        return result["error"]["code"]
    return result["status"]


async def expect_code(session: ClientSession, steps: list[dict[str, Any]], index: int, expected: str) -> Verdict:
    response, _ = await execute(session, steps)
    actual = result_code(response["steps"][index])
    return expected, actual, actual == expected


async def check_tools(session: ClientSession, _root: Path | None) -> Verdict:
    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
    problems = []
    for name in EXPECTED_TOOLS:
        tool = tools.get(name)
        if tool is None:
            problems.append(f"{name} missing")
            continue
        if not tool.title:
            problems.append(f"{name} no title")
        if not (tool.annotations and tool.annotations.read_only_hint):
            problems.append(f"{name} not read-only")
        if not tool.output_schema:
            problems.append(f"{name} no output schema")
    actual = "tools=" + ",".join(sorted(tools)) + ("; " + "; ".join(problems) if problems else "")
    return "search and execute with title, readOnlyHint, outputSchema", actual, not problems and set(tools) == EXPECTED_TOOLS


async def check_resources(session: ClientSession, _root: Path | None) -> Verdict:
    listed = {str(item.uri) for item in (await session.list_resources()).resources}
    return ", ".join(sorted(EXPECTED_RESOURCES)), ", ".join(sorted(listed)), listed == EXPECTED_RESOURCES


async def check_prompts(session: ClientSession, _root: Path | None) -> Verdict:
    listed = {prompt.name for prompt in (await session.list_prompts()).prompts}
    return ", ".join(sorted(EXPECTED_PROMPTS)), ", ".join(sorted(listed)), listed == EXPECTED_PROMPTS


async def check_doctor(session: ClientSession, _root: Path | None) -> Verdict:
    response, _ = await execute(session, [step("doctor", "doctor")])
    report = response["steps"][0].get("result", {})
    self_test = report.get("self_test", {})
    actual = f"healthy={report.get('healthy')} self_test={self_test.get('status')}"
    passed = report.get("healthy") is True and self_test.get("released") is True and self_test.get("status") == "ok"
    return "healthy=True self_test=ok released", actual, passed


async def task_balanced_released(session: ClientSession, _root: Path | None) -> Verdict:
    steps = [step("s", "process_upload", filename="statement.csv", content_base64=encode(fixture("statement_balanced.csv")), opening="1000.00", **UPLOAD_ARGS)]
    return await expect_code(session, steps, 0, "ok")


async def task_balanced_without_opening(session: ClientSession, _root: Path | None) -> Verdict:
    steps = [step("s", "process_upload", filename="statement.csv", content_base64=encode(fixture("statement_balanced.csv")), **UPLOAD_ARGS)]
    return await expect_code(session, steps, 0, "PARSE_ERROR")


async def task_tampered_mismatch(session: ClientSession, _root: Path | None) -> Verdict:
    steps = [step("s", "process_upload", filename="statement.csv", content_base64=encode(fixture("statement_tampered.csv")), opening="1000.00", **UPLOAD_ARGS)]
    return await expect_code(session, steps, 0, "BALANCE_MISMATCH")


async def task_camt053_released(session: ClientSession, _root: Path | None) -> Verdict:
    steps = [step("s", "process_upload", filename="camt053.xml", content_base64=encode(fixture("camt053_balanced.xml")))]
    return await expect_code(session, steps, 0, "ok")


async def task_camt053_doctype_refused(session: ClientSession, _root: Path | None) -> Verdict:
    steps = [step("s", "process_upload", filename="camt053.xml", content_base64=encode(fixture("camt053_doctype.xml")))]
    return await expect_code(session, steps, 0, "PARSE_ERROR")


async def task_unsupported_extension(session: ClientSession, _root: Path | None) -> Verdict:
    steps = [step("s", "process_upload", filename="statement.exe", content_base64=encode(fixture("statement_balanced.csv")), opening="1000.00", **UPLOAD_ARGS)]
    return await expect_code(session, steps, 0, "UNSUPPORTED_INPUT")


async def task_oversized_upload(session: ClientSession, _root: Path | None) -> Verdict:
    oversized = encode(b"x" * (UPLOAD_BYTES + 1))
    steps = [step("s", "process_upload", filename="statement.csv", content_base64=oversized)]
    return await expect_code(session, steps, 0, "INPUT_LIMIT")


async def task_records_on_refused(session: ClientSession, _root: Path | None) -> Verdict:
    steps = [
        step("refuse", "process_upload", filename="statement.csv", content_base64=encode(fixture("statement_balanced.csv")), **UPLOAD_ARGS),
        step("rows", "records", from_step="refuse", collection="transactions"),
    ]
    return await expect_code(session, steps, 1, "DOCUMENT_REFUSED")


async def task_path_traversal(session: ClientSession, root: Path | None) -> Verdict:
    if root is None:
        raise RuntimeError("no --root directory available for the scoped server")
    statement = root / "statement.csv"
    statement.write_bytes(fixture("statement_balanced.csv"))
    command = server_parameters(CONFIG["command"], ["--root", str(root)])
    async with stdio_client(command) as (read, write):
        async with ClientSession(read, write) as scoped:
            await scoped.initialize()
            steps = [
                step("escape", "process_file", path="../statement.csv", opening="1000.00", **UPLOAD_ARGS),
                step("absolute", "process_file", path=str(statement.resolve()), opening="1000.00", **UPLOAD_ARGS),
            ]
            response, _ = await execute(scoped, steps)
    codes = [result_code(item) for item in response["steps"]]
    return "INVALID_PATH, INVALID_PATH", ", ".join(codes), codes == ["INVALID_PATH", "INVALID_PATH"]


async def task_response_budget(session: ClientSession, _root: Path | None) -> Verdict:
    header = fixture("statement_balanced.csv").splitlines(keepends=True)[0]
    rows = b"".join(f"02/01/2026,Sample {number},,1.00,{1000 + number}.00\n".encode() for number in range(1, 201))
    steps = [
        step("up", "process_upload", filename="rows.csv", content_base64=encode(header + rows), opening="1000.00", **UPLOAD_ARGS),
        step("doc", "document", from_step="up"),
        step("rows", "records", from_step="up", collection="transactions", limit=10),
    ]
    response, text = await execute(session, steps)
    size = len(text.encode("utf-8"))
    doc_code = result_code(response["steps"][1])
    rows_page = response["steps"][2]["result"]
    actual = f"bytes={size} document={doc_code} rows={len(rows_page['items'])}/{rows_page['total']}"
    passed = size <= RESPONSE_BYTES and doc_code == "RESPONSE_LIMIT" and len(rows_page["items"]) == 10 and rows_page["total"] == 200
    return f"valid JSON <= {RESPONSE_BYTES} bytes, document=RESPONSE_LIMIT, rows page of 10", actual, passed


CHECKS: list[tuple[str, str, Callable[[ClientSession, Path | None], Awaitable[Verdict]]]] = [
    ("S1", "tools listed with title, read-only, output schema", check_tools),
    ("S2", "resources listed", check_resources),
    ("S3", "prompts listed", check_prompts),
    ("S4", "doctor healthy with released sample", check_doctor),
    ("T1", "balanced statement released with opening 1000.00", task_balanced_released),
    ("T2", "same statement without opening refused", task_balanced_without_opening),
    ("T3", "tampered statement refused BALANCE_MISMATCH", task_tampered_mismatch),
    ("T4", "balanced CAMT.053 released", task_camt053_released),
    ("T5", "CAMT.053 with DOCTYPE refused PARSE_ERROR", task_camt053_doctype_refused),
    ("T6", "unsupported extension gives UNSUPPORTED_INPUT", task_unsupported_extension),
    ("T7", "oversized upload gives INPUT_LIMIT", task_oversized_upload),
    ("T8", "records on refused document gives DOCUMENT_REFUSED", task_records_on_refused),
    ("T9", "path traversal under --root gives INVALID_PATH", task_path_traversal),
    ("T10", "records response stays within the response budget", task_response_budget),
]
CONFIG: dict[str, str] = {}


async def run_suite(session: ClientSession, root: Path | None) -> list[dict[str, Any]]:
    results = []
    for check_id, name, check in CHECKS:
        try:
            expected, actual, passed = await check(session, root)
        except Exception as exc:
            expected, actual, passed = "no exception", f"{type(exc).__name__}: {exc}", False
        results.append({"id": check_id, "name": name, "expected": expected, "actual": actual, "passed": bool(passed)})
    return results


async def run_all(repeat: int, root_override: Path | None) -> list[list[dict[str, Any]]]:
    with tempfile.TemporaryDirectory(prefix="openbooks-harness-") as directory:
        root = root_override or Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        runs = []
        async with stdio_client(server_parameters(CONFIG["command"], [])) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for _ in range(repeat):
                    runs.append(await run_suite(session, root))
        return runs


def ascii_cell(value: str, width: int) -> str:
    text = value.encode("ascii", "backslashreplace").decode("ascii")
    return text if len(text) <= width else text[: width - 3] + "..."


def print_table(results: list[dict[str, Any]]) -> None:
    print(f"{'ID':<5}{'CHECK':<46}{'EXPECTED':<34}{'ACTUAL':<40}RESULT")
    for row in results:
        verdict = "PASS" if row["passed"] else "FAIL"
        print(f"{row['id']:<5}{ascii_cell(row['name'], 45):<46}{ascii_cell(row['expected'], 33):<34}{ascii_cell(row['actual'], 39):<40}{verdict}")


def summarise(runs: list[list[dict[str, Any]]]) -> dict[str, Any]:
    ids = [row["id"] for row in runs[0]]
    total = len(ids)
    pass_at_1 = sum(row["passed"] for row in runs[0]) / total
    consistent = [all(run[index]["passed"] for run in runs) for index in range(total)]
    return {
        "checks": total,
        "repeat": len(runs),
        "pass_at_1": round(pass_at_1, 4),
        "pass_pow_k": round(sum(consistent) / total, 4),
        "per_check": {
            check_id: sum(run[index]["passed"] for run in runs)
            for index, check_id in enumerate(ids)
        },
        "all_passed": all(all(row["passed"] for row in run) for run in runs),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic install self-check for the Open Books MCP server.")
    parser.add_argument("--command", default=DEFAULT_COMMAND, help="command that starts the MCP server over stdio")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="machine-readable JSON report path")
    parser.add_argument("--repeat", type=int, default=1, help="run the suite N times and report pass@1 and pass^k")
    parser.add_argument("--root", type=Path, default=None, help="directory passed as --root to the scoped server for T9")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    CONFIG["command"] = args.command
    try:
        runs = asyncio.run(run_all(args.repeat, args.root.resolve() if args.root else None))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"self-check could not run the server: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print_table(runs[0])
    summary = summarise(runs)
    print(f"\npass@1={summary['pass_at_1']:.2f}  pass^{summary['repeat']}={summary['pass_pow_k']:.2f}  "
          f"checks={summary['checks']}  overall={'PASS' if summary['all_passed'] else 'FAIL'}")
    report = {"command": args.command, "runs": runs, "summary": summary}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
