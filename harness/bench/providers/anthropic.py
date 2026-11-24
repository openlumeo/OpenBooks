from __future__ import annotations

from typing import Any

from bench.providers.base import Provider, Reply, ToolCall, usage_from

ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 4096


class AnthropicProvider(Provider):
    name = "anthropic"
    default_base_url = "https://api.anthropic.com"

    def build_request(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": _wire_messages(messages),
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [_wire_tool(tool) for tool in tools]
        headers = {"x-api-key": self._api_key, "anthropic-version": ANTHROPIC_VERSION}
        return f"{self.base_url}/v1/messages", headers, body

    def parse_reply(self, payload: dict[str, Any], turn: int) -> Reply:
        blocks = payload.get("content") or []
        return Reply(
            text="".join(block.get("text", "") for block in blocks if block.get("type") == "text"),
            tool_calls=[
                ToolCall(id=block["id"], name=block["name"], arguments=dict(block.get("input") or {}))
                for block in blocks
                if block.get("type") == "tool_use"
            ],
            usage=usage_from(payload.get("usage") or {}, "input_tokens", "output_tokens"),
            stop=str(payload.get("stop_reason") or ""),
        )


def _wire_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "user":
            wire.append({"role": "user", "content": message["content"]})
        elif role == "assistant":
            wire.append({"role": "assistant", "content": _assistant_content(message)})
        elif role == "tool":
            _add_tool_result(wire, message)
        else:
            raise ValueError(f"unknown message role {role!r}")
    return wire


def _assistant_content(message: dict[str, Any]) -> Any:
    calls = message.get("tool_calls") or []
    if not calls:
        return message.get("content", "")
    text_blocks = [{"type": "text", "text": message["content"]}] if message.get("content") else []
    return text_blocks + [
        {"type": "tool_use", "id": call["id"], "name": call["name"], "input": call["arguments"]}
        for call in calls
    ]


def _add_tool_result(wire: list[dict[str, Any]], message: dict[str, Any]) -> None:
    block = {
        "type": "tool_result",
        "tool_use_id": message["tool_call_id"],
        "content": message["content"],
    }
    last = wire[-1] if wire else None
    if last and last["role"] == "user" and isinstance(last["content"], list):
        wire[-1] = {"role": "user", "content": [*last["content"], block]}
    else:
        wire.append({"role": "user", "content": [block]})


def _wire_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "input_schema": tool["input_schema"],
    }
