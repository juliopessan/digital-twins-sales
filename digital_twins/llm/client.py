"""
LLM client abstraction.

Every agent node calls through `LLMClient.complete(...)` rather than
touching the Anthropic SDK directly — this is what makes it trivial to
later swap in per-node models (already wired via config.settings).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from digital_twins.config import settings

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_json_fence(text: str) -> str:
    """Some models wrap JSON in ```json ... ``` fences despite instructions
    not to. Strip them so json.loads() in the calling agent node doesn't
    choke on the leading/trailing backticks."""
    match = _JSON_FENCE_RE.match(text.strip())
    return match.group(1).strip() if match else text


class LLMClient(ABC):
    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        """Return raw text completion. If json_mode, caller expects valid JSON text back."""
        raise NotImplementedError


class AnthropicLLMClient(LLMClient):
    """Thin wrapper over the real Anthropic API."""

    def __init__(self, api_key: str | None = None) -> None:
        import anthropic  # local import: keeps the package importable without the SDK installed

        resolved_key = api_key or settings.anthropic_api_key
        if not resolved_key:
            raise RuntimeError("ANTHROPIC_API_KEY não configurada. Exporte a variável ou passe api_key explicitamente.")
        self._client = anthropic.Anthropic(api_key=resolved_key)

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        sys_prompt = system
        if json_mode:
            sys_prompt += (
                "\n\nResponda APENAS com um único objeto JSON válido. Sem texto "
                "explicativo, sem blocos de markdown, sem preâmbulo."
            )
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=sys_prompt,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return _strip_json_fence(text) if json_mode else text


def build_default_client(api_key: str | None = None) -> LLMClient:
    return AnthropicLLMClient(api_key=api_key)
