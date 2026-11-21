from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openbooks_mcp.operations import MAX_RESPONSE, MAX_UPLOAD, SAMPLE, Operations, Step
from openbooks_mcp.server import private_http_app


def step(id: str, operation: str, **arguments) -> Step:
    return Step(id=id, operation=operation, arguments=arguments)


def test_local_scope_and_document_projections(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "statement.csv").write_bytes(SAMPLE)
    outside = tmp_path / "other.csv"
    outside.write_bytes(SAMPLE)
    ops = Operations(root.resolve())

    response = json.loads(ops.execute([
        step("escape", "process_file", path="../other.csv"),
        step("absolute", "process_file", path=str(outside.resolve())),
        step("verify", "process_file", path="statement.csv", currency="INR", opening="1000.00", date_order="dmy"),
        step("rows", "records", from_step="verify", collection="transactions", limit=1),
        step("proof", "records", from_step="verify", collection="evidence", prefix="txn-00001."),
    ]))
    denied, absolute, verified, rows, proof = response["steps"]
    assert denied["error"]["code"] == absolute["error"]["code"] == "INVALID_PATH"
    assert verified["result"]["status"] == "ok"
    assert verified["result"]["counts"]["transactions"] == 2
    assert rows["result"]["items"][0]["amount"] == {"amount": "100.00", "currency": "INR"}
    assert rows["result"]["next_offset"] == 1
    assert all(row["key"].startswith("txn-00001.") for row in proof["result"]["items"])


