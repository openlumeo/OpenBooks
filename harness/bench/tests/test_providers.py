import email.utils
import json
import socket
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from bench.providers import make_provider
from bench.providers.base import ProviderError, Reply, ToolCall, Usage, redact, retry_after_seconds

KEY = "test-secret-key-7f3a9c"
MODEL = "test-model"
PROVIDERS = ["anthropic", "openai", "gemini", "compat"]
SUFFIX = {"anthropic": "", "openai": "/v1", "gemini": "", "compat": "/v1"}
PATHS = {
    "anthropic": "/v1/messages",
    "openai": "/v1/chat/completions",
    "gemini": f"/v1beta/models/{MODEL}:generateContent",
    "compat": "/v1/chat/completions",
}
AUTH = {
    "anthropic": ("x-api-key", KEY),
    "openai": ("authorization", f"Bearer {KEY}"),
    "gemini": ("x-goog-api-key", KEY),
    "compat": ("authorization", f"Bearer {KEY}"),
}
STOP = {"anthropic": "end_turn", "openai": "stop", "gemini": "STOP", "compat": "stop"}
TOOL_STOP = {"anthropic": "tool_use", "openai": "tool_calls", "gemini": "STOP", "compat": "tool_calls"}
TOOL_CALL_ID = {
    "anthropic": "toolu_1",
    "openai": "call_1",
    "gemini": "gemini-call-1-0",
    "compat": "call_1",
}
USER_HI = [{"role": "user", "content": "hi"}]
TOOL_SPEC = {
    "name": "sum",
    "description": "Sum a file",
    "input_schema": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    },
}
ROUND_TRIP = [
    {"role": "user", "content": "sum a.csv"},
    {
        "role": "assistant",
        "content": "checking",
        "tool_calls": [{"id": "t1", "name": "sum", "arguments": {"path": "a.csv"}}],
    },
    {"role": "tool", "tool_call_id": "t1", "name": "sum", "content": '{"total": 3}'},
]

TEXT_REPLY: dict[str, dict[str, Any]] = {
    "anthropic": {
        "content": [{"type": "text", "text": "hello there"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 11, "output_tokens": 3},
    },
    "openai": {
        "choices": [{"message": {"role": "assistant", "content": "hello there"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 3},
    },
    "gemini": {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "hello there"}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3},
    },
}
TEXT_REPLY["compat"] = TEXT_REPLY["openai"]

TOOL_REPLY: dict[str, dict[str, Any]] = {
    "anthropic": {
        "content": [
            {"type": "text", "text": "checking"},
            {"type": "tool_use", "id": "toolu_1", "name": "sum", "input": {"path": "a.csv"}},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 11, "output_tokens": 3},
    },
    "openai": {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "checking",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "sum", "arguments": '{"path": "a.csv"}'},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 3},
    },
    "gemini": {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "checking"},
                        {"functionCall": {"name": "sum", "args": {"path": "a.csv"}}},
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3},
    },
}
TOOL_REPLY["compat"] = TOOL_REPLY["openai"]


