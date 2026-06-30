"""
Streamlit front-end for the Sales Digital Twins board simulator.

    streamlit run streamlit_app.py

Visual language: Avanade design tokens (palette, typography, components)
applied to the report layout; the debate transcript itself is rendered as a
pixel-art "office" of stakeholder characters with speech bubbles, inspired by
pixel-agents-hq/pixel-agents (a Claude Code session visualizer) — reimplemented
natively in HTML/CSS here since that project is TypeScript-only and purpose-built
for VS Code/terminal hook events, not portable as a Python dependency.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from digital_twins.config import settings
from digital_twins.llm.client import build_default_client
from digital_twins.models import AccountContext, StakeholderRole
from digital_twins.orchestration.graph import build_board_graph
from digital_twins.personas.resolver import PersonaFactory
from digital_twins.reporting import build_html_report, build_markdown_report

ACCOUNTS_DIR = Path(__file__).parent / "accounts"

ROLE_ICON = {
    StakeholderRole.CEO: "👑",
    StakeholderRole.CTO: "💻",
    StakeholderRole.CFO: "💰",
    StakeholderRole.PROCUREMENT: "📋",
    StakeholderRole.CHAMPION: "🚀",
    StakeholderRole.END_USER: "🧑‍💼",
    StakeholderRole.LEGAL_COMPLIANCE: "⚖️",
    StakeholderRole.SECURITY: "🔒",
}

# Avanade thermal gradient family, used as a deterministic per-role color cycle.
ROLE_COLOR_CYCLE = ["#FFD700", "#FFB414", "#FF5800", "#B43C14", "#C80000", "#890078"]

SENTIMENT_COLOR = {
    "supportive": "#00A650",
    "neutral": "#7f7f7f",
    "skeptical": "#FFB414",
    "blocking": "#C80000",
}
SENTIMENT_LABEL_PT = {
    "supportive": "Favorável",
    "neutral": "Neutro",
    "skeptical": "Cético",
    "blocking": "Bloqueador",
}


def _role_color(role_value: str) -> str:
    idx = sum(ord(c) for c in role_value) % len(ROLE_COLOR_CYCLE)
    return ROLE_COLOR_CYCLE[idx]


def _sample_account() -> AccountContext:
    return AccountContext(
        account_name="Northwind Logistics",
        deal_stage="Proposal sent, awaiting committee review",
        pitch_summary=(
            "Multi-agent Gen AI platform to automate freight document processing, "
            "replacing a 14-person manual review team with a 3-person oversight team."
        ),
        proposed_solution=(
            "Azure-hosted agentic pipeline: OCR + extraction agents + human-in-the-loop "
            "exception handling, 18-week implementation, $640k Year 1 (license + services)."
        ),
        deal_value_usd=640_000,
        roles_in_committee=[
            StakeholderRole.CHAMPION,
            StakeholderRole.CTO,
            StakeholderRole.CFO,
            StakeholderRole.PROCUREMENT,
        ],
        real_data={
            StakeholderRole.CFO: [
                "Posted on LinkedIn last quarter about 'doing more with less' after a hiring freeze",
                "Previously rejected a similar automation vendor over unclear ROI math",
                "Reports to a CEO who publicly committed to 15% opex reduction this fiscal year",
            ]
        },
    )


def _inject_avanade_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

        :root {
            --ava-orange: #FF5800;
            --ava-dark-orange: #DC4600;
            --ava-grey-80: #333333;
            --ava-grey-60: #666666;
            --ava-grey-40: #999999;
            --ava-grey-20: #cccccc;
            --ava-grey-10: #e5e5e5;
            --ava-solar: #FFD700;
            --ava-aurora: #890078;
        }

        html, body, [class*="css"] {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            color: var(--ava-grey-80);
        }

        .ava-hero {
            background: linear-gradient(135deg, #FF5800 0%, #890078 100%);
            color: #fff;
            padding: 40px 36px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            margin-bottom: 24px;
        }
        .ava-hero::after {
            content: "";
            position: absolute;
            right: -100px; top: -100px;
            width: 360px; height: 360px;
            background: radial-gradient(circle, rgba(255,215,0,.45) 0%, rgba(255,215,0,0) 70%);
        }
        .ava-hero h1 { font-weight: 300; font-size: 34px; margin: 0 0 6px 0; }
        .ava-hero h1 b { font-weight: 700; }
        .ava-hero .kicker {
            font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase;
            opacity: .9; margin-bottom: 10px;
        }
        .ava-hero .lede { font-weight: 300; opacity: .95; max-width: 70ch; }

        .ava-arc {
            background: #fff; border-top: 4px solid var(--ava-orange);
            box-shadow: 0 4px 12px rgba(0,0,0,0.10);
            border-radius: 4px; display: flex; margin-bottom: 24px;
        }
        .ava-arc-cell { flex: 1; padding: 18px 16px; border-right: 1px solid var(--ava-grey-10); text-align: center; }
        .ava-arc-cell:last-child { border-right: none; }
        .ava-arc-big { font-weight: 700; font-size: 28px; color: var(--ava-dark-orange); }
        .ava-arc-label { font-weight: 600; font-size: 12.5px; color: var(--ava-grey-80); margin-top: 4px; }

        .ava-section-bar {
            border-left: 4px solid var(--ava-orange);
            padding-left: 12px; margin: 28px 0 12px 0;
            font-weight: 600; font-size: 19px; color: var(--ava-grey-80);
        }

        .ava-roadmap-step {
            background: #fff; border: 1px solid var(--ava-grey-10); border-radius: 8px;
            padding: 14px 16px; margin-bottom: 10px; display: flex; gap: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        }
        .ava-roadmap-num {
            flex: 0 0 30px; height: 30px; border-radius: 50%;
            background: linear-gradient(135deg, #FFD700 0%, #FF5800 100%);
            color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center;
            font-size: 13px;
        }
        .ava-roadmap-step p { margin: 0; font-size: 14px; color: var(--ava-grey-80); }

        /* Pixel office — debate transcript */
        .pixel-office {
            background: var(--ava-grey-80);
            background-image:
                linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
            background-size: 24px 24px;
            border-radius: 8px; padding: 24px; margin-bottom: 12px;
        }
        .pixel-round-label {
            font-family: 'Press Start 2P', monospace; font-size: 11px; color: var(--ava-solar);
            margin: 18px 0 12px 0; letter-spacing: .05em;
        }
        .pixel-turn { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 16px; }
        .pixel-avatar {
            flex: 0 0 48px; width: 48px; height: 48px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px; border-radius: 4px; image-rendering: pixelated;
            border: 3px solid rgba(0,0,0,.35); box-shadow: 0 0 0 2px rgba(255,255,255,.15) inset;
        }
        .pixel-bubble {
            background: #fff; border-radius: 0 10px 10px 10px; padding: 12px 16px;
            max-width: 720px; position: relative; box-shadow: 0 4px 10px rgba(0,0,0,.25);
        }
        .pixel-name {
            font-family: 'Press Start 2P', monospace; font-size: 10px; margin-bottom: 6px;
            display: inline-block; padding: 2px 8px; border-radius: 3px; color: #fff;
        }
        .pixel-text { font-size: 14px; color: var(--ava-grey-80); line-height: 1.5; }

        .ava-footnote { font-size: 11.5px; color: var(--ava-grey-40); margin-top: 18px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(account: AccountContext) -> None:
    value = f"US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "—"
    st.markdown(
        f"""
        <div class="ava-hero">
            <div class="kicker">Sales Digital Twins · Board Simulator</div>
            <h1>Simulação de comitê — <b>{account.account_name}</b></h1>
            <div class="lede">{account.pitch_summary}</div>
            <div class="lede" style="margin-top:8px; font-weight:600;">
                Estágio: {account.deal_stage} &nbsp;·&nbsp; Valor: {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_arc(verdict) -> None:
    consensus = "Sim" if verdict.consensus_reached else "Não"
    sentiment = SENTIMENT_LABEL_PT.get(verdict.overall_sentiment.value, verdict.overall_sentiment.value)
    blockers = len(verdict.blocking_stakeholders)
    st.markdown(
        f"""
        <div class="ava-arc">
            <div class="ava-arc-cell"><div class="ava-arc-big">{consensus}</div><div class="ava-arc-label">Consenso atingido</div></div>
            <div class="ava-arc-cell"><div class="ava-arc-big">{sentiment}</div><div class="ava-arc-label">Sentimento geral</div></div>
            <div class="ava-arc-cell"><div class="ava-arc-big">{blockers}</div><div class="ava-arc-label">Stakeholders bloqueadores</div></div>
            <div class="ava-arc-cell"><div class="ava-arc-big">{len(verdict.top_objections)}</div><div class="ava-arc-label">Objeções levantadas</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pixel_office(transcript) -> None:
    html = ['<div class="pixel-office">']
    last_round = 0
    for turn in transcript:
        if turn.round_number != last_round:
            last_round = turn.round_number
            html.append(f'<div class="pixel-round-label">ROUND {last_round}</div>')
        icon = ROLE_ICON.get(turn.role, "🧑")
        color = _role_color(turn.role.value)
        sent_color = SENTIMENT_COLOR.get(turn.sentiment.value, "#666")
        sent_label = SENTIMENT_LABEL_PT.get(turn.sentiment.value, turn.sentiment.value)
        html.append(
            f"""
            <div class="pixel-turn">
                <div class="pixel-avatar" style="background:{color};">{icon}</div>
                <div class="pixel-bubble">
                    <span class="pixel-name" style="background:{sent_color};">{turn.name} · {sent_label}</span>
                    <div class="pixel-text">{turn.statement}</div>
                </div>
            </div>
            """
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_roadmap(items: list[str]) -> None:
    for i, item in enumerate(items, start=1):
        st.markdown(
            f"""
            <div class="ava-roadmap-step">
                <div class="ava-roadmap-num">{i}</div>
                <p>{item}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(page_title="Sales Digital Twins — Board Simulator", layout="wide")
    _inject_avanade_theme()

    with st.sidebar:
        st.header("Configuração da rodada")

        account_options = {"Northwind Logistics (exemplo)": None}
        if ACCOUNTS_DIR.exists():
            for f in sorted(ACCOUNTS_DIR.glob("*.json")):
                account_options[f.stem] = f
        account_options["Carregar JSON customizado"] = "upload"

        choice = st.selectbox("Conta", list(account_options.keys()))
        uploaded = None
        if account_options[choice] == "upload":
            uploaded = st.file_uploader("AccountContext (.json)", type="json")

        mock_mode = st.checkbox("Modo mock (sem API, gratuito)", value=True)
        api_key = None
        if not mock_mode:
            api_key = st.text_input("Anthropic API Key", type="password")
            st.caption("A chave é usada só em memória nesta sessão — não é salva em disco.")

        max_rounds = st.slider("Máximo de rounds", 1, 5, settings.max_rounds)
        run_clicked = st.button("Rodar simulação", type="primary", use_container_width=True)

    if run_clicked:
        if account_options[choice] == "upload":
            if uploaded is None:
                st.error("Envie um arquivo JSON de conta antes de rodar.")
                st.stop()
            account = AccountContext.model_validate(json.load(uploaded))
        elif account_options[choice] is None:
            account = _sample_account()
        else:
            account = AccountContext.model_validate(json.loads(account_options[choice].read_text(encoding="utf-8")))

        if not mock_mode and not api_key:
            st.error("Informe a Anthropic API Key ou marque o modo mock.")
            st.stop()

        personas = PersonaFactory.build_committee(account)
        llm = build_default_client(mock=mock_mode, api_key=api_key)
        app = build_board_graph(llm)

        with st.spinner("Rodando o debate do comitê..."):
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

        st.session_state["result"] = {
            "account": account,
            "personas": personas,
            "transcript": final_state["transcript"],
            "verdict": final_state["verdict"],
        }

    result = st.session_state.get("result")
    if not result:
        st.info("Configure a conta na barra lateral e clique em **Rodar simulação** para começar.")
        return

    account = result["account"]
    personas = result["personas"]
    transcript = result["transcript"]
    verdict = result["verdict"]

    render_hero(account)
    render_arc(verdict)

    st.markdown('<div class="ava-section-bar">Comitê simulado</div>', unsafe_allow_html=True)
    cols = st.columns(len(personas))
    for col, p in zip(cols, personas):
        with col:
            source_label = "Dados reais" if p.source.value == "real" else "Arquétipo"
            st.markdown(
                f"**{ROLE_ICON.get(p.role, '🧑')} {p.name}**  \n{p.role.value} · {source_label}  \nVeto: {p.decision_power:.2f}"
            )

    st.markdown('<div class="ava-section-bar">Debate simulado</div>', unsafe_allow_html=True)
    render_pixel_office(transcript)

    st.markdown('<div class="ava-section-bar">Principais objeções</div>', unsafe_allow_html=True)
    for o in verdict.top_objections:
        st.markdown(f"- {o}")

    st.markdown('<div class="ava-section-bar">Plano de ação recomendado</div>', unsafe_allow_html=True)
    render_roadmap(verdict.recommended_talk_track)

    st.markdown('<div class="ava-section-bar">Avaliação de risco</div>', unsafe_allow_html=True)
    st.write(verdict.risk_summary)

    report_md = build_markdown_report(account, personas, transcript, verdict)
    report_html = build_html_report(account, personas, transcript, verdict)
    slug = account.account_name.lower().replace(" ", "-")
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "Baixar relatório (.md)",
            data=report_md,
            file_name=f"{slug}-report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with dl_col2:
        st.download_button(
            "Baixar relatório estilizado (.html)",
            data=report_html,
            file_name=f"{slug}-report.html",
            mime="text/html",
            use_container_width=True,
        )

    st.markdown(
        '<div class="ava-footnote">Visual: tokens de design Avanade Style Guide v1.1 · '
        "Conversa renderizada em estilo pixel-art próprio, inspirado em pixel-agents-hq/pixel-agents "
        "(reimplementado nativamente — aquele projeto é um visualizador de sessões Claude Code em "
        "VS Code/terminal, não uma biblioteca Python embutível).</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
