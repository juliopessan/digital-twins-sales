"""
What-if scenarios — branch, simulate, compare: treat the deal like code,
branch variants, and compare the outcomes side by side.

The idea: instead of running ONE debate with ONE pitch, you declare N
variants of the deal (price A vs B, with/without a POC, anchoring on ROI vs
risk), each becomes a "branch" of the base AccountContext, all of them run
the same debate graph, and the result is a side-by-side comparison — "in
which scenario does the CFO block least?" — with a risk score per scenario.

CLI usage:

    python -m digital_twins.main --scenarios scenarios.json

where scenarios.json is a list of ScenarioSpec:

    [
      {"name": "full-price", "description": "Proposal as-is"},
      {"name": "with-poc", "proposed_solution": "... 6-week paid POC ...",
       "deal_value_usd": 90000}
    ]

Omitted fields inherit from the base AccountContext (the branch only carries
the delta).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from pydantic import BaseModel, Field

from digital_twins.llm.client import LLMClient
from digital_twins.models import (
    AccountContext,
    DebateTurn,
    DebateVerdict,
    Sentiment,
    StakeholderProfile,
)

logger = logging.getLogger(__name__)

# Weight of each sentiment in the risk score (higher = worse for the deal).
_SENTIMENT_RISK = {
    Sentiment.SUPPORTIVE: 0.0,
    Sentiment.NEUTRAL: 1.0,
    Sentiment.SKEPTICAL: 2.0,
    Sentiment.BLOCKING: 3.0,
}


class ScenarioSpec(BaseModel):
    """A branch of the deal: only the fields present override the base AccountContext."""

    name: str
    description: str = ""
    pitch_summary: Optional[str] = None
    proposed_solution: Optional[str] = None
    deal_value_usd: Optional[float] = None
    seller_opening: Optional[str] = None
    deal_stage: Optional[str] = None

    def apply(self, base: AccountContext) -> AccountContext:
        overrides = {
            k: v
            for k, v in self.model_dump(exclude={"name", "description"}).items()
            if v is not None
        }
        return base.model_copy(update=overrides)


class ScenarioOutcome(BaseModel):
    """Result of a branch: verdict + transcript + aggregate risk score."""

    scenario: ScenarioSpec
    verdict: DebateVerdict
    transcript: list[DebateTurn] = Field(default_factory=list)
    risk_score: float = Field(
        default=0.0,
        description="Aggregate (lower = better): overall sentiment + number of blockers + lack of consensus.",
    )


def compute_risk_score(verdict: DebateVerdict) -> float:
    """Simple score comparable across scenarios (lower = better).

    It is not a probability — it's an internal ranking: overall sentiment
    weighs up to 3, each blocking stakeholder adds 1, lack of consensus
    adds 1.
    """
    score = _SENTIMENT_RISK.get(verdict.overall_sentiment, 1.0)
    score += float(len(verdict.blocking_stakeholders))
    if not verdict.consensus_reached:
        score += 1.0
    return score


def run_scenarios(
    base_account: AccountContext,
    scenarios: list[ScenarioSpec],
    llm: LLMClient,
    *,
    max_rounds: int = 3,
    max_workers: int = 3,
) -> list[ScenarioOutcome]:
    """Runs the debate graph once per scenario and returns the outcomes sorted by risk.

    Each scenario rebuilds its own committee (the seller_opening/pitch feed
    into the personas' system prompt), so the branches are fully independent
    and can run in parallel.
    """
    # Local imports to avoid a cycle (graph -> agents -> ... does not import scenarios).
    from digital_twins.orchestration.graph import build_board_graph
    from digital_twins.personas.resolver import PersonaFactory

    app = build_board_graph(llm)

    def _run_one(spec: ScenarioSpec) -> ScenarioOutcome:
        account = spec.apply(base_account)
        personas: list[StakeholderProfile] = PersonaFactory.build_committee(account)
        logger.info("Running scenario %r ...", spec.name)
        final_state = app.invoke(
            {
                "account": account,
                "personas": personas,
                "round_number": 0,
                "max_rounds": max_rounds,
                "transcript": [],
                "current_index": 0,
                "speaking_order": [],
                "facilitator_decision": "continue",
            }
        )
        verdict: DebateVerdict = final_state["verdict"]
        return ScenarioOutcome(
            scenario=spec,
            verdict=verdict,
            transcript=final_state["transcript"],
            risk_score=compute_risk_score(verdict),
        )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        outcomes = list(pool.map(_run_one, scenarios))

    return sorted(outcomes, key=lambda o: o.risk_score)


def build_comparison_markdown(
    base_account: AccountContext, outcomes: list[ScenarioOutcome]
) -> str:
    """Side-by-side comparison of the scenarios, already sorted by risk (best first)."""
    lines = [
        f"# Scenario Comparison — {base_account.account_name}",
        "",
        f"Deal stage: {base_account.deal_stage}",
        "",
        "| Scenario | Risk | Sentiment | Consensus | Blockers | Top Objection |",
        "|---|---|---|---|---|---|",
    ]
    for o in outcomes:
        v = o.verdict
        blockers = ", ".join(r.value for r in v.blocking_stakeholders) or "—"
        top = v.top_objections[0] if v.top_objections else "—"
        lines.append(
            f"| {o.scenario.name} | {o.risk_score:.1f} | {v.overall_sentiment.value} "
            f"| {'yes' if v.consensus_reached else 'no'} | {blockers} | {top} |"
        )

    best = outcomes[0]
    lines += [
        "",
        f"**Recommended scenario: `{best.scenario.name}`** (lowest aggregate risk: {best.risk_score:.1f}).",
        "",
    ]

    for o in outcomes:
        v = o.verdict
        lines += [f"## Scenario: {o.scenario.name}", ""]
        if o.scenario.description:
            lines += [f"_{o.scenario.description}_", ""]
        lines += ["Top objections:", ""]
        lines += [f"- {obj}" for obj in v.top_objections] or ["- (none)"]
        lines += ["", "Recommended talk track:", ""]
        lines += [f"- {t}" for t in v.recommended_talk_track]
        lines += ["", f"Risk: {v.risk_summary}", ""]

    return "\n".join(lines)