class FakeVendor:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responses: list[tuple[int, dict[str, str], Any]] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                owner.requests.append(
                    {
                        "path": self.path,
                        "headers": {key.lower(): value for key, value in self.headers.items()},
                        "body": json.loads(raw),
                    }
                )
                status, headers, payload = owner.responses.pop(0)
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def reply(self, payload: Any, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.responses.append((status, headers or {}, payload))

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


@pytest.fixture
def vendor():
    server = FakeVendor()
    yield server
    server.close()


def build(name: str, vendor: FakeVendor, sleeps: list[float]):
    provider = make_provider(name, MODEL, KEY, base_url=vendor.url + SUFFIX[name])
    provider.sleep = sleeps.append
    return provider


@pytest.mark.parametrize("name", PROVIDERS)
def test_plain_text_reply(vendor, name):
    vendor.reply(TEXT_REPLY[name])
    reply = build(name, vendor, []).complete("be brief", USER_HI, [])
    assert reply == Reply(text="hello there", tool_calls=[], usage=Usage(11, 3), stop=STOP[name])
    request = vendor.requests[0]
    assert request["path"] == PATHS[name]
    assert KEY not in request["path"]
    header, value = AUTH[name]
    assert request["headers"][header] == value


@pytest.mark.parametrize("name", PROVIDERS)
def test_tool_call_reply(vendor, name):
    vendor.reply(TOOL_REPLY[name])
    reply = build(name, vendor, []).complete("", [{"role": "user", "content": "sum a.csv"}], [TOOL_SPEC])
    assert reply.text == "checking"
    assert reply.tool_calls == [ToolCall(id=TOOL_CALL_ID[name], name="sum", arguments={"path": "a.csv"})]
    assert reply.stop == TOOL_STOP[name]


@pytest.mark.parametrize("name", PROVIDERS)
def test_rate_limit_then_success_honours_retry_after(vendor, name):
    vendor.reply({"error": "slow down"}, status=429, headers={"Retry-After": "2"})
    vendor.reply(TEXT_REPLY[name])
    sleeps: list[float] = []
    reply = build(name, vendor, sleeps).complete("", USER_HI, [])
    assert reply.text == "hello there"
    assert len(vendor.requests) == 2
    assert sleeps == [2.0]


@pytest.mark.parametrize("name", PROVIDERS)
def test_server_error_three_times_raises(vendor, name):
    for _ in range(3):
        vendor.reply({"error": "boom"}, status=500)
    sleeps: list[float] = []
    with pytest.raises(ProviderError, match="HTTP 500"):
        build(name, vendor, sleeps).complete("", USER_HI, [])
    assert len(vendor.requests) == 3
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize("name", PROVIDERS)
def test_error_body_echoing_key_is_redacted(vendor, name):
    vendor.reply({"error": f"invalid api key {KEY}"}, status=401)
    with pytest.raises(ProviderError) as info:
        build(name, vendor, []).complete("", USER_HI, [])
    message = str(info.value)
    assert KEY not in message
    assert KEY not in repr(info.value)
    assert "[REDACTED]" in message
    assert "HTTP 401" in message
    assert len(vendor.requests) == 1


def test_repr_never_shows_key():
    provider = make_provider("openai", MODEL, KEY)
    assert KEY not in repr(provider)
    assert KEY not in str(provider)


def test_connection_failure_retries_then_raises():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    sleeps: list[float] = []
    provider = make_provider("openai", MODEL, KEY, base_url=f"http://127.0.0.1:{port}/v1")
    provider.sleep = sleeps.append
    with pytest.raises(ProviderError, match="connection error"):
        provider.complete("", USER_HI, [])
    assert sleeps == [1.0, 2.0]


def test_redact_and_retry_after_parsing():
    later = email.utils.format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
    assert redact(f"a {KEY} b", KEY) == "a [REDACTED] b"
    assert retry_after_seconds("3") == 3.0
    assert retry_after_seconds("9999") == 60.0
    assert 0 < retry_after_seconds(later) <= 30
    assert retry_after_seconds("soon") is None
    assert retry_after_seconds(None) is None


def test_make_provider_validates_input():
    with pytest.raises(ValueError, match="unknown provider"):
        make_provider("nope", MODEL, KEY)
    with pytest.raises(ValueError, match="API key"):
        make_provider("openai", MODEL, "")
    with pytest.raises(ValueError, match="base_url"):
        make_provider("compat", MODEL, None)


def test_compat_without_key_sends_no_authorization(vendor):
    vendor.reply(TEXT_REPLY["compat"])
    provider = make_provider("compat", MODEL, None, base_url=vendor.url + "/v1")
    provider.sleep = [].append
    provider.complete("", USER_HI, [])
    assert "authorization" not in vendor.requests[0]["headers"]


def test_anthropic_round_trip_wire_format(vendor):
    vendor.reply(TEXT_REPLY["anthropic"])
    build("anthropic", vendor, []).complete("you sum", ROUND_TRIP, [TOOL_SPEC])
    request = vendor.requests[0]
    body = request["body"]
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert body["system"] == "you sum"
    assert body["max_tokens"] == 4096
    assert body["tools"] == [
        {"name": "sum", "description": "Sum a file", "input_schema": TOOL_SPEC["input_schema"]}
    ]
    assert body["messages"] == [
        {"role": "user", "content": "sum a.csv"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "checking"},
                {"type": "tool_use", "id": "t1", "name": "sum", "input": {"path": "a.csv"}},
            ],
        },
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": '{"total": 3}'}]},
    ]


