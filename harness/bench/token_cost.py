from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from bench.mcp_client import DEFAULT_MCP_COMMAND, McpClient, McpError, split_command

SCHEMA = "token-cost.v1"
BENCH_DIR = Path(__file__).resolve().parent
HARNESS_DIR = BENCH_DIR.parent
SAMPLES_DIR = HARNESS_DIR / "samples"
DEFAULT_OUT_DIR = HARNESS_DIR / "bench-out"
OUT_FILENAME = "token-cost.v1.json"
CHARS_PER_TOKEN = 4
TOKEN_METHOD_TIKTOKEN = "tiktoken cl100k_base"
TOKEN_METHOD_ESTIMATE = "chars/4 estimate (ceil(characters / 4))"
EXECUTE_TOOL = "execute"
UPLOAD_OPERATION = "process_upload"
RESOURCES_METHOD = "resources/list"

Counter = Callable[[str], int]


@dataclass(frozen=True)
class SampleCase:
    filename: str
    arguments: dict[str, str]


SAMPLE_CASES = (
    SampleCase("statement_balanced.csv", {"opening": "1000.00", "currency": "INR", "date_order": "dmy"}),
    SampleCase("statement_tampered.csv", {"opening": "1000.00", "currency": "INR", "date_order": "dmy"}),
    SampleCase("camt053_balanced.xml", {}),
)


@dataclass(frozen=True)
class Measure:
    name: str
    raw_bytes: int
    tokens: int


@dataclass(frozen=True)
class SampleResult:
    filename: str
    status: str
    code: str
    request: Measure
    response: Measure


@dataclass(frozen=True)
class Report:
    schema: str
    command: str
    token_method: str
    tools: Measure
    tool_names: tuple[str, ...]
    resources: Measure
    resource_uris: tuple[str, ...]
    samples: tuple[SampleResult, ...]


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def load_counter() -> tuple[Counter, str]:
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return estimate_tokens, TOKEN_METHOD_ESTIMATE
    return lambda text: len(encoding.encode(text)), TOKEN_METHOD_TIKTOKEN


def measure(name: str, text: str, count: Counter) -> Measure:
    return Measure(name, len(text.encode("utf-8")), count(text))


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def tool_text(result: dict[str, Any]) -> str:
    blocks = result.get("content", [])
    texts = [block.get("text", "") for block in blocks if isinstance(block, dict)]
    return "\n".join(texts) if texts else compact_json(result)


def find_key(node: Any, key: str) -> Any:
    queue = [node]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            if key in current:
                return current[key]
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return None


def parse_outcome(text: str) -> tuple[str, str]:
    try:
        body = json.loads(text)
    except ValueError:
        return "unparsed", ""
    status = find_key(body, "status")
    code = find_key(body, "code")
    return str(status or "unknown"), str(code or "")


def upload_arguments(case: SampleCase) -> dict[str, Any]:
    content = base64.b64encode((SAMPLES_DIR / case.filename).read_bytes()).decode("ascii")
    upload = {"filename": case.filename, "content_base64": content, **case.arguments}
    return {"steps": [{"id": "doc", "operation": UPLOAD_OPERATION, "arguments": upload}]}


def measure_sample(client: Any, case: SampleCase, count: Counter) -> SampleResult:
    arguments = upload_arguments(case)
    request = measure(f"request {case.filename}", compact_json(arguments), count)
    text = tool_text(client.call_tool(EXECUTE_TOOL, arguments))
    status, code = parse_outcome(text)
    response = measure(f"response {case.filename}", text, count)
    return SampleResult(case.filename, status, code, request, response)


def build_report(client: Any, count: Counter, token_method: str) -> Report:
    tools = client.list_tools()
    resources_result = client.request(RESOURCES_METHOD, {})
    resources = resources_result.get("resources", []) if isinstance(resources_result, dict) else []
    samples = tuple(measure_sample(client, case, count) for case in SAMPLE_CASES)
    return Report(
        schema=SCHEMA,
        command=DEFAULT_MCP_COMMAND,
        token_method=token_method,
        tools=measure("tools/list", compact_json(tools), count),
        tool_names=tuple(str(tool.get("name")) for tool in tools),
        resources=measure("resources/list", compact_json(resources), count),
        resource_uris=tuple(str(resource.get("uri")) for resource in resources),
        samples=samples,
    )


def row(item: Measure) -> str:
    return f"| {item.name} | {item.raw_bytes} | {item.tokens} |"


def render_markdown(report: Report) -> str:
    lines = [
        f"Token method: {report.token_method}",
        f"Server command: `{report.command}`",
        "",
        "| Measure | Raw bytes | Tokens |",
        "|---|---:|---:|",
        row(report.tools),
        row(report.resources),
    ]
    for sample in report.samples:
        lines.append(row(sample.request))
        lines.append(row(sample.response))
    lines += ["", "| Outcome | Status | Code | Raw bytes | Tokens |", "|---|---|---|---:|---:|"]
    for sample in report.samples:
        lines.append(
            f"| {sample.filename} | {sample.status} | {sample.code or '-'} | "
            f"{sample.response.raw_bytes} | {sample.response.tokens} |"
        )
    return "\n".join(lines)


class FakeClient:
    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": "execute", "description": "fake", "inputSchema": {"type": "object"}}]

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if method != RESOURCES_METHOD:
            raise McpError(f"unexpected method {method}")
        return {"resources": [{"uri": "openbooks://fake", "name": "fake"}]}

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        filename = arguments["steps"][0]["arguments"]["filename"]
        refused = "tampered" in filename
        body = {"steps": [{"id": "doc", "status": "refused" if refused else "ok", "code": "BALANCE_MISMATCH" if refused else None}]}
        return {"content": [{"type": "text", "text": json.dumps(body)}]}


def self_check() -> int:
    report = build_report(FakeClient(), estimate_tokens, TOKEN_METHOD_ESTIMATE)
    outcomes = {sample.filename: sample for sample in report.samples}
    assert report.tool_names == ("execute",), report.tool_names
    assert report.resource_uris == ("openbooks://fake",), report.resource_uris
    assert report.tools.tokens > 0 and report.resources.tokens > 0
    assert outcomes["statement_tampered.csv"].status == "refused"
    assert outcomes["statement_tampered.csv"].code == "BALANCE_MISMATCH"
    assert outcomes["statement_balanced.csv"].status == "ok"
    assert all(sample.request.raw_bytes > 0 and sample.response.tokens > 0 for sample in report.samples)
    assert "| tools/list |" in render_markdown(report)
    assert json.loads(json.dumps(dataclasses.asdict(report)))["schema"] == SCHEMA
    print("token_cost self-check ok")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bench.token_cost", description="Measure LLM token cost of the Open Books MCP server.")
    parser.add_argument("--self-check", action="store_true", help="run an in-memory fake server check and exit")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="directory for token-cost.v1.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_check:
        return self_check()
    count, token_method = load_counter()
    try:
        with McpClient(split_command(DEFAULT_MCP_COMMAND)) as client:
            report = build_report(client, count, token_method)
    except McpError as error:
        print(f"cannot measure the MCP server: {error}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / OUT_FILENAME
    path.write_text(json.dumps(dataclasses.asdict(report), indent=2) + "\n", encoding="utf-8")
    print(render_markdown(report))
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
