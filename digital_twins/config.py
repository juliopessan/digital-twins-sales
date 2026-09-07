"""Central configuration. Reads from environment, with sane defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load from .env file if it exists
load_dotenv()


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    exa_api_key: str | None = os.getenv("EXA_API_KEY")

    # Default everything to Haiku 4.5 for cost — override per-node via env if
    # you want stronger judgment on the facilitator/synthesizer at higher cost
    # (e.g. DT_FACILITATOR_MODEL=claude-sonnet-5).
    persona_model: str = os.getenv("DT_PERSONA_MODEL", "claude-haiku-4-5-20251001")
    facilitator_model: str = os.getenv("DT_FACILITATOR_MODEL", "claude-haiku-4-5-20251001")
    synthesizer_model: str = os.getenv("DT_SYNTHESIZER_MODEL", "claude-haiku-4-5-20251001")

    # DeepSeek is an alternate provider (see llm/client.py DeepSeekLLMClient),
    # used for every node when the caller selects provider="deepseek" — one
    # model id for all three roles, since DeepSeek doesn't offer the same
    # cost-tiered lineup Anthropic does. deepseek-v4-flash over -v4-pro:
    # noticeably faster turnaround for a debate with many turns, at the
    # cost of some reasoning depth. Both are reasoning models — flash still
    # spends tokens on `reasoning_content` before the visible answer, just
    # fewer of them — so the max_tokens_* headroom below and the
    # finish_reason="length" retry in DeepSeekLLMClient.complete() still apply.
    deepseek_model: str = os.getenv("DT_DEEPSEEK_MODEL", "deepseek-v4-flash")

    # Generous enough to survive DeepSeek's reasoning_content eating into
    # the same budget before the visible answer (see note above); harmless
    # headroom for Anthropic, which doesn't have that overhead.
    max_tokens_persona_turn: int = 700
    max_tokens_facilitator: int = 600
    max_tokens_synthesis: int = 4096

    max_rounds: int = int(os.getenv("DT_MAX_ROUNDS", "3"))


settings = Settings()
