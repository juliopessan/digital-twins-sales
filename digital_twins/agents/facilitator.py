"""
Facilitator: the hierarchical supervisor.

Two responsibilities, two node functions:

  1. `start_round`   — decide/refresh speaking_order for this round and
                        reset current_index to 0. On round 1, speaking order
                        follows AccountContext.roles_in_committee. On later
                        rounds, it re-sorts by decision_power descending IF
                        the round is escalating (so the highest-veto
                        stakeholder gets the final word), otherwise keeps
                        the original order for consistency.

  2. `evaluate_round` — after all personas have spoken this round, an LLM
                         call (the facilitator's own judgment) decides:
                         continue / escalate / conclude. This is the
                         supervisor reasoning over its subordinates' output
                         — the hierarchical part of "hierarchical
                         orchestration".

Both are deliberately cheap LLM calls (or pure heuristics) — the facilitator
should not be the most expensive node in the graph; the personas debating
each other is where the interesting (and costly) generation happens.
"""
from __future__ import annotations

import json
import logging

from digital_twins.config import settings
from digital_twins.llm.client import LLMClient
from digital_twins.models import AccountContext, StakeholderProfile
from digital_twins.orchestration.state import BoardState

logger = logging.getLogger(__name__)


def start_round(state: BoardState) -> dict:
    account: AccountContext = state["account"]
    personas: list[StakeholderProfile] = state["personas"]
    round_number = state.get("round_number", 0) + 1

    if state.get("facilitator_decision") == "escalate":
        # Re-order by decision_power descending: let the biggest veto speak last,
        # so their objection is the one left ringing as the round closes.
        order = sorted(
            (p.role.value for p in personas),
            key=lambda rv: next(p.decision_power for p in personas if p.role.value == rv),
        )
    else:
        # Default order based on the persona list (already prepends salesman in Factory)
        order = [p.role.value for p in personas]

    return {
        "round_number": round_number,
        "speaking_order": order,
        "current_index": 0,
    }


_DECISION_SYSTEM_PROMPT = """\
You are the decision engine for the facilitator of a simulated buying
committee debate. Read the latest round of statements and decide what
happens next.

Return STRICTLY a JSON object in this format (the "decision" values must
stay exactly in English, as shown below; "reasoning" should also be in
English):
{"decision": "continue" | "escalate" | "conclude", "reasoning": "<one sentence, in English>"}

- "continue": more debate is useful, no need to change the dynamic.
- "escalate": a high-power stakeholder (CFO/CEO/CTO) raised a blocking
  objection that the others haven't addressed yet — reorder so they get a
  pointed rebuttal.
- "conclude": either consensus is forming, or positions have clearly
  hardened and one more round would just repeat objections already on the
  table.
"""


def make_evaluate_round_node(llm: LLMClient):
    def evaluate_round(state: BoardState) -> dict:
        round_number = state["round_number"]
        max_rounds = state["max_rounds"]

        this_round_turns = [t for t in state.get("transcript", []) if t.round_number == round_number]
        summary = "\n".join(f"- {t.name} ({t.sentiment.value}): {t.statement}" for t in this_round_turns)

        if round_number >= max_rounds:
            decision, reasoning = "conclude", f"Reached max_rounds={max_rounds}."
        else:
            raw = llm.complete(
                system=_DECISION_SYSTEM_PROMPT,
                user=f"Statements from round {round_number}:\n{summary}",
                model=settings.facilitator_model,
                max_tokens=settings.max_tokens_facilitator,
                json_mode=True,
            )
            try:
                parsed = json.loads(raw)
                decision = parsed.get("decision", "continue")
                reasoning = parsed.get("reasoning", "")
            except json.JSONDecodeError:
                logger.warning("Facilitator returned non-JSON, defaulting to 'continue': %r", raw)
                decision, reasoning = "continue", "fallback: facilitator output was not valid JSON"

        logger.info("Facilitator decision after round %s: %s (%s)", round_number, decision, reasoning)
        return {"facilitator_decision": decision, "facilitator_reasoning": reasoning}

    return evaluate_round


def route_after_evaluation(state: BoardState) -> str:
    decision = state.get("facilitator_decision", "continue")
    if decision == "conclude":
        return "synthesize"
    return "next_round"  # covers both "continue" and "escalate"
