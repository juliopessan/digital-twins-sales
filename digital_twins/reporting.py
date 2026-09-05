"""Renders a board-debate result into a sales-facing Markdown report.

This is part of the standard run workflow (see main.py) — every run produces
a report file alongside the console transcript, so reps don't have to copy
terminal output by hand to share a verdict.
"""
from __future__ import annotations

import html
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

    if account.seller_opening:
        lines.append("### Fala de abertura do vendedor")
        lines.append("")
        lines.append(f"> {account.seller_opening}")
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

    if verdict.meddpicc_scorecard:
        lines.append("### Scorecard MEDDPICC")
        lines.append("")
        for dimension, assessment in verdict.meddpicc_scorecard.items():
            lines.append(f"- **{dimension}:** {assessment}")
        lines.append("")

    if verdict.seller_coaching:
        sc = verdict.seller_coaching
        lines.append("## Coach — avaliação do seu pitch")
        lines.append("")
        lines.append(f"**Nota:** {sc.pitch_grade}")
        lines.append("")
        if sc.what_landed:
            lines.append("**O que funcionou:**")
            lines.append("")
            for item in sc.what_landed:
                lines.append(f"- {item}")
            lines.append("")
        if sc.what_backfired:
            lines.append("**O que saiu pela culatra:**")
            lines.append("")
            for item in sc.what_backfired:
                lines.append(f"- {item}")
            lines.append("")
        if sc.rewrite_suggestions:
            lines.append("**Sugestões de reescrita:**")
            lines.append("")
            for i, item in enumerate(sc.rewrite_suggestions, start=1):
                lines.append(f"{i}. {item}")
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


