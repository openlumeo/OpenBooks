from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openbooks_mcp.operations import MAX_RESPONSE, SAMPLE, Operations, Step
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
