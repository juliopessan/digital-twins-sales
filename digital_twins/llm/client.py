"""
LLM client abstraction.

Every agent node calls through `LLMClient.complete(...)` rather than
touching the Anthropic SDK directly — this is what makes it trivial to
later swap in per-node models (already wired via config.settings).
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from digital_twins.config import settings

logger = logging.getLogger(__name__)

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
            raise RuntimeError("ANTHROPIC_API_KEY is not configured. Export the variable or pass api_key explicitly.")
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
                "\n\nRespond ONLY with a single valid JSON object. No explanatory "
                "text, no markdown blocks, no preamble."
            )
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=sys_prompt,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return _strip_json_fence(text) if json_mode else text


class DeepSeekLLMClient(LLMClient):
    """Thin wrapper over DeepSeek's OpenAI-compatible chat completions API.

    No SDK dependency: DeepSeek's API is a REST-compatible superset of
    OpenAI's chat completions shape, so a plain HTTP POST is enough and
    keeps this module importable without an extra package.
    """

    _BASE_URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or settings.deepseek_api_key
        if not resolved_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured. Export the variable or pass api_key explicitly.")
        self._api_key = resolved_key

    # deepseek-v4-pro is a reasoning model: `reasoning_content` shares the
    # same max_tokens budget as the visible `content`, and how much
    # reasoning a given prompt triggers isn't predictable ahead of time. A
    # request that hits the cap mid-thought comes back with finish_reason
    # "length" and either an empty or truncated answer — silently passing
    # that through breaks the caller's SENTIMENT-tag parsing (persona
    # turns) or produces invalid JSON (facilitator/synthesizer). Retry once
    # with a much larger budget, sized off how many tokens reasoning
    # actually consumed on the first attempt, rather than guessing.
    _MAX_RETRY_TOKENS = 16_000

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        text, finish_reason, reasoning_tokens = self._call(
            system=system, user=user, model=model, max_tokens=max_tokens, json_mode=json_mode
        )
        if finish_reason == "length" and max_tokens < self._MAX_RETRY_TOKENS:
            retry_budget = min(
                max(max_tokens * 2, max_tokens + reasoning_tokens + 512),
                self._MAX_RETRY_TOKENS,
            )
            logger.warning(
                "DeepSeek response truncated (finish_reason=length, reasoning_tokens=%s) "
                "at max_tokens=%s; retrying once with max_tokens=%s.",
                reasoning_tokens, max_tokens, retry_budget,
            )
            text, _, _ = self._call(
                system=system, user=user, model=model, max_tokens=retry_budget, json_mode=json_mode
            )
        return _strip_json_fence(text) if json_mode else text

    def _call(
        self, *, system: str, user: str, model: str, max_tokens: int, json_mode: bool
    ) -> tuple[str, str | None, int]:
        import requests

        sys_prompt = system
        if json_mode:
            sys_prompt += (
                "\n\nRespond ONLY with a single valid JSON object. No explanatory "
                "text, no markdown blocks, no preamble."
            )
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            # DeepSeek's structured-output mode; the prompt instruction above
            # is kept too since not every DeepSeek model honors this flag.
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            self._BASE_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        text = choice["message"]["content"] or ""
        finish_reason = choice.get("finish_reason")
        reasoning_tokens = (
            data.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        )
        return text, finish_reason, reasoning_tokens


def build_default_client(api_key: str | None = None, provider: str = "anthropic") -> LLMClient:
    if provider == "deepseek":
        return DeepSeekLLMClient(api_key=api_key)
    return AnthropicLLMClient(api_key=api_key)