def build_html_report(
    account: AccountContext,
    personas: list[StakeholderProfile],
    transcript: list[DebateTurn],
    verdict: DebateVerdict,
) -> str:
    """Standalone HTML report styled with custom design tokens (palette, typography,
    hero/arc/roadmap/pull-quote/footer components). Opens in any browser, no dependencies."""
    e = html.escape
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    consensus_label = "Sim" if verdict.consensus_reached else "Não"
    sentiment_label = _SENTIMENT_LABEL.get(verdict.overall_sentiment.value, verdict.overall_sentiment.value)
    blockers = ", ".join(r.value for r in verdict.blocking_stakeholders) or "Nenhum"
    value_line = f"US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "—"

    committee_rows = "\n".join(
        f"""<tr>
            <td>{e(p.name)}</td>
            <td>{e(p.role.value)}</td>
            <td>{"Dados reais da conta" if p.source.value == "real" else "Arquétipo genérico"}</td>
            <td>{p.decision_power:.2f}</td>
        </tr>"""
        for p in personas
    )

    objections_html = "\n".join(f"<li>{e(o)}</li>" for o in verdict.top_objections)

    roadmap_html = "\n".join(
        f"""<div class="dt-roadmap-step">
            <div class="dt-roadmap-num">{i}</div>
            <p>{e(t)}</p>
        </div>"""
        for i, t in enumerate(verdict.recommended_talk_track, start=1)
    )

    meddpicc_html = ""
    if verdict.meddpicc_scorecard:
        rows = "\n".join(
            f"<tr><td><strong>{e(dim)}</strong></td><td>{e(assessment)}</td></tr>"
            for dim, assessment in verdict.meddpicc_scorecard.items()
        )
        meddpicc_html = f"""
  <div class="dt-section-bar">Scorecard MEDDPICC</div>
  <table>
    <tr><th>Dimensão</th><th>Avaliação</th></tr>
    {rows}
  </table>
"""

    coaching_html = ""
    if verdict.seller_coaching:
        sc = verdict.seller_coaching

        def _list_block(title: str, items: list[str], ordered: bool = False) -> str:
            if not items:
                return ""
            tag = "ol" if ordered else "ul"
            lis = "\n".join(f"<li>{e(i)}</li>" for i in items)
            return f"<p><strong>{title}</strong></p><{tag}>{lis}</{tag}>"

        coaching_html = f"""
  <div class="dt-section-bar">Coach — avaliação do seu pitch</div>
  <div class="dt-pullquote">{e(sc.pitch_grade)}</div>
  {_list_block("O que funcionou", sc.what_landed)}
  {_list_block("O que saiu pela culatra", sc.what_backfired)}
  {_list_block("Sugestões de reescrita", sc.rewrite_suggestions, ordered=True)}
"""

    transcript_html_parts: list[str] = []
    last_round = 0
    for turn in transcript:
        if turn.round_number != last_round:
            last_round = turn.round_number
            transcript_html_parts.append(f'<div class="dt-section-bar">Rodada {last_round}</div>')
        turn_sentiment = _SENTIMENT_LABEL.get(turn.sentiment.value, turn.sentiment.value)
        transcript_html_parts.append(
            f"""<div class="dt-turn">
                <span class="dt-turn-name">{e(turn.name)} · {e(turn_sentiment)}</span>
                <p>{e(turn.statement)}</p>
            </div>"""
        )
    transcript_html = "\n".join(transcript_html_parts)

    seller_opening_html = ""
    if account.seller_opening:
        seller_opening_html = (
            '<div class="dt-section-bar">Fala de abertura do vendedor</div>'
            f'<div class="dt-pullquote">{e(account.seller_opening)}</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Simulação de Comitê — {e(account.account_name)}</title>
<style>
:root {{
  --dt-orange: #FF5800;
  --dt-dark-orange: #DC4600;
  --dt-grey-80: #333333;
  --dt-grey-60: #666666;
  --dt-grey-40: #999999;
  --dt-grey-20: #cccccc;
  --dt-grey-10: #e5e5e5;
  --dt-aurora: #890078;
}}
body {{
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  color: var(--dt-grey-80);
  background: #fafafa;
  margin: 0;
  padding: 0 0 48px 0;
}}
.dt-container {{ max-width: 880px; margin: 0 auto; padding: 0 24px; }}
.dt-hero {{
  background: linear-gradient(135deg, #FF5800 0%, #890078 100%);
  color: #fff; padding: 48px 40px; position: relative; overflow: hidden;
}}
.dt-hero::after {{
  content: ""; position: absolute; right: -120px; top: -120px;
  width: 420px; height: 420px;
  background: radial-gradient(circle, rgba(255,215,0,.45) 0%, rgba(255,215,0,0) 70%);
}}
.dt-hero .kicker {{ font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; opacity: .9; margin-bottom: 12px; }}
.dt-hero h1 {{ font-weight: 300; font-size: 36px; margin: 0 0 8px 0; max-width: 22ch; }}
.dt-hero h1 b {{ font-weight: 700; }}
.dt-hero .lede {{ font-weight: 300; opacity: .95; max-width: 70ch; margin: 4px 0; }}

.dt-arc {{
  background: #fff; border-top: 4px solid var(--dt-orange);
  box-shadow: 0 4px 12px rgba(0,0,0,0.10); display: flex; margin: -24px 24px 32px 24px;
  position: relative; z-index: 2; border-radius: 4px;
}}
.dt-arc-cell {{ flex: 1; padding: 20px 16px; border-right: 1px solid var(--dt-grey-10); text-align: center; }}
.dt-arc-cell:last-child {{ border-right: none; }}
.dt-arc-big {{ font-weight: 700; font-size: 28px; color: var(--dt-dark-orange); }}
.dt-arc-label {{ font-weight: 600; font-size: 12.5px; margin-top: 4px; }}

.dt-section-bar {{
  border-left: 4px solid var(--dt-orange); padding-left: 14px; margin: 36px 0 16px 0;
  font-weight: 600; font-size: 21px;
}}

table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--dt-grey-10); }}
th {{ color: var(--dt-grey-60); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}

.dt-pullquote {{
  background: var(--dt-orange); color: #fff; font-weight: 400; font-size: 22px;
  line-height: 1.4; padding: 28px 32px; border-radius: 4px; margin: 16px 0;
}}

.dt-roadmap-step {{
  background: #fff; border: 1px solid var(--dt-grey-10); border-radius: 8px;
  padding: 16px 18px; margin-bottom: 12px; display: flex; gap: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}}
.dt-roadmap-num {{
  flex: 0 0 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, #FFD700 0%, #FF5800 100%);
  color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 14px;
}}
.dt-roadmap-step p {{ margin: 0; font-size: 14.5px; }}

.dt-turn {{ border-left: 3px solid var(--dt-grey-20); padding-left: 14px; margin-bottom: 16px; }}
.dt-turn-name {{ font-weight: 600; font-size: 13px; color: var(--dt-dark-orange); text-transform: uppercase; letter-spacing: .02em; }}
.dt-turn p {{ margin: 6px 0 0 0; font-size: 14.5px; line-height: 1.6; }}

.dt-footer {{
  background: var(--dt-grey-80); color: var(--dt-grey-40);
  padding: 28px 40px; margin-top: 48px; font-size: 12px; line-height: 1.7;
}}
.dt-footer b {{ color: #fff; }}

@media (prefers-color-scheme: dark) {{
  :root {{
    --dt-grey-80: #e5e5e5;
    --dt-grey-60: #b0b0b0;
    --dt-grey-40: #808080;
    --dt-grey-20: #4a4a4a;
    --dt-grey-10: #2a2a2a;
  }}
  body {{
    color: #e5e5e5;
    background: #1a1a1a;
  }}
  .dt-arc {{
    background: #2a2a2a;
    box-shadow: 0 4px 12px rgba(0,0,0,0.40);
  }}
  .dt-arc-big {{
    color: #FFD700;
  }}
  .dt-roadmap-step {{
    background: #2a2a2a;
    border-color: #4a4a4a;
    box-shadow: 0 4px 12px rgba(0,0,0,0.40);
  }}
  table {{
    color: #e5e5e5;
  }}
  th {{
    color: #b0b0b0;
  }}
  .dt-turn {{
    border-left-color: #4a4a4a;
  }}
  .dt-turn-name {{
    color: #FFD700;
  }}
  .dt-turn p {{
    color: #d0d0d0;
  }}
  .dt-footer {{
    background: #0f0f0f;
    color: #808080;
  }}
  .dt-footer b {{
    color: #e5e5e5;
  }}
  ul, ol {{
    color: #e5e5e5;
  }}
  ul li, ol li {{
    color: #d0d0d0;
  }}
  p {{
    color: #d0d0d0;
  }}
  .dt-section-bar {{
    color: #e5e5e5;
  }}
}}
</style>
</head>
<body>
<div class="dt-hero">
  <div class="dt-container">
    <div class="kicker">Sales Digital Twins · Board Simulator</div>
    <h1>Simulação de Comitê — <b>{e(account.account_name)}</b></h1>
    <div class="lede">{e(account.pitch_summary)}</div>
    <div class="lede"><strong>Estágio:</strong> {e(account.deal_stage)} &nbsp;·&nbsp; <strong>Valor:</strong> {value_line} &nbsp;·&nbsp; Gerado em {generated_at}</div>
  </div>
</div>

<div class="dt-arc">
  <div class="dt-arc-cell"><div class="dt-arc-big">{consensus_label}</div><div class="dt-arc-label">Consenso atingido</div></div>
  <div class="dt-arc-cell"><div class="dt-arc-big">{e(sentiment_label)}</div><div class="dt-arc-label">Sentimento geral</div></div>
  <div class="dt-arc-cell"><div class="dt-arc-big">{len(verdict.blocking_stakeholders)}</div><div class="dt-arc-label">Bloqueadores</div></div>
  <div class="dt-arc-cell"><div class="dt-arc-big">{len(verdict.top_objections)}</div><div class="dt-arc-label">Objeções</div></div>
</div>

<div class="dt-container">
  <div class="dt-section-bar">Proposta avaliada</div>
  <p><strong>Solução proposta:</strong> {e(account.proposed_solution)}</p>
  {seller_opening_html}
  <div class="dt-section-bar">Comitê simulado</div>
  <table>
    <tr><th>Stakeholder</th><th>Papel</th><th>Base de dados</th><th>Peso de veto</th></tr>
    {committee_rows}
  </table>

  <div class="dt-section-bar">Stakeholders bloqueadores</div>
  <div class="dt-pullquote">{e(blockers)}</div>

  <div class="dt-section-bar">Principais objeções</div>
  <ul>{objections_html}</ul>

  <div class="dt-section-bar">Plano de ação recomendado</div>
  {roadmap_html}

  <div class="dt-section-bar">Avaliação de risco</div>
  <p>{e(verdict.risk_summary)}</p>
  {meddpicc_html}
  {coaching_html}
  <div class="dt-section-bar">Transcrição completa do debate simulado</div>
  {transcript_html}
</div>

<div class="dt-footer">
  <b>Relatório gerado automaticamente</b> por uma simulação de IA do comitê de compra.
  Use como preparação tática, não como previsão garantida do comportamento real dos stakeholders.<br>
  Visual: tokens de design proprietário v1.1.
</div>
</body>
</html>"""
