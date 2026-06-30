"""
LLM client abstraction.

Every agent node calls through `LLMClient.complete(...)` rather than
touching the Anthropic SDK directly. This is what makes the whole graph
testable without an API key (MockLLMClient) and what makes it trivial to
later swap in per-node models (already wired via config.settings).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from digital_twins.config import settings


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
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Export it, pass api_key explicitly, "
                "or use --mock to run this demo with MockLLMClient instead."
            )
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
                "\n\nRespond with ONLY a single valid JSON object. No prose, "
                "no markdown fences, no preamble."
            )
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=sys_prompt,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class MockLLMClient(LLMClient):
    """
    Deterministic, offline stand-in used by tests and `main.py --mock`.

    It doesn't try to be smart — it produces structurally valid output
    (including valid JSON when json_mode=True) so the graph wiring, state
    reducers, and conditional edges can all be exercised without spending
    a single token.
    """

    def __init__(self) -> None:
        self._call_count = 0

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        self._call_count += 1
        if json_mode:
            return self._mock_json(system, user)
        return (
            f"[mock turn #{self._call_count}] Based on the brief, I have concerns "
            f"about scope and timeline, but I see potential value here."
        )

    def _mock_json(self, system: str, user: str) -> str:
        # Branch on content of the prompt to return shape-appropriate mocks
        # for the two structured-output call sites: facilitator decisions
        # and the final synthesis.
        if "facilitator_decision" in system or "continue" in system.lower():
            return json.dumps(
                {
                    "decision": "continue" if self._call_count < 3 else "conclude",
                    "reasoning": "Mock facilitator: rotating decision for demo purposes.",
                }
            )
        return json.dumps(
            {
                "consensus_reached": False,
                "overall_sentiment": "skeptical",
                "top_objections": [
                    "Total cost of ownership unclear over 3 years",
                    "Integration timeline conflicts with Q3 freeze window",
                ],
                "blocking_stakeholders": ["cfo"],
                "recommended_talk_track": [
                    "Lead with TCO breakdown vs. status quo, not feature list",
                    "Offer a phased rollout that respects the Q3 freeze",
                ],
                "risk_summary": "Mock synthesis: CFO is the primary blocker on cost framing.",
            }
        )


def build_default_client(mock: bool = False, api_key: str | None = None) -> LLMClient:
    return MockLLMClient() if mock else AnthropicLLMClient(api_key=api_key)
