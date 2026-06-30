"""Renders a board-debate result into a sales-facing Markdown report.

This is part of the standard run workflow (see main.py) — every run produces
a report file alongside the console transcript, so reps don't have to copy
terminal output by hand to share a verdict.
"""
from __future__ import annotations

from datetime import datetime, timezone

from digital_twins.models import AccountContext, DebateTurn, DebateVerdict, StakeholderProfile

_SENTIMENT_LABEL = {
    "supportive": "Favorável",
    "neutral": "Neutro",
    "skeptical": "Cético",
    "blocking": "Bloqueador",
}


def build_markdown_report(
    account: AccountContext,
    personas: list[StakeholderProfile],
    transcript: list[DebateTurn],
    verdict: DebateVerdict,
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append(f"# Simulação de Comitê de Compra — {account.account_name}")
    lines.append("")
    lines.append(f"**Gerado em:** {generated_at}  ")
    lines.append(f"**Estágio do deal:** {account.deal_stage}  ")
    if account.deal_value_usd:
        lines.append(f"**Valor do deal:** US$ {account.deal_value_usd:,.0f}  ")
    lines.append("")
    lines.append("## Proposta avaliada")
    lines.append("")
    lines.append(f"- **Pitch:** {account.pitch_summary}")
    lines.append(f"- **Solução proposta:** {account.proposed_solution}")
    lines.append("")

    lines.append("## Comitê simulado")
    lines.append("")
    lines.append("| Stakeholder | Papel | Base de dados | Peso de veto |")
    lines.append("|---|---|---|---|")
    for p in personas:
        source_label = "Dados reais da conta" if p.source.value == "real" else "Arquétipo genérico"
        lines.append(f"| {p.name} | {p.role.value} | {source_label} | {p.decision_power:.2f} |")
    lines.append("")

    lines.append("## Veredito")
    lines.append("")
    consensus_label = "Sim" if verdict.consensus_reached else "Não"
    sentiment_label = _SENTIMENT_LABEL.get(verdict.overall_sentiment.value, verdict.overall_sentiment.value)
    lines.append(f"- **Consenso atingido:** {consensus_label}")
    lines.append(f"- **Sentimento geral:** {sentiment_label}")
    blockers = ", ".join(r.value for r in verdict.blocking_stakeholders) or "Nenhum"
    lines.append(f"- **Stakeholders bloqueadores:** {blockers}")
    lines.append("")

    lines.append("### Principais objeções")
    lines.append("")
    for o in verdict.top_objections:
        lines.append(f"- {o}")
    lines.append("")

    lines.append("### Plano de ação recomendado para o próximo contato")
    lines.append("")
    for i, t in enumerate(verdict.recommended_talk_track, start=1):
        lines.append(f"{i}. {t}")
    lines.append("")

    lines.append("### Avaliação de risco")
    lines.append("")
    lines.append(verdict.risk_summary)
    lines.append("")

    lines.append("## Transcrição completa do debate simulado")
    lines.append("")
    last_round = 0
    for turn in transcript:
        if turn.round_number != last_round:
            last_round = turn.round_number
            lines.append(f"### Rodada {last_round}")
            lines.append("")
        sentiment_label = _SENTIMENT_LABEL.get(turn.sentiment.value, turn.sentiment.value)
        lines.append(f"**{turn.name}** _{sentiment_label}_  ")
        lines.append(f"{turn.statement}")
        lines.append("")

    lines.append("---")
    lines.append(
        "_Relatório gerado automaticamente por uma simulação de IA do comitê de compra. "
        "Use como preparação tática, não como previsão garantida do comportamento real dos stakeholders._"
    )

    return "\n".join(lines)
