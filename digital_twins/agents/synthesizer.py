"""Synthesizer: turns the full transcript into a DebateVerdict the sales rep can act on."""
from __future__ import annotations

import json
import logging

from digital_twins.config import settings
from digital_twins.i18n import to_en, to_en_list
from digital_twins.llm.client import LLMClient
from digital_twins.models import DebateVerdict, SellerCoaching, Sentiment, StakeholderRole
from digital_twins.orchestration.state import BoardState

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
You are synthesizing the transcript of a simulated buying committee debate
into an actionable verdict for the salesperson who will face this
committee for real.

Beyond the overall verdict, assess the debate through the lens of the
MEDDPICC enterprise sales framework — but ONLY for the dimensions the
debate actually revealed evidence for (do not invent an assessment for
what didn't come up):
- "Metrics": was it possible to prove concrete ROI/metrics for whoever owns the budget decision?
- "Economic Buyer": did the highest-veto-power stakeholder lean toward blocking or supporting, and why?
- "Identify Pain": was the technical/operational pain raised addressed by any other stakeholder (e.g. the Champion) during the debate?
- "Champion": did the internal Champion (if any) bring real ammunition or just stay on the defensive?
Include only the dimensions above that have clear evidence in the transcript.

Return STRICTLY a JSON object in this format. The KEYS and the VALUES of
"overall_sentiment" and "blocking_stakeholders" must stay exactly in
English, as shown below — all textual CONTENT (objections, talk track,
risk summary, scorecard) should be in English as well:
{
  "consensus_reached": bool,
  "overall_sentiment": "supportive" | "neutral" | "skeptical" | "blocking",
  "top_objections": [string, ...],
  "blocking_stakeholders": [string, ...]    // MUST use only these exact role values:
                                             // "cfo", "cto", "procurement", "end_user",
                                             // "champion", "legal_compliance", "ceo", "security", "salesman"
  "recommended_talk_track": [string, ...],  // concrete, specific advice for the next call
  "risk_summary": string,
  "meddpicc_scorecard": {                   // only dimensions with evidence (can be {})
    "Metrics": string,
    "Economic Buyer": string,
    "Identify Pain": string,
    "Champion": string
  }
}

Be specific and tactical. "Better address the concerns" is useless;
"Open with a 3-year TCO table before any feature demo, because the CFO's
objection was specifically about hidden integration cost" is useful.
"""

_SELLER_COACHING_ADDENDUM = """\

IMPORTANT: there was a REAL opening statement from the salesperson
(provided at the start of the input). Beyond the verdict above, act as a
sales coach and assess the SALESPERSON'S PERFORMANCE — how their WORDS
held up (or didn't) against the objections the committee raised during the
debate. Do not assess the committee here; assess the person who gave the
pitch.

Add to the same JSON the field "seller_coaching" with this format:
"seller_coaching": {
  "pitch_grade": string,            // short, honest grade, e.g. "C+ — strong on ROI, weak on governance"
  "what_landed": [string, ...],     // statements from their pitch that resonated or went unchallenged
  "what_backfired": [string, ...],  // statements that were attacked and that they couldn't hold up
  "rewrite_suggestions": [string, ...] // concrete rewrites: "instead of X, say Y because Z"
}
"""


def _parse_seller_coaching(sc: dict | None) -> SellerCoaching | None:
    if not sc:
        return None
    return SellerCoaching(
        pitch_grade=to_en(sc.get("pitch_grade", "")),
        what_landed=to_en_list(sc.get("what_landed", [])),
        what_backfired=to_en_list(sc.get("what_backfired", [])),
        rewrite_suggestions=to_en_list(sc.get("rewrite_suggestions", [])),
    )


def make_synthesize_node(llm: LLMClient, feedback_block: str = ""):
    def synthesize(state: BoardState) -> dict:
        transcript = state.get("transcript", [])
        full_text = "\n".join(
            f"[Round {t.round_number}] {t.name} ({t.sentiment.value}): {t.statement}" for t in transcript
        )

        account = state["account"]
        system_prompt = _SYNTHESIS_SYSTEM_PROMPT
        if feedback_block:
            system_prompt = feedback_block + "\n\n" + system_prompt
        user_content = f"Full transcript:\n{full_text}"
        if account.seller_opening:
            system_prompt = _SYNTHESIS_SYSTEM_PROMPT + _SELLER_COACHING_ADDENDUM
            user_content = (
                f'Salesperson\'s opening statement:\n"{account.seller_opening}"\n\n' + user_content
            )

        raw = llm.complete(
            system=system_prompt,
            user=user_content,
            model=state.get("model_synthesizer") or settings.synthesizer_model,
            max_tokens=settings.max_tokens_synthesis,
            json_mode=True,
        )

        try:
            parsed = json.loads(raw)
            verdict = DebateVerdict(
                consensus_reached=parsed["consensus_reached"],
                overall_sentiment=Sentiment(parsed["overall_sentiment"]),
                top_objections=to_en_list(parsed["top_objections"]),
                blocking_stakeholders=[StakeholderRole(r) for r in parsed["blocking_stakeholders"]],
                recommended_talk_track=to_en_list(parsed["recommended_talk_track"]),
                risk_summary=to_en(parsed["risk_summary"]),
                meddpicc_scorecard={
                    dim: to_en(assessment)
                    for dim, assessment in parsed.get("meddpicc_scorecard", {}).items()
                },
                seller_coaching=_parse_seller_coaching(parsed.get("seller_coaching")),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Synthesizer output failed validation (%s); raw=%r", exc, raw)
            verdict = DebateVerdict(
                consensus_reached=False,
                overall_sentiment=Sentiment.NEUTRAL,
                top_objections=["Synthesis failed — check the logs; the raw transcript is still available."],
                blocking_stakeholders=[],
                recommended_talk_track=["Re-run the synthesis or review the transcript manually."],
                risk_summary=f"Synthesizer parsing error: {exc}",
            )

        return {"verdict": verdict}

    return synthesize
