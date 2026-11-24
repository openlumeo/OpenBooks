from __future__ import annotations

import collections
import json
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "openbooks-bench", "version": "0.1.0"}
DEFAULT_MCP_COMMAND = "npx -y @lumeo_hq/openbooks mcp"
STARTUP_TIMEOUT_S = 180.0
CALL_TIMEOUT_S = 600.0
SHUTDOWN_TIMEOUT_S = 5.0
STDERR_TAIL_LINES = 20
METHOD_NOT_FOUND = -32601
IS_WINDOWS = sys.platform == "win32"


class McpError(RuntimeError):
    pass


class McpTimeout(McpError):
    pass


def split_command(command: str) -> list[str]:
    if not IS_WINDOWS:
        return shlex.split(command)
    return [_unquote(token) for token in shlex.split(command, posix=False)]


def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def resolve_executable(argv: list[str]) -> list[str]:
    if IS_WINDOWS and argv and argv[0].lower() == "npx":
        return [shutil.which("npx.cmd") or "npx.cmd", *argv[1:]]
    return list(argv)


def _kill(process: subprocess.Popen[bytes]) -> None:
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    process.kill()


def _parse_message(line: str) -> dict[str, Any] | None:
    text = line.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class McpClient:
    def __init__(
        self,
        argv: list[str],
        env: dict[str, str] | None = None,
        call_timeout: float = CALL_TIMEOUT_S,
    ) -> None:
        self._argv = resolve_executable(argv)
        self._env = env
        self._call_timeout = call_timeout
        self._process: subprocess.Popen[bytes] | None = None
        self._stdin: Any = None
        self._inbox: queue.Queue[str | None] = queue.Queue()
        self._stderr_tail: collections.deque[str] = collections.deque(maxlen=STDERR_TAIL_LINES)
        self._threads: list[threading.Thread] = []
        self._request_id = 0

    def __enter__(self) -> McpClient:
        self.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            raise McpError("MCP client already started")
        try:
            self._process = subprocess.Popen(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
            )
        except OSError as error:
            raise McpError(f"cannot start MCP server {self._argv[0]!r}: {error}") from error
        self._stdin = self._process.stdin
        self._spawn(self._pump_stdout, self._process.stdout)
        self._spawn(self._drain_stderr, self._process.stderr)
        try:
            result = self.request(
                "initialize",
                {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
                timeout=STARTUP_TIMEOUT_S,
            )
            if not isinstance(result, dict) or result.get("protocolVersion") != PROTOCOL_VERSION:
                raise McpError(f"MCP server answered protocol {result.get('protocolVersion') if isinstance(result, dict) else None!r}")
            self.notify("notifications/initialized")
        except McpError:
            self.close()
            raise

    def list_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params = {} if cursor is None else {"cursor": cursor}
            result = _as_dict(self.request("tools/list", params), "tools/list")
            tools.extend(item for item in result.get("tools", []) if isinstance(item, dict))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return _as_dict(result, "tools/call")

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
        self._request_id += 1
        request_id = self._request_id
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        limit = self._call_timeout if timeout is None else timeout
        return self._await_result(request_id, method, limit)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        self._process = None
        try:
            if self._stdin is not None:
                self._stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=SHUTDOWN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            _kill(process)
            process.wait(timeout=SHUTDOWN_TIMEOUT_S)
        for thread in self._threads:
            thread.join(timeout=1.0)

    def _spawn(self, target: Any, stream: Any) -> None:
        thread = threading.Thread(target=target, args=(stream,), daemon=True)
        thread.start()
        self._threads.append(thread)

    def _pump_stdout(self, stream: Any) -> None:
        for raw in iter(stream.readline, b""):
            self._inbox.put(raw.decode("utf-8", errors="replace"))
        self._inbox.put(None)

    def _drain_stderr(self, stream: Any) -> None:
        for raw in iter(stream.readline, b""):
            self._stderr_tail.append(raw.decode("utf-8", errors="replace").rstrip())

    def _send(self, message: dict[str, Any]) -> None:
        if self._stdin is None or self._process is None:
            raise McpError("MCP server is not running")
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            self._stdin.write(data)
            self._stdin.flush()
        except (OSError, ValueError) as error:
            raise McpError(f"write to MCP server failed: {error}{self._stderr_hint()}") from error

    def _await_result(self, request_id: int, method: str, limit: float) -> Any:
        deadline = time.monotonic() + limit
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpTimeout(f"{method} timed out after {limit:g}s{self._stderr_hint()}")
            try:
                line = self._inbox.get(timeout=remaining)
            except queue.Empty:
                raise McpTimeout(f"{method} timed out after {limit:g}s{self._stderr_hint()}") from None
            if line is None:
                raise McpError(f"MCP server closed its output during {method}{self._stderr_hint()}")
            message = _parse_message(line)
            if message is None:
                continue
            if "method" in message and "id" in message:
                self._send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": METHOD_NOT_FOUND, "message": "not supported by the bench client"}})
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"] if isinstance(message["error"], dict) else {}
                raise McpError(f"{method} failed: {error.get('message', 'unknown error')} (code {error.get('code')})")
            return message.get("result")

    def _stderr_hint(self) -> str:
        tail = [line for line in list(self._stderr_tail)[-3:] if line]
        return f" (server stderr: {' | '.join(tail)})" if tail else ""


def _as_dict(value: Any, method: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise McpError(f"{method} returned a non-object result")
    return value
