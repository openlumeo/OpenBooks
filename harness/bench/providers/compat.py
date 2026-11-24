from __future__ import annotations

from bench.providers.openai import OpenAIProvider


class CompatProvider(OpenAIProvider):
    name = "compat"
    default_base_url = ""
    requires_key = False

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        if not base_url:
            raise ValueError("compat provider needs a base_url")
        super().__init__(model, api_key, base_url=base_url, timeout=timeout)

    def auth_headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return super().auth_headers()
