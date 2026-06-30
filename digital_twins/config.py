"""Central configuration. Reads from environment, with sane defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")

    # Model tiers — split so the cheap/fast model can run high-volume persona
    # turns while a stronger model handles the facilitator's escalation
    # judgment and the final synthesis. Override via env if you want every
    # node on the same model.
    persona_model: str = os.getenv("DT_PERSONA_MODEL", "claude-haiku-4-5-20251001")
    facilitator_model: str = os.getenv("DT_FACILITATOR_MODEL", "claude-sonnet-5")
    synthesizer_model: str = os.getenv("DT_SYNTHESIZER_MODEL", "claude-sonnet-5")

    max_tokens_persona_turn: int = 400
    max_tokens_facilitator: int = 300
    max_tokens_synthesis: int = 2000

    max_rounds: int = int(os.getenv("DT_MAX_ROUNDS", "3"))


settings = Settings()
