"""
Persona agent node.

Subordinate to the Facilitator in the hierarchy: it never decides WHEN to
speak or WHO speaks next — it only generates content for whichever persona
the Facilitator's speaking_order says is up. This separation is what keeps
the hierarchy clean: persona agents have zero orchestration logic.
"""
from __future__ import annotations

import json
import logging

from digital_twins.config import settings
from digital_twins.llm.client import LLMClient
from digital_twins.models import DebateTurn, Sentiment, StakeholderProfile, StakeholderRole
from digital_twins.orchestration.state import BoardState

logger = logging.getLogger(__name__)

_SENTIMENT_TAGGING_SUFFIX = """

Depois da sua fala em personagem, em uma NOVA linha final, gere exatamente
uma tag legível por máquina neste formato e nada mais nessa linha (a
palavra em si deve ficar em inglês, mesmo que sua fala esteja em português):
SENTIMENT: supportive|neutral|skeptical|blocking
"""


def _find_persona(personas: list[StakeholderProfile], role_value: str) -> StakeholderProfile:
    for p in personas:
        if p.role.value == role_value:
            return p
    raise KeyError(f"No persona found for role {role_value!r}")


def _format_transcript_so_far(transcript: list[DebateTurn]) -> str:
    if not transcript:
        return "(Nenhuma fala ainda — você está abrindo o debate.)"
    lines = [f"[Rodada {t.round_number}] {t.name}: {t.statement}" for t in transcript]
    return "\n".join(lines)


def _parse_sentiment(raw_text: str) -> tuple[str, Sentiment]:
    """Split the LLM's free-text statement from its trailing SENTIMENT tag."""
    sentiment = Sentiment.NEUTRAL
    statement = raw_text.strip()
    if "SENTIMENT:" in raw_text:
        body, _, tag_line = raw_text.rpartition("SENTIMENT:")
        statement = body.strip()
        tag = tag_line.strip().lower()
        for candidate in Sentiment:
            if candidate.value in tag:
                sentiment = candidate
                break
    return statement, sentiment


def make_persona_turn_node(llm: LLMClient):
    """Factory returning a LangGraph node bound to a given LLMClient."""

    def persona_turn(state: BoardState) -> dict:
        speaking_order = state["speaking_order"]
        idx = state["current_index"]
        role_value = speaking_order[idx]
        persona = _find_persona(state["personas"], role_value)

        user_prompt = (
            "Transcrição do debate até agora:\n"
            f"{_format_transcript_so_far(state.get('transcript', []))}\n\n"
            "Agora é a sua vez de falar. Dê sua fala para esta rodada."
        )

        raw = llm.complete(
            system=(persona.system_prompt or "") + _SENTIMENT_TAGGING_SUFFIX,
            user=user_prompt,
            model=settings.persona_model,
            max_tokens=settings.max_tokens_persona_turn,
        )
        statement, sentiment = _parse_sentiment(raw)

        turn = DebateTurn(
            round_number=state["round_number"],
            role=persona.role,
            name=persona.name,
            statement=statement,
            objections_raised=[o for o in persona.known_objections if o.lower()[:15] in statement.lower()],
            sentiment=sentiment,
        )
        logger.info("Round %s — %s (%s): %s", turn.round_number, turn.name, sentiment.value, statement[:80])

        return {
            "transcript": [turn],
            "current_index": idx + 1,
        }

    return persona_turn


def more_personas_left(state: BoardState) -> str:
    """Conditional edge: keep cycling through speaking_order, or hand back to facilitator."""
    if state["current_index"] < len(state["speaking_order"]):
        return "next_persona"
    return "round_complete"
