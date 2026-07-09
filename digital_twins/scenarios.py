"""
Cenários what-if — inspirado no "Scenarios & Simulations" do Palantir Foundry
("Treating Your Business Like Code; branch, simulate, and explore").

A ideia: em vez de rodar UM debate com UM pitch, você declara N variantes do
deal (preço A vs B, com/sem POC, ancorar em ROI vs risco), cada uma vira um
"branch" do AccountContext base, todas rodam o mesmo grafo de debate, e o
resultado é um comparativo lado a lado — "em qual cenário o CFO bloqueia
menos?" — com um score de risco por cenário.

Uso via CLI:

    python -m digital_twins.main --scenarios cenarios.json

onde cenarios.json é uma lista de ScenarioSpec:

    [
      {"name": "preco-cheio", "description": "Proposta como está"},
      {"name": "com-poc", "proposed_solution": "... POC paga de 6 semanas ...",
       "deal_value_usd": 90000}
    ]

Campos omitidos herdam do AccountContext base (o branch só carrega o delta).
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

# Peso de cada sentimento no score de risco (maior = pior para o deal).
_SENTIMENT_RISK = {
    Sentiment.SUPPORTIVE: 0.0,
    Sentiment.NEUTRAL: 1.0,
    Sentiment.SKEPTICAL: 2.0,
    Sentiment.BLOCKING: 3.0,
}


class ScenarioSpec(BaseModel):
    """Um branch do deal: só os campos presentes sobrescrevem o AccountContext base."""

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
    """Resultado de um branch: veredito + transcrição + score de risco agregado."""

    scenario: ScenarioSpec
    verdict: DebateVerdict
    transcript: list[DebateTurn] = Field(default_factory=list)
    risk_score: float = Field(
        default=0.0,
        description="Agregado (menor = melhor): sentimento geral + nº de bloqueadores + falta de consenso.",
    )


def compute_risk_score(verdict: DebateVerdict) -> float:
    """Score simples e comparável entre cenários (menor = melhor).

    Não é probabilidade — é um ranking interno: sentimento geral pesa até 3,
    cada stakeholder bloqueador soma 1, falta de consenso soma 1.
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
    """Roda o grafo de debate uma vez por cenário e devolve os resultados ordenados por risco.

    Cada cenário reconstrói o próprio comitê (o seller_opening/pitch entram no
    system prompt das personas), então os branches são totalmente independentes
    e podem rodar em paralelo.
    """
    # Imports locais para evitar ciclo (graph -> agents -> ... não importa scenarios).
    from digital_twins.orchestration.graph import build_board_graph
    from digital_twins.personas.resolver import PersonaFactory

    app = build_board_graph(llm)

    def _run_one(spec: ScenarioSpec) -> ScenarioOutcome:
        account = spec.apply(base_account)
        personas: list[StakeholderProfile] = PersonaFactory.build_committee(account)
        logger.info("Rodando cenário %r ...", spec.name)
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
    """Comparativo lado a lado dos cenários, já ordenados por risco (melhor primeiro)."""
    lines = [
        f"# Comparativo de cenários — {base_account.account_name}",
        "",
        f"Estágio do deal: {base_account.deal_stage}",
        "",
        "| Cenário | Risco | Sentimento | Consenso | Bloqueadores | Objeção nº 1 |",
        "|---|---|---|---|---|---|",
    ]
    for o in outcomes:
        v = o.verdict
        blockers = ", ".join(r.value for r in v.blocking_stakeholders) or "—"
        top = v.top_objections[0] if v.top_objections else "—"
        lines.append(
            f"| {o.scenario.name} | {o.risk_score:.1f} | {v.overall_sentiment.value} "
            f"| {'sim' if v.consensus_reached else 'não'} | {blockers} | {top} |"
        )

    best = outcomes[0]
    lines += [
        "",
        f"**Cenário recomendado: `{best.scenario.name}`** (menor risco agregado: {best.risk_score:.1f}).",
        "",
    ]

    for o in outcomes:
        v = o.verdict
        lines += [f"## Cenário: {o.scenario.name}", ""]
        if o.scenario.description:
            lines += [f"_{o.scenario.description}_", ""]
        lines += ["Principais objeções:", ""]
        lines += [f"- {obj}" for obj in v.top_objections] or ["- (nenhuma)"]
        lines += ["", "Talk track recomendado:", ""]
        lines += [f"- {t}" for t in v.recommended_talk_track]
        lines += ["", f"Risco: {v.risk_summary}", ""]

    return "\n".join(lines)
