"""Synthesizer: turns the full transcript into a DebateVerdict the sales rep can act on."""
from __future__ import annotations

import json
import logging

from digital_twins.config import settings
from digital_twins.llm.client import LLMClient
from digital_twins.models import DebateVerdict, Sentiment, StakeholderRole
from digital_twins.orchestration.state import BoardState

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
You are synthesizing a simulated buying-committee debate transcript into an
actionable verdict for the sales rep who will face this committee for real.

Return STRICTLY a JSON object with this shape:
{
  "consensus_reached": bool,
  "overall_sentiment": "supportive" | "neutral" | "skeptical" | "blocking",
  "top_objections": [string, ...],
  "blocking_stakeholders": [string, ...]   // MUST use only these exact role values:
                                            // "cfo", "cto", "procurement", "end_user",
                                            // "champion", "legal_compliance", "ceo", "security"
  "recommended_talk_track": [string, ...], // concrete, specific next-call advice
  "risk_summary": string
}

Be specific and tactical. "Address concerns better" is useless;
"Lead with a 3-year TCO table before showing any feature demo, because the
CFO's objection was specifically about hidden integration cost" is useful.
"""


def make_synthesize_node(llm: LLMClient):
    def synthesize(state: BoardState) -> dict:
        transcript = state.get("transcript", [])
        full_text = "\n".join(
            f"[Round {t.round_number}] {t.name} ({t.sentiment.value}): {t.statement}" for t in transcript
        )

        raw = llm.complete(
            system=_SYNTHESIS_SYSTEM_PROMPT,
            user=f"Full transcript:\n{full_text}",
            model=settings.synthesizer_model,
            max_tokens=settings.max_tokens_synthesis,
            json_mode=True,
        )

        try:
            parsed = json.loads(raw)
            verdict = DebateVerdict(
                consensus_reached=parsed["consensus_reached"],
                overall_sentiment=Sentiment(parsed["overall_sentiment"]),
                top_objections=parsed["top_objections"],
                blocking_stakeholders=[StakeholderRole(r) for r in parsed["blocking_stakeholders"]],
                recommended_talk_track=parsed["recommended_talk_track"],
                risk_summary=parsed["risk_summary"],
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Synthesizer output failed validation (%s); raw=%r", exc, raw)
            verdict = DebateVerdict(
                consensus_reached=False,
                overall_sentiment=Sentiment.NEUTRAL,
                top_objections=["Synthesis failed — see logs; raw transcript still available."],
                blocking_stakeholders=[],
                recommended_talk_track=["Re-run synthesis or review transcript manually."],
                risk_summary=f"Synthesizer parse error: {exc}",
            )

        return {"verdict": verdict}

    return synthesize
