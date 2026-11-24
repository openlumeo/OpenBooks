from bench.providers.anthropic import AnthropicProvider
from bench.providers.base import Provider, ProviderError, Reply, ToolCall, Usage
from bench.providers.compat import CompatProvider
from bench.providers.gemini import GeminiProvider
from bench.providers.openai import OpenAIProvider

PROVIDER_CLASSES = {
    cls.name: cls for cls in (AnthropicProvider, OpenAIProvider, GeminiProvider, CompatProvider)
}

__all__ = [
    "AnthropicProvider",
    "CompatProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "Provider",
    "ProviderError",
    "Reply",
    "ToolCall",
    "Usage",
    "make_provider",
]


def make_provider(name: str, model: str, api_key: str | None, base_url: str | None = None) -> Provider:
    provider_class = PROVIDER_CLASSES.get(name)
    if provider_class is None:
        raise ValueError(f"unknown provider {name!r}")
    return provider_class(model, api_key, base_url=base_url)
