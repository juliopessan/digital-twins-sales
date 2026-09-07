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
    "supportive": "Supportive",
    "neutral": "Neutral",
    "skeptical": "Skeptical",
    "blocking": "Blocking",
}


def build_markdown_report(
    account: AccountContext,
    personas: list[StakeholderProfile],
    transcript: list[DebateTurn],
    verdict: DebateVerdict,
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append(f"# Buying Committee Simulation — {account.account_name}")
    lines.append("")
    lines.append(f"**Generated at:** {generated_at}  ")
    lines.append(f"**Deal stage:** {account.deal_stage}  ")
    if account.deal_value_usd:
        lines.append(f"**Deal value:** US$ {account.deal_value_usd:,.0f}  ")
    lines.append("")
    lines.append("## Proposal evaluated")
    lines.append("")
    lines.append(f"- **Pitch:** {account.pitch_summary}")
    lines.append(f"- **Proposed solution:** {account.proposed_solution}")
    lines.append("")

    if account.seller_opening:
        lines.append("### Seller's opening statement")
        lines.append("")
        lines.append(f"> {account.seller_opening}")
        lines.append("")

    lines.append("## Simulated committee")
    lines.append("")
    lines.append("| Stakeholder | Role | Data source | Veto weight |")
    lines.append("|---|---|---|---|")
    for p in personas:
        source_label = "Real account data" if p.source.value == "real" else "Generic archetype"
        lines.append(f"| {p.name} | {p.role.value} | {source_label} | {p.decision_power:.2f} |")
    lines.append("")

    lines.append("## Verdict")
    lines.append("")
    consensus_label = "Yes" if verdict.consensus_reached else "No"
    sentiment_label = _SENTIMENT_LABEL.get(verdict.overall_sentiment.value, verdict.overall_sentiment.value)
    lines.append(f"- **Consensus reached:** {consensus_label}")
    lines.append(f"- **Overall sentiment:** {sentiment_label}")
    blockers = ", ".join(r.value for r in verdict.blocking_stakeholders) or "None"
    lines.append(f"- **Blocking stakeholders:** {blockers}")
    lines.append("")

    lines.append("### Top objections")
    lines.append("")
    for o in verdict.top_objections:
        lines.append(f"- {o}")
    lines.append("")

    lines.append("### Recommended action plan for the next touchpoint")
    lines.append("")
    for i, t in enumerate(verdict.recommended_talk_track, start=1):
        lines.append(f"{i}. {t}")
    lines.append("")

    lines.append("### Risk assessment")
    lines.append("")
    lines.append(verdict.risk_summary)
    lines.append("")

    if verdict.meddpicc_scorecard:
        lines.append("### MEDDPICC scorecard")
        lines.append("")
        for dimension, assessment in verdict.meddpicc_scorecard.items():
            lines.append(f"- **{dimension}:** {assessment}")
        lines.append("")

    if verdict.seller_coaching:
        sc = verdict.seller_coaching
        lines.append("## Coach — your pitch review")
        lines.append("")
        lines.append(f"**Grade:** {sc.pitch_grade}")
        lines.append("")
        if sc.what_landed:
            lines.append("**What landed:**")
            lines.append("")
            for item in sc.what_landed:
                lines.append(f"- {item}")
            lines.append("")
        if sc.what_backfired:
            lines.append("**What backfired:**")
            lines.append("")
            for item in sc.what_backfired:
                lines.append(f"- {item}")
            lines.append("")
        if sc.rewrite_suggestions:
            lines.append("**Rewrite suggestions:**")
            lines.append("")
            for i, item in enumerate(sc.rewrite_suggestions, start=1):
                lines.append(f"{i}. {item}")
            lines.append("")

    lines.append("## Full transcript of the simulated debate")
    lines.append("")
    last_round = 0
    for turn in transcript:
        if turn.round_number != last_round:
            last_round = turn.round_number
            lines.append(f"### Round {last_round}")
            lines.append("")
        sentiment_label = _SENTIMENT_LABEL.get(turn.sentiment.value, turn.sentiment.value)
        lines.append(f"**{turn.name}** _{sentiment_label}_  ")
        lines.append(f"{turn.statement}")
        lines.append("")

    lines.append("---")
    lines.append(
        "_This report was generated automatically by an AI simulation of the buying committee. "
        "Use it as tactical preparation, not as a guaranteed prediction of real stakeholder behavior._"
    )

    return "\n".join(lines)


_ROLE_LABEL_EN = {
    "salesman": "Salesperson",
    "ceo": "CEO",
    "cto": "CTO",
    "cfo": "CFO",
    "procurement": "Procurement",
    "champion": "Internal champion",
    "end_user": "End user",
    "legal_compliance": "Legal/Compliance",
    "security": "Security",
}


def build_html_report(
    account: AccountContext,
    personas: list[StakeholderProfile],
    transcript: list[DebateTurn],
    verdict: DebateVerdict,
) -> str:
    """Standalone HTML report using the Ledger design system — the same one applied
    to the Next.js results page (web/app/runs/[id]/page.tsx) — so a downloaded
    report and the live run look like the same product. The ledger's clay/mint
    pair marks the same measured/asserted split as the web UI: total committee
    vs. personas grounded in real data is computed from the objects passed in
    here; everything else (objections, verdict, coaching) is left unmarked, per
    the Ledger rule against badging anything that wasn't actually verified."""
    e = html.escape
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    consensus_label = "Yes" if verdict.consensus_reached else "No"
    sentiment_label = _SENTIMENT_LABEL.get(verdict.overall_sentiment.value, verdict.overall_sentiment.value)
    value_line = f"US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "—"

    committee = [p for p in personas if p.role.value != "salesman"]
    real_personas = [p for p in committee if p.source.value == "real"]
    archetype_personas = [p for p in committee if p.source.value == "archetype"]
    real_pct = (len(real_personas) / len(committee) * 100) if committee else 0
    rounds = max((t.round_number for t in transcript), default=0)

    def role_label(role_value: str) -> str:
        return _ROLE_LABEL_EN.get(role_value, role_value)

    committee_rows = "\n".join(
        f"""<tr>
            <td>{e(role_label(p.role.value))}</td>
            <td>{e(p.name)}</td>
            <td><span class="pill {"pill-mint" if p.source.value == "real" else "pill-clay"}">{"real" if p.source.value == "real" else "archetype"}</span></td>
            <td class="num">{p.decision_power:.2f}</td>
            <td>{e(", ".join(p.priorities[:3]))}</td>
        </tr>"""
        for p in committee
    )

    objections_html = "\n".join(f"<li>{e(o)}</li>" for o in verdict.top_objections)

    roadmap_html = "\n".join(f"<li>{e(t)}</li>" for t in verdict.recommended_talk_track)

    blockers_html = ""
    if verdict.blocking_stakeholders:
        blockers = ", ".join(role_label(r.value) for r in verdict.blocking_stakeholders)
        blockers_html = f"""
  <div class="flag">
    <span class="flag-k">Blockers</span>
    <p>{e(blockers)}</p>
  </div>"""

    meddpicc_html = ""
    if verdict.meddpicc_scorecard:
        rows = "\n".join(
            f"<tr><td style=\"text-transform:capitalize\">{e(dim)}</td><td>{e(assessment)}</td></tr>"
            for dim, assessment in verdict.meddpicc_scorecard.items()
        )
        meddpicc_html = f"""
  <div class="tbl-wrap">
    <table>
      <tr><th>MEDDPICC</th><th>Assessment</th></tr>
      {rows}
    </table>
  </div>"""

    coaching_html = ""
    if verdict.seller_coaching:
        sc = verdict.seller_coaching

        def _joined(items: list[str]) -> str:
            return e(" · ".join(items)) if items else "—"

        coaching_html = f"""
  <div class="card">
    <p class="h3">Coach — grade: <span class="mono">{e(sc.pitch_grade)}</span></p>
    <p class="body-text"><strong>What landed:</strong> {_joined(sc.what_landed)}</p>
    <p class="body-text"><strong>What backfired:</strong> {_joined(sc.what_backfired)}</p>
    <p class="body-text" style="margin-bottom:0"><strong>Rewrite it like this:</strong> {_joined(sc.rewrite_suggestions)}</p>
  </div>"""

    transcript_html_parts: list[str] = []
    for turn in transcript:
        turn_sentiment = _SENTIMENT_LABEL.get(turn.sentiment.value, turn.sentiment.value)
        objections_li = "\n".join(f"<li>{e(o)}</li>" for o in turn.objections_raised)
        transcript_html_parts.append(
            f"""<div class="card">
        <div class="row" style="justify-content:space-between; margin-bottom:10px">
          <span class="h3" style="margin:0">{e(turn.name)} · {e(role_label(turn.role.value))}</span>
          <span class="mono meta">round {turn.round_number} · {e(turn_sentiment)}</span>
        </div>
        <p class="body-text" style="max-width:none">{e(turn.statement)}</p>
        {f'<ul style="margin:10px 0 0; padding-left:18px">{objections_li}</ul>' if turn.objections_raised else ""}
      </div>"""
        )
    transcript_html = "\n".join(transcript_html_parts)

    measured_html = ""
    if real_personas:
        names = ", ".join(f"{e(p.name)} ({e(role_label(p.role.value))})" for p in real_personas)
        verb = "has statements backed" if len(real_personas) == 1 else "have statements backed"
        measured_html = f"""
  <div class="measured">
    <span class="tick">✓</span>
    <p><span class="k">Grounded in real data</span>{names} {verb} by verifiable facts
    collected about the real person.</p>
  </div>"""

    flag_html = ""
    if archetype_personas:
        names = ", ".join(f"{e(p.name)} ({e(role_label(p.role.value))})" for p in archetype_personas)
        verb = "has" if len(archetype_personas) == 1 else "have"
        pronoun = "their reaction" if len(archetype_personas) == 1 else "their reactions"
        flag_html = f"""
  <div class="flag">
    <span class="flag-k">No real data</span>
    <p>{names} {verb} no real fact attached — {"their statement comes" if len(archetype_personas) == 1 else "their statements come"}
    from a generic role archetype. Treat {pronoun} as illustrative, not predictive.</p>
  </div>"""

    seller_opening_html = ""
    if account.seller_opening:
        seller_opening_html = f"""
  <p class="body-text" style="max-width:none"><strong>Seller's opening statement:</strong></p>
  <p class="body-text" style="max-width:none; font-style:italic">"{e(account.seller_opening)}"</p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Committee Simulation — {e(account.account_name)}</title>
<style>
:root {{
  --display: "Helvetica Neue", Helvetica, Arial, sans-serif;
  --voice: Georgia, "Times New Roman", serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, monospace;
  --paper: #f2efe8; --paper-deep: #e7e3da; --rule: #d6d2c8;
  --ink: #11110f; --ink-soft: #55524b; --ink-faint: #9c988e;
  --clay: #ed6738; --clay-deep: #c8481c; --mint: #4f9c6b;
  --ledger-bg: #14140f; --ledger-ink: #efece4; --ledger-dim: #85817a;
  --ledger-rule: #2c2b25; --ledger-mint: #8fcfa6;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --paper: #12120e; --paper-deep: #1b1b16; --rule: #2e2d27;
    --ink: #f0ede5; --ink-soft: #a8a49b; --ink-faint: #6d6a63;
    --clay: #f57d51; --clay-deep: #ff9a71; --mint: #7fc79a;
    --ledger-bg: #0b0b08; --ledger-rule: #232219;
  }}
}}
* {{ box-sizing: border-box; }}
html, body {{ background: var(--paper); color: var(--ink); font-family: var(--display); margin: 0; padding: 0; }}
body {{ font-size: 15px; line-height: 1.5; }}
.page {{ max-width: 880px; margin: 0 auto; padding: 56px 32px 80px; }}
.eyebrow {{
  display: flex; align-items: center; gap: 14px; font-family: var(--mono); font-size: 11px;
  font-weight: 500; letter-spacing: .17em; text-transform: uppercase; color: var(--ink-faint); margin: 0 0 20px;
}}
.eyebrow::before {{ content: ""; width: 40px; height: 1px; background: var(--ink-faint); flex: none; }}
.display {{ font-weight: 800; letter-spacing: -0.03em; line-height: 1.05; font-size: 40px; margin: 0 0 18px; }}
.voice {{ font-family: var(--voice); font-weight: 400; font-style: italic; letter-spacing: -0.01em; }}
.lede {{ font-size: 16px; line-height: 1.6; color: var(--ink-soft); max-width: 62ch; margin: 0 0 12px; }}
.h3, .card p.h3 {{ font-size: 17px; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 12px; }}
.body-text {{ font-size: 14.5px; line-height: 1.65; color: var(--ink-soft); max-width: 68ch; }}
.mono {{ font-family: var(--mono); }}
.meta {{ font-size: 11px; color: var(--ink-faint); }}

.ledger {{
  background: var(--ledger-bg); color: var(--ledger-ink); padding: 26px 28px;
  display: flex; flex-direction: column; gap: 20px; margin: 32px 0 40px;
}}
.ledger-head {{
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  font-family: var(--mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
}}
.ledger-head .live {{ display: flex; align-items: center; gap: 9px; }}
.ledger-head .live::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--ledger-mint); }}
.ledger-head .meta {{ color: var(--ledger-dim); }}
.bar-row {{ display: flex; flex-direction: column; gap: 9px; padding-top: 18px; border-top: 1px solid var(--ledger-rule); }}
.bar-label {{ display: flex; align-items: baseline; justify-content: space-between; gap: 16px; font-family: var(--mono); font-size: 12.5px; color: var(--ledger-dim); }}
.bar-label b {{ font-family: var(--display); font-weight: 700; font-size: 24px; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; color: var(--ledger-ink); }}
.bar-track {{ height: 5px; background: var(--ledger-rule); }}
.bar-fill {{ height: 100%; }}
.figs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 20px 24px; padding-top: 18px; border-top: 1px solid var(--ledger-rule); }}
.fig {{ display: flex; align-items: baseline; gap: 9px; }}
.fig b {{ font-family: var(--display); font-weight: 700; font-size: 24px; letter-spacing: -0.025em; font-variant-numeric: tabular-nums; color: var(--ledger-ink); }}
.fig span {{ font-family: var(--mono); font-size: 11.5px; color: var(--ledger-dim); }}

.measured {{ display: flex; gap: 14px; border: 1px solid var(--rule); padding: 15px 16px; margin: 0 0 20px; }}
.measured .tick {{ flex: none; width: 26px; height: 26px; display: grid; place-items: center; background: var(--mint); color: #fff; font-size: 14px; font-weight: 700; }}
.measured p {{ font-size: 13.5px; line-height: 1.55; color: var(--ink); margin: 0; }}
.measured .k {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-faint); display: block; margin-bottom: 5px; }}

.flag {{
  border-left: 2px solid var(--clay); background: color-mix(in srgb, var(--clay) 9%, transparent);
  padding: 15px 18px; display: flex; flex-direction: column; gap: 7px; margin: 0 0 20px;
}}
.flag-k {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--clay-deep); }}
.flag p {{ font-size: 13.5px; color: var(--ink-soft); margin: 0; }}

.pill {{
  display: inline-flex; align-items: center; font-family: var(--mono); font-size: 10.5px;
  letter-spacing: .1em; text-transform: uppercase; padding: 3px 9px; border: 1px solid var(--rule);
}}
.pill-mint {{ border-color: var(--mint); color: var(--mint); }}
.pill-clay {{ border-color: var(--clay); color: var(--clay); }}

.section {{ border-top: 1px solid var(--rule); padding: 40px 0; }}
.section:first-of-type {{ padding-top: 0; border-top: none; }}
.tbl-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--rule); }}
th {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .13em; text-transform: uppercase; color: var(--ink-faint); font-weight: 500; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; font-family: var(--mono); font-size: 12.5px; }}
.card {{ border: 1px solid var(--rule); padding: 18px 20px; margin-bottom: 14px; }}
.row {{ display: flex; align-items: center; }}
ul, ol {{ color: var(--ink-soft); }}
</style>
</head>
<body>
<div class="page">
  <p class="eyebrow">Sales Digital Twins — {e(account.account_name)}</p>
  <h1 class="display">The committee reacted. <span class="voice">Now the read is yours.</span></h1>
  <p class="lede">{e(account.pitch_summary)}</p>
  <p class="body-text" style="max-width:none">{e(account.proposed_solution)}</p>
  {seller_opening_html}

  <div class="ledger">
    <div class="ledger-head">
      <span class="live">Completed</span>
      <span class="meta">{e(account.deal_stage)} · generated at {generated_at}{f" · {value_line}" if account.deal_value_usd else ""}</span>
    </div>
    <div class="bar-row">
      <div class="bar-label"><span>Simulated committee</span><b>{len(committee)}</b></div>
      <div class="bar-track"><div class="bar-fill" style="width:100%; background:var(--clay)"></div></div>
      <div class="bar-label"><span>Grounded in real data</span><b>{len(real_personas)}</b></div>
      <div class="bar-track"><div class="bar-fill" style="width:{real_pct:.0f}%; background:var(--ledger-mint)"></div></div>
    </div>
    <div class="figs">
      <div class="fig"><b>{rounds}</b><span>rounds</span></div>
      <div class="fig"><b>{len(transcript)}</b><span>debate turns</span></div>
      <div class="fig"><b>{len(verdict.blocking_stakeholders)}</b><span>blockers</span></div>
      <div class="fig"><b>{len(verdict.top_objections)}</b><span>objections</span></div>
    </div>
  </div>

  {measured_html}
  {flag_html}

  <div class="section">
    <p class="eyebrow">Committee</p>
    <div class="tbl-wrap">
      <table>
        <tr><th>Role</th><th>Name</th><th>Source</th><th>Decision weight</th><th>Priorities</th></tr>
        {committee_rows}
      </table>
    </div>
  </div>

  <div class="section">
    <p class="eyebrow">Debate transcript</p>
    {transcript_html}
  </div>

  <div class="section">
    <p class="eyebrow">Verdict</p>
    <p class="lede">{"The committee reached a " + '<span class="voice">consensus.</span>' if verdict.consensus_reached else 'The committee <span class="voice">did not reach a consensus.</span>'}</p>
    <p class="body-text" style="max-width:none; margin-bottom:20px">{e(verdict.risk_summary)}</p>
    {blockers_html}
    <p class="h3" style="margin-top:24px">Top objections</p>
    <ul>{objections_html}</ul>
    <p class="h3" style="margin-top:24px">Recommended action plan</p>
    <ol>{roadmap_html}</ol>
    {meddpicc_html}
    {coaching_html}
  </div>

  <p class="meta" style="margin-top:40px">
    This report was generated automatically by an AI simulation of the buying committee.
    Use it as tactical preparation, not as a guaranteed prediction of real stakeholder behavior.
  </p>
</div>
</body>
</html>"""
