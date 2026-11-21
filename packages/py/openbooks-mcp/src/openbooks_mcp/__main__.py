from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from . import __version__
from .server import build_server, private_http_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="openbooks-mcp")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--root", type=Path, help="approve a local input directory for stdio")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--port", type=int, default=8791, help="private loopback HTTP port")
    args = parser.parse_args()

    if args.transport == "stdio":
        root = args.root
        if root is not None:
            try:
                root = root.resolve(strict=True)
                if not root.is_dir():
                    parser.error("--root must name an existing directory")
            except (OSError, RuntimeError):
                parser.error("--root must name an existing directory")
        build_server(root).run("stdio")
        return

    if args.root is not None:
        parser.error("--root is only available over stdio")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    token = os.environ.get("OPENBOOKS_MCP_TOKEN", "")
    if not token.isascii() or len(token) < 32 or any(ch.isspace() or not ch.isprintable() for ch in token):
        parser.error("set OPENBOOKS_MCP_TOKEN to a random ASCII token of at least 32 characters")

    uvicorn.run(
        private_http_app(token.encode("ascii")),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        limit_concurrency=8,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