def test_symlink_cannot_escape_local_scope(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "other.csv"
    outside.write_bytes(SAMPLE)
    try:
        (root / "linked.csv").symlink_to(outside)
    except OSError:
        pytest.skip("this environment cannot create symlinks")
    response = json.loads(Operations(root.resolve()).execute([step("link", "process_file", path="linked.csv")]))
    assert response["steps"][0]["error"]["code"] == "INVALID_PATH"


def test_refusals_and_scoped_uploads() -> None:
    ops = Operations()
    discovered = json.loads(ops.search("process", True))
    assert "process_file" not in [operation["name"] for operation in discovered["operations"]]
    encoded = base64.b64encode(SAMPLE).decode("ascii")
    response = json.loads(ops.execute([
        step("refuse", "process_sample"),
        step("denied", "records", from_step="refuse", collection="transactions"),
        step("missing", "document", from_step="unknown"),
        step("invalid", "process_upload", filename="../escape.csv", content_base64=encoded),
        step("bad_b64", "process_upload", filename="statement.csv", content_base64="!!!!"),
        step("upload", "process_upload", filename="statement.csv", content_base64=encoded, currency="INR", opening="1000.00"),
        step("closing", "records", from_step="upload", collection="batches"),
    ]))
    refused, denied, missing, invalid, bad_b64, upload, closing = response["steps"]
    assert refused["result"]["error"]["code"] == "PARSE_ERROR"
    assert denied["error"]["code"] == "DOCUMENT_REFUSED"
    assert missing["error"]["code"] == "MISSING_DOCUMENT"
    assert invalid["error"]["code"] == "INVALID_ARGUMENTS"
    assert bad_b64["error"]["code"] == "INVALID_ENCODING"
    assert upload["result"]["status"] == "ok"
    assert closing["result"]["items"][0]["closing"]["amount"] == "950.00"


def test_batch_limit_preserves_independent_results() -> None:
    ops = Operations()
    rows = b"".join(
        f"02/01/2026,Sample {number},,1.00,{1000 + number}.00\n".encode()
        for number in range(1, 201)
    )
    encoded = base64.b64encode(SAMPLE.splitlines(keepends=True)[0] + rows).decode()
    response = ops.execute([
        step("upload", "process_upload", filename="rows.csv", content_base64=encoded, currency="INR", opening="1000.00"),
        step("big", "document", from_step="upload"),
        step("slice", "records", from_step="upload", collection="transactions", limit=1),
    ])
    assert len(response) <= MAX_RESPONSE
    uploaded, big, sliced = json.loads(response)["steps"]
    assert uploaded["result"]["status"] == "ok"
    assert big["error"]["code"] == "RESPONSE_LIMIT"
    assert sliced["result"]["total"] == 200
    duplicates = json.loads(ops.execute([step("same", "formats"), step("same", "formats")]))
    assert duplicates["error"]["code"] == "DUPLICATE_STEP"


def test_stdio_lists_two_tools_and_executes_a_batch() -> None:
    async def run() -> None:
        args = StdioServerParameters(command=sys.executable, args=["-m", "openbooks_mcp"])
        async with stdio_client(args) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert [tool.name for tool in tools] == ["search", "execute"]
                result = await session.call_tool("execute", {"steps": [
                    {"id": "csv", "operation": "process_sample", "arguments": {"opening": "1000.00"}},
                    {"id": "proof", "operation": "records", "arguments": {"from_step": "csv", "collection": "assertions"}},
                ]})
                assert not result.is_error
                assert result.structured_content is None
                assert len(result.content) == 1 and result.content[0].type == "text"
                parsed = json.loads(result.content[0].text)["steps"]
                assert parsed[0]["result"]["status"] == "ok"
                assert all(row["passed"] for row in parsed[1]["result"]["items"])

    asyncio.run(run())


def run_one(ops: Operations, operation: str, **arguments) -> dict:
    return json.loads(ops.execute([step("only", operation, **arguments)]))["steps"][0]


def test_search_matches_keywords_and_rejects_unknown_terms() -> None:
    ops = Operations()
    names = [op["name"] for op in json.loads(ops.search("upload", False))["operations"]]
    assert names[0] == "process_upload"
    assert json.loads(ops.search("zzzz-no-match", False))["operations"] == []
    everything = json.loads(ops.search("", False))["operations"]
    assert {op["name"] for op in everything} == {"formats", "process_sample", "process_upload", "records", "document"}
    assert all("arguments" not in op for op in everything)


def test_unknown_operation_and_extra_arguments_are_refused() -> None:
    ops = Operations()
    assert run_one(ops, "no_such_op")["error"]["code"] == "UNKNOWN_OPERATION"
    assert run_one(ops, "process_sample", unexpected=1)["error"]["code"] == "INVALID_ARGUMENTS"
    assert run_one(ops, "process_sample", opening="1e3")["error"]["code"] == "INVALID_ARGUMENTS"
    assert run_one(ops, "process_sample", opening="1000.00")["result"]["status"] == "ok"


def test_upload_rejects_oversized_data_urls_and_wrong_extensions() -> None:
    ops = Operations()
    oversized = base64.b64encode(b"x" * (MAX_UPLOAD + 1)).decode("ascii")
    assert run_one(ops, "process_upload", filename="a.csv", content_base64=oversized)["error"]["code"] == "INPUT_LIMIT"
    prefixed = "data:text/csv;base64," + base64.b64encode(SAMPLE).decode("ascii")
    assert run_one(ops, "process_upload", filename="a.csv", content_base64=prefixed)["error"]["code"] == "INVALID_ENCODING"
    encoded = base64.b64encode(SAMPLE).decode("ascii")
    assert run_one(ops, "process_upload", filename="a.exe", content_base64=encoded)["error"]["code"] == "UNSUPPORTED_INPUT"


def test_upload_accepts_unicode_descriptions_and_empty_payload_is_refused_cleanly() -> None:
    ops = Operations()
    unicode_rows = "02/01/2026,Café ₹ 支払い,100.00,,900.00\n".encode()
    encoded = base64.b64encode(SAMPLE.splitlines(keepends=True)[0] + unicode_rows).decode()
    result = run_one(ops, "process_upload", filename="unicode.csv", content_base64=encoded, currency="INR", opening="1000.00")
    assert result["result"]["status"] in {"ok", "refused"}
    empty = run_one(ops, "process_upload", filename="empty.csv", content_base64="")
    assert empty["error"]["code"] == "INVALID_ARGUMENTS"


def test_process_file_refuses_null_bytes_and_parent_segments(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    ops = Operations(root.resolve())
    for path in ("sub/../../other.csv", "nul\x00.csv", "./missing.csv"):
        error = run_one(ops, "process_file", path=path)
        assert error["error"]["code"] == "INVALID_PATH", path
    assert run_one(ops, "process_file", path="")["error"]["code"] == "INVALID_ARGUMENTS"


def test_process_file_refuses_directories(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    (root / "folder.csv").mkdir(parents=True)
    ops = Operations(root.resolve())
    assert run_one(ops, "process_file", path="folder.csv")["error"]["code"] == "INVALID_PATH"


def test_records_paging_handles_empty_and_out_of_range_offsets() -> None:
    ops = Operations()
    upload = step("verify", "process_sample", opening="1000.00")
    beyond = json.loads(ops.execute([
        upload,
        step("page", "records", from_step="verify", collection="transactions", offset=999, limit=5),
        step("prefix", "records", from_step="verify", collection="transactions", prefix="no-such-id"),
    ]))["steps"]
    assert beyond[1]["result"] == {"collection": "transactions", "items": [], "total": 2, "next_offset": None}
    assert beyond[2]["result"]["total"] == 0


def test_records_refuses_unknown_collections_and_bad_limits() -> None:
    ops = Operations()
    assert run_one(ops, "records", from_step="x", collection="secrets")["error"]["code"] == "INVALID_ARGUMENTS"
    assert run_one(ops, "records", from_step="x", collection="transactions", limit=0)["error"]["code"] == "INVALID_ARGUMENTS"
    assert run_one(ops, "records", from_step="x", collection="transactions", limit=11)["error"]["code"] == "INVALID_ARGUMENTS"


def test_duplicate_step_ids_are_rejected_before_any_work() -> None:
    ops = Operations()
    response = json.loads(ops.execute([step("a", "formats"), step("a", "process_sample")]))
    assert response["error"]["code"] == "DUPLICATE_STEP"
    assert "steps" not in response


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openbooks_mcp", *args],
        capture_output=True, text=True, timeout=60, env={**os.environ, "OPENBOOKS_MCP_TOKEN": ""},
    )


def test_cli_rejects_root_for_http_and_missing_roots(tmp_path: Path) -> None:
    http_with_root = run_cli("--transport", "streamable-http", "--root", str(tmp_path))
    assert http_with_root.returncode == 2
    assert "only available over stdio" in http_with_root.stderr
    missing = run_cli("--root", str(tmp_path / "does-not-exist"))
    assert missing.returncode == 2
    assert "existing directory" in missing.stderr


def test_cli_rejects_weak_tokens_and_out_of_range_ports() -> None:
    weak = run_cli("--transport", "streamable-http")
    assert weak.returncode == 2 and "OPENBOOKS_MCP_TOKEN" in weak.stderr
    bad_port = run_cli("--transport", "streamable-http", "--port", "70000")
    assert bad_port.returncode == 2 and "--port" in bad_port.stderr


def test_http_requires_bearer_before_reading_body() -> None:
    async def run() -> None:
        app = private_http_app(b"test-token-with-at-least-32-characters")
        sent = []

        async def receive():
            raise AssertionError("unauthenticated request body was read")

        async def send(message):
            sent.append(message)

        await app({"type": "http", "headers": []}, receive, send)
        assert sent[0]["status"] == 401
        assert (b"www-authenticate", b"Bearer") in sent[0]["headers"]

    asyncio.run(run())
