from __future__ import annotations

from typing import Any
from urllib.parse import quote

from bench.providers.base import Provider, ProviderError, Reply, ToolCall, usage_from

UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$schema",
        "$id",
        "$comment",
        "$defs",
        "definitions",
        "additionalProperties",
        "unevaluatedProperties",
        "patternProperties",
        "examples",
    }
)


class GeminiProvider(Provider):
    name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com"

    def build_request(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        body: dict[str, Any] = {"contents": _contents(messages)}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [_declaration(tool) for tool in tools]}]
        url = f"{self.base_url}/v1beta/models/{quote(self.model, safe='')}:generateContent"
        return url, {"x-goog-api-key": self._api_key}, body

    def parse_reply(self, payload: dict[str, Any], turn: int) -> Reply:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise ProviderError("gemini response has no candidates")
        candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        calls = [part["functionCall"] for part in parts if "functionCall" in part]
        return Reply(
            text="".join(part.get("text", "") for part in parts),
            tool_calls=[
                ToolCall(
                    id=f"gemini-call-{turn}-{index}",
                    name=call["name"],
                    arguments=dict(call.get("args") or {}),
                )
                for index, call in enumerate(calls)
            ],
            usage=usage_from(payload.get("usageMetadata") or {}, "promptTokenCount", "candidatesTokenCount"),
            stop=str(candidate.get("finishReason") or ""),
        )


def clean_schema(node: Any) -> Any:
    if isinstance(node, list):
        return [clean_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    return {
        key: _clean_properties(value) if key == "properties" else clean_schema(value)
        for key, value in node.items()
        if key not in UNSUPPORTED_SCHEMA_KEYS
    }


def _clean_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {name: clean_schema(schema) for name, schema in properties.items()}


def _contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": message["content"]}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": _assistant_parts(message)})
        elif role == "tool":
            _add_function_response(contents, message)
        else:
            raise ValueError(f"unknown message role {role!r}")
    return contents


def _assistant_parts(message: dict[str, Any]) -> list[dict[str, Any]]:
    text_parts = [{"text": message["content"]}] if message.get("content") else []
    call_parts = [
        {"functionCall": {"name": call["name"], "args": call["arguments"]}}
        for call in message.get("tool_calls") or []
    ]
    return text_parts + call_parts


def _add_function_response(contents: list[dict[str, Any]], message: dict[str, Any]) -> None:
    part = {
        "functionResponse": {
            "name": message["name"],
            "response": {"content": message["content"]},
        }
    }
    last = contents[-1] if contents else None
    if last and last["role"] == "user" and last["parts"] and "functionResponse" in last["parts"][-1]:
        contents[-1] = {"role": "user", "parts": [*last["parts"], part]}
    else:
        contents.append({"role": "user", "parts": [part]})


def _declaration(tool: dict[str, Any]) -> dict[str, Any]:
    declaration: dict[str, Any] = {"name": tool["name"], "description": tool.get("description", "")}
    schema = clean_schema(tool["input_schema"])
    if schema:
        declaration["parameters"] = schema
    return declaration
