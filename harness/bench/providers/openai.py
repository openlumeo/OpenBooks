from __future__ import annotations

import json
from typing import Any

from bench.providers.base import Provider, ProviderError, Reply, ToolCall, usage_from


class OpenAIProvider(Provider):
    name = "openai"
    default_base_url = "https://api.openai.com/v1"

    def build_request(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        wire = [{"role": "system", "content": system}] if system else []
        body: dict[str, Any] = {
            "model": self.model,
            "messages": wire + [_wire_message(message) for message in messages],
        }
        if tools:
            body["tools"] = [_wire_tool(tool) for tool in tools]
        return f"{self.base_url}/chat/completions", self.auth_headers(), body

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def parse_reply(self, payload: dict[str, Any], turn: int) -> Reply:
        choices = payload.get("choices") or []
        if not choices:
            raise ProviderError("response has no choices")
        choice = choices[0]
        message = choice.get("message") or {}
        return Reply(
            text=message.get("content") or "",
            tool_calls=[_parse_call(call) for call in message.get("tool_calls") or []],
            usage=usage_from(payload.get("usage") or {}, "prompt_tokens", "completion_tokens"),
            stop=str(choice.get("finish_reason") or ""),
        )


def parse_arguments(raw: Any) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise ProviderError("tool arguments are not valid JSON") from None
    if not isinstance(value, dict):
        raise ProviderError("tool arguments must be a JSON object")
    return value


def _wire_message(message: dict[str, Any]) -> dict[str, Any]:
    role = message["role"]
    if role == "user":
        return {"role": "user", "content": message["content"]}
    if role == "assistant":
        return _wire_assistant(message)
    if role == "tool":
        return {"role": "tool", "tool_call_id": message["tool_call_id"], "content": message["content"]}
    raise ValueError(f"unknown message role {role!r}")


def _wire_assistant(message: dict[str, Any]) -> dict[str, Any]:
    calls = message.get("tool_calls") or []
    if not calls:
        return {"role": "assistant", "content": message.get("content", "")}
    return {
        "role": "assistant",
        "content": message.get("content") or None,
        "tool_calls": [_wire_call(call) for call in calls],
    }


def _wire_call(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call["id"],
        "type": "function",
        "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
    }


def _parse_call(call: dict[str, Any]) -> ToolCall:
    function = call["function"]
    return ToolCall(
        id=call["id"],
        name=function["name"],
        arguments=parse_arguments(function.get("arguments")),
    )


def _wire_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }
