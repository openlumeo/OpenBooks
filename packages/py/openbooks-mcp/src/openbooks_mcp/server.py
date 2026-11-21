from __future__ import annotations

import asyncio
from pathlib import Path
from secrets import compare_digest
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .operations import MAX_STEPS, Operations, Step

MAX_HTTP_BODY = 2 * 1024 * 1024
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
DOCS = "https://openbooks.lumeo.co.in/docs/mcp"


def build_server(root: Path | None = None) -> MCPServer:
    operations = Operations(root)
    server = MCPServer(
        "openbooks",
        title="Open Books",
        version=__version__,
        website_url=DOCS,
        instructions="Use search to discover operations. Use execute to verify documents and inspect their proof in one ordered batch.",
        log_level="WARNING",
    )

    @server.tool(annotations=READ_ONLY, structured_output=False)
    def search(query: Annotated[str, Field(max_length=160)] = "", details: bool = False) -> str:
        """Find Open Books operations by name or keyword. Request details to see argument schemas."""
        return operations.search(query, details)

    @server.tool(annotations=READ_ONLY, structured_output=False)
    async def execute(steps: Annotated[list[Step], Field(min_length=1, max_length=MAX_STEPS)]) -> str:
        """Run an ordered batch. Each step has an id, operation and arguments. Use from_step to inspect a preceding document."""
        return await asyncio.to_thread(operations.execute, steps)

    return server


def private_http_app(token: bytes):
    app = build_server().streamable_http_app(
        stateless_http=True,
        json_response=True,
        max_request_body_size=MAX_HTTP_BODY,
    )
    authorization = b"Bearer " + token

    async def protected(scope, receive, send):
        if scope["type"] == "http":
            provided = [value for name, value in scope["headers"] if name == b"authorization"]
            if len(provided) != 1 or not compare_digest(authorization, provided[0]):
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"www-authenticate", b"Bearer"), (b"cache-control", b"no-store")],
                })
                await send({"type": "http.response.body", "body": b"Authorization required"})
                return
        await app(scope, receive, send)

    return protected