def test_anthropic_merges_parallel_tool_results(vendor):
    vendor.reply(TEXT_REPLY["anthropic"])
    messages = [
        {"role": "user", "content": "sum both"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "t1", "name": "sum", "arguments": {"path": "a.csv"}},
                {"id": "t2", "name": "sum", "arguments": {"path": "b.csv"}},
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "name": "sum", "content": "1"},
        {"role": "tool", "tool_call_id": "t2", "name": "sum", "content": "2"},
    ]
    build("anthropic", vendor, []).complete("", messages, [TOOL_SPEC])
    assert vendor.requests[0]["body"]["messages"][2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "1"},
            {"type": "tool_result", "tool_use_id": "t2", "content": "2"},
        ],
    }


@pytest.mark.parametrize("name", ["openai", "compat"])
def test_openai_round_trip_wire_format(vendor, name):
    vendor.reply(TEXT_REPLY[name])
    build(name, vendor, []).complete("you sum", ROUND_TRIP, [TOOL_SPEC])
    request = vendor.requests[0]
    body = request["body"]
    assert request["path"] == PATHS[name]
    assert body["messages"] == [
        {"role": "system", "content": "you sum"},
        {"role": "user", "content": "sum a.csv"},
        {
            "role": "assistant",
            "content": "checking",
            "tool_calls": [
                {
                    "id": "t1",
                    "type": "function",
                    "function": {"name": "sum", "arguments": json.dumps({"path": "a.csv"})},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "content": '{"total": 3}'},
    ]
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "sum",
                "description": "Sum a file",
                "parameters": TOOL_SPEC["input_schema"],
            },
        }
    ]


def test_gemini_round_trip_wire_format(vendor):
    vendor.reply(TEXT_REPLY["gemini"])
    build("gemini", vendor, []).complete("you sum", ROUND_TRIP, [TOOL_SPEC])
    request = vendor.requests[0]
    body = request["body"]
    assert request["headers"]["x-goog-api-key"] == KEY
    assert body["systemInstruction"] == {"parts": [{"text": "you sum"}]}
    assert body["tools"] == [
        {
            "functionDeclarations": [
                {
                    "name": "sum",
                    "description": "Sum a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                }
            ]
        }
    ]
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "sum a.csv"}]},
        {
            "role": "model",
            "parts": [
                {"text": "checking"},
                {"functionCall": {"name": "sum", "args": {"path": "a.csv"}}},
            ],
        },
        {
            "role": "user",
            "parts": [{"functionResponse": {"name": "sum", "response": {"content": '{"total": 3}'}}}],
        },
    ]


def test_gemini_merges_parallel_function_responses(vendor):
    vendor.reply(TEXT_REPLY["gemini"])
    messages = [
        {"role": "user", "content": "sum both"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "t1", "name": "sum", "arguments": {"path": "a.csv"}},
                {"id": "t2", "name": "sum", "arguments": {"path": "b.csv"}},
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "name": "sum", "content": "1"},
        {"role": "tool", "tool_call_id": "t2", "name": "sum", "content": "2"},
    ]
    build("gemini", vendor, []).complete("", messages, [TOOL_SPEC])
    assert vendor.requests[0]["body"]["contents"][2] == {
        "role": "user",
        "parts": [
            {"functionResponse": {"name": "sum", "response": {"content": "1"}}},
            {"functionResponse": {"name": "sum", "response": {"content": "2"}}},
        ],
    }
