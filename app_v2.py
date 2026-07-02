"""
Digital Twins Sales Simulator — UI v2 with Navigation Bar.
Applies Microsoft Streamlit App 2 pattern with Avanade theme.
Full functionality ported from streamlit_app.py — tabs replaced by st_navbar.
"""
from __future__ import annotations

import html as html_module
import json
import threading
from pathlib import Path
from queue import Empty, Queue

import streamlit as st
from streamlit_navigation_bar import st_navbar

from digital_twins.config import settings
from digital_twins.feedback import (
    MAX_ENTRIES,
    add_feedback,
    all_accounts_with_feedback,
    build_feedback_prompt_block,
    clear_feedback,
    load_feedback,
    remove_feedback,
)
from digital_twins.llm.client import build_default_client
from digital_twins.models import AccountContext, StakeholderRole
from digital_twins.office import (
    FACILITATOR_KEY,
    SYNTHESIZER_KEY,
    build_agent_defs,
    build_agent_states,
    build_layout,
    build_office_html,
)
from digital_twins.orchestration.graph import build_board_graph
from digital_twins.personas.resolver import PersonaFactory
from digital_twins.reporting import build_html_report, build_markdown_report
from digital_twins.research import ResearchError, research_stakeholder

ACCOUNTS_DIR = Path(__file__).parent / "accounts"

ROLE_ICON = {
    StakeholderRole.SALESMAN: "🎤",
    StakeholderRole.CEO: "👑",
    StakeholderRole.CTO: "💻",
    StakeholderRole.CFO: "💰",
    StakeholderRole.PROCUREMENT: "📋",
    StakeholderRole.CHAMPION: "🚀",
    StakeholderRole.END_USER: "🧑‍💼",
    StakeholderRole.LEGAL_COMPLIANCE: "⚖️",
    StakeholderRole.SECURITY: "🔒",
}

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

_ROLE_LABEL_PT = {
    StakeholderRole.SALESMAN: "Vendedor",
    StakeholderRole.CEO: "CEO",
    StakeholderRole.CTO: "CTO",
    StakeholderRole.CFO: "CFO",
    StakeholderRole.PROCUREMENT: "Procurement",
    StakeholderRole.CHAMPION: "Champion interno",
    StakeholderRole.END_USER: "Usuário final",
    StakeholderRole.LEGAL_COMPLIANCE: "Jurídico/Compliance",
    StakeholderRole.SECURITY: "Segurança",
}


def _role_color(role_value: str) -> str:
    idx = sum(ord(c) for c in role_value) % len(ROLE_COLOR_CYCLE)
    return ROLE_COLOR_CYCLE[idx]


# ─────────────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────────────
_favicon_path = Path(__file__).parent / "favicon.ico"
_favicon_bytes = None
try:
    with open(_favicon_path, "rb") as _f:
        _favicon_bytes = _f.read()
except Exception:
    pass

st.set_page_config(
    page_title="Sales Digital Twins — Board Simulator",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon=_favicon_bytes if _favicon_bytes else "🎯",
)


def _inject_light_theme() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] { background-color: #ffffff !important; color: #1a1a1a !important; }
        [data-testid="stSidebar"] { background-color: #f5f5f5 !important; }
        .ava-hero { background: linear-gradient(135deg, #FF5800 0%, #890078 100%) !important; }
        .ava-arc { background: #ffffff !important; border-top: 4px solid #FF5800; }
        [data-testid="stMarkdownContainer"], [data-testid="stText"] { color: #1a1a1a !important; }
        input, select, textarea { background-color: #ffffff !important; color: #1a1a1a !important; border: 1px solid #cccccc !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _inject_avanade_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ava-orange: #FF5800; --ava-dark-orange: #DC4600;
            --ava-grey-80: #333333; --ava-grey-60: #666666;
            --ava-grey-40: #999999; --ava-grey-20: #cccccc;
            --ava-grey-10: #e5e5e5; --ava-solar: #FFD700; --ava-aurora: #890078;
        }
        html, body, [class*="css"] { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; color: var(--ava-grey-80); }
        /* Core scroll fix for Streamlit */
        [data-testid="stAppViewContainer"], [data-testid="stApp"], .main {
            overflow: auto !important;
        }
        /* Ensure specific containers don't trap scroll */
        .st-emotion-cache-1gwvy71, .st-emotion-cache-12fmjuu {
            overflow: visible !important;
        }
        /* Remove Streamlit default header bar and decoration */
        [data-testid="stHeader"] { 
            display: none !important;
        }
        [data-testid="stDecoration"] { display: none !important; }
        /* Main content padding - offset for fixed navbar */
        .block-container { 
            padding-top: 4.5rem !important; 
            padding-bottom: 2rem !important;
            overflow: visible !important;
        }
        /* Fixed st_navbar at top=0 */
        iframe[title="streamlit_navigation_bar.st_navbar"] {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 50px !important;
            z-index: 1000000 !important;
            margin-top: 0 !important;
        }
        /* Sidebar toggle positioning - must be above navbar */
        [data-testid="stSidebarCollapsedControl"] {
            position: fixed !important;
            top: 10px !important;
            left: 10px !important;
            z-index: 1000001 !important;
            background: #FF5800 !important;
            border-radius: 4px !important;
            padding: 2px !important;
        }
        [data-testid="stSidebarCollapsedControl"] button {
            color: #FFFFFF !important;
        }
        .ava-hero {
            background: linear-gradient(135deg, #FF5800 0%, #890078 100%);
            color: #fff; padding: 40px 36px; border-radius: 8px;
            position: relative; overflow: hidden; margin-bottom: 24px;
        }
        .ava-hero::after {
            content: ""; position: absolute; right: -100px; top: -100px;
            width: 360px; height: 360px;
            background: radial-gradient(circle, rgba(255,215,0,.45) 0%, rgba(255,215,0,0) 70%);
        }
        .ava-hero h1 { font-weight: 300; font-size: 34px; margin: 0 0 6px 0; }
        .ava-hero h1 b { font-weight: 700; }
        .ava-hero .kicker { font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; opacity: .9; margin-bottom: 10px; }
        .ava-hero .lede { font-weight: 300; opacity: .95; max-width: 70ch; }
        .ava-arc {
            background: #fff; border-top: 4px solid var(--ava-orange);
            box-shadow: 0 4px 12px rgba(0,0,0,0.10); border-radius: 4px;
            display: flex; margin-bottom: 24px;
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
        .ava-footnote { font-size: 11.5px; color: var(--ava-grey-40); margin-top: 18px; }
        .stButton > button {
            background: linear-gradient(135deg, #FF5800 0%, #DC4600 100%) !important;
            color: white !important; border: none !important; font-weight: 600 !important;
        }
        .stButton > button:hover { background: linear-gradient(135deg, #DC4600 0%, #B43C14 100%) !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _get_navbar() -> str:
    pages = ["🎯 Simulação", "🎨 Office", "📋 Veredito", "👔 Coach", "📤 Export", "🧠 Memory"]
    styles = {
        "nav": {"background-color": "#FF5800", "justify-content": "left"},
        "span": {"color": "#FFFFFF", "padding": "0 16px", "font-weight": "500", "font-size": "14px"},
        "active": {
            "background-color": "rgba(255,255,255,0.2)",
            "color": "#FFFFFF",
            "font-weight": "700",
            "border-bottom": "3px solid #FFFFFF",
            "padding": "0 16px",
        },
    }
    options = {"show_menu": False, "show_sidebar": True}
    return st_navbar(pages=pages, styles=styles, options=options)


def render_hero(account: AccountContext) -> None:
    value = f"US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "—"
    st.markdown(
        f"""
        <div class="ava-hero">
            <div class="kicker">Sales Digital Twins · Board Simulator</div>
            <h1>Simulação de comitê — <b>{html_module.escape(account.account_name)}</b></h1>
            <div class="lede">{html_module.escape(account.pitch_summary)}</div>
            <div class="lede" style="margin-top:8px; font-weight:600;">
                Estágio: {html_module.escape(account.deal_stage)} &nbsp;·&nbsp; Valor: {value}
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


def render_roadmap(items: list[str]) -> None:
    for i, item in enumerate(items, start=1):
        st.markdown(
            f"""
            <div class="ava-roadmap-step">
                <div class="ava-roadmap-num">{i}</div>
                <p>{html_module.escape(item)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_office(personas, log: list[dict]) -> None:
    agent_defs = build_agent_defs(personas)
    layout, ncols, nrows = build_layout(len(personas))
    keys = [d["key"] for d in agent_defs]
    agent_states = build_agent_states(log, keys)
    office_html = build_office_html(agent_defs, layout, ncols, nrows, agent_states)
    st.html(office_html)


_PIXEL_TRANSCRIPT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
body { margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
.pixel-office {
    background: #333333;
    background-image: linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
    background-size: 24px 24px;
    border-radius: 8px; padding: 24px; box-sizing: border-box;
}
.pixel-round-label { font-family: 'Press Start 2P', monospace; font-size: 11px; color: #FFD700; margin: 18px 0 12px 0; letter-spacing: .05em; }
.pixel-turn { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 16px; }
.pixel-avatar { flex: 0 0 48px; width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; font-size: 22px; border-radius: 4px; image-rendering: pixelated; border: 3px solid rgba(0,0,0,.35); box-shadow: 0 0 0 2px rgba(255,255,255,.15) inset; }
.pixel-bubble { background: #fff; border-radius: 0 10px 10px 10px; padding: 12px 16px; max-width: 720px; position: relative; box-shadow: 0 4px 10px rgba(0,0,0,.25); }
.pixel-name { font-family: 'Press Start 2P', monospace; font-size: 10px; margin-bottom: 6px; display: inline-block; padding: 2px 8px; border-radius: 3px; color: #fff; }
.pixel-text { font-size: 14px; color: #333333; line-height: 1.5; }
"""


def render_pixel_office(transcript) -> None:
    parts = ['<div class="pixel-office">']
    last_round = 0
    for turn in transcript:
        if turn.round_number != last_round:
            last_round = turn.round_number
            parts.append(f'<div class="pixel-round-label">RODADA {last_round}</div>')
        icon = ROLE_ICON.get(turn.role, "🧑")
        color = _role_color(turn.role.value)
        sent_color = SENTIMENT_COLOR.get(turn.sentiment.value, "#666")
        sent_label = SENTIMENT_LABEL_PT.get(turn.sentiment.value, turn.sentiment.value)
        parts.append(
            f"""<div class="pixel-turn">
                <div class="pixel-avatar" style="background:{color};">{icon}</div>
                <div class="pixel-bubble">
                    <span class="pixel-name" style="background:{sent_color};">{html_module.escape(turn.name)} · {sent_label}</span>
                    <div class="pixel-text">{html_module.escape(turn.statement)}</div>
                </div>
            </div>"""
        )
    parts.append("</div>")
    inner_html = "".join(parts)
    full_html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_PIXEL_TRANSCRIPT_CSS}</style></head><body>{inner_html}</body></html>'
    st.html(full_html)


def _run_debate_with_events(app, initial_state: dict, q: Queue) -> None:
    transcript: list = []
    verdict = None
    speaking_order: list[str] = []
    next_idx = 0
    try:
        q.put({"event": "start", "agent": FACILITATOR_KEY})
        for step in app.stream(initial_state, stream_mode="updates"):
            for node_name, update in step.items():
                if node_name == "start_round":
                    q.put({"event": "done", "agent": FACILITATOR_KEY})
                    speaking_order = update.get("speaking_order", [])
                    next_idx = 0
                    if speaking_order:
                        q.put({"event": "start", "agent": speaking_order[0]})
                elif node_name == "persona_turn":
                    turn = update["transcript"][0]
                    transcript.append(turn)
                    q.put({"event": "done", "agent": turn.role.value})
                    next_idx += 1
                    if next_idx < len(speaking_order):
                        q.put({"event": "start", "agent": speaking_order[next_idx]})
                    else:
                        q.put({"event": "start", "agent": FACILITATOR_KEY})
                elif node_name == "evaluate_round":
                    q.put({"event": "done", "agent": FACILITATOR_KEY})
                    if update.get("facilitator_decision") == "conclude":
                        q.put({"event": "start", "agent": SYNTHESIZER_KEY})
                    else:
                        q.put({"event": "start", "agent": FACILITATOR_KEY})
                elif node_name == "synthesize":
                    verdict = update["verdict"]
                    q.put({"event": "done", "agent": SYNTHESIZER_KEY})
        q.put({"event": "result", "transcript": transcript, "verdict": verdict})
    except Exception as exc:
        q.put({"event": "error", "agent": "squad", "error": str(exc)})
    finally:
        q.put({"event": "finished"})


def _render_objections_with_feedback(verdict, account_slug: str) -> None:
    feedback_entries = load_feedback(account_slug)
    existing_texts = {e["text"]: e for e in feedback_entries}
    if "feedback_modal" not in st.session_state:
        st.session_state.feedback_modal = {}
    for i, obj in enumerate(verdict.top_objections):
        existing = existing_texts.get(obj)
        col_text, col_approve, col_reject = st.columns([7, 1, 1])
        with col_text:
            if existing is None:
                st.markdown(f"- {obj}")
            elif existing["approved"]:
                st.markdown(f"✅ {obj}")
            else:
                reason_part = f" *(motivo: {existing['reason']})*" if existing.get("reason") else ""
                st.markdown(f"~~{obj}~~{reason_part} ❌")
        with col_approve:
            if existing is None:
                if st.button("👍", key=f"approve_{account_slug}_{i}"):
                    add_feedback(account_slug, obj, approved=True)
                    st.rerun()
            elif existing["approved"] and st.button("↩", key=f"undo_approve_{account_slug}_{i}"):
                remove_feedback(account_slug, obj)
                st.rerun()
        with col_reject:
            if existing is None:
                if st.button("👎", key=f"reject_{account_slug}_{i}"):
                    st.session_state.feedback_modal[i] = {"text": obj, "step": "reason"}
                    st.rerun()
            elif not existing["approved"] and st.button("↩", key=f"undo_reject_{account_slug}_{i}"):
                remove_feedback(account_slug, obj)
                st.rerun()
        if st.session_state.feedback_modal.get(i, {}).get("step") == "reason":
            with st.container(border=True):
                st.caption(f"Rejeitando: *{obj}*")
                reason = st.text_input("Por que rejeitar? (opcional)", key=f"reason_{account_slug}_{i}", placeholder="Ex: Já temos WAF que mitiga isso")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Confirmar rejeição", key=f"confirm_{account_slug}_{i}", type="primary"):
                        add_feedback(account_slug, obj, approved=False, reason=reason or None)
                        del st.session_state.feedback_modal[i]
                        st.rerun()
                with c2:
                    if st.button("Cancelar", key=f"cancel_{account_slug}_{i}"):
                        del st.session_state.feedback_modal[i]
                        st.rerun()
    if not verdict.top_objections:
        st.info("Nenhuma objeção registrada nesta simulação.")
    used = len(feedback_entries)
    if used > 0:
        st.caption(f"💾 Feedback desta conta: {used}/{MAX_ENTRIES} entradas")


def _render_memory_dashboard(account_slug: str) -> None:
    st.markdown('<div class="ava-section-bar">Feedback Loop — Sistema Imune</div>', unsafe_allow_html=True)
    st.markdown(
        "Inspirado no princípio: *\"Agents are 30% of the work. The other 70% is the immune system.\"*  \n"
        "Aprovações e rejeições condicionam simulações futuras via injeção direta no prompt de sistema."
    )
    all_accounts = all_accounts_with_feedback()
    if not all_accounts:
        st.info("Nenhum feedback registrado ainda. Aprove (👍) ou rejeite (👎) objeções na aba 📋 Veredito.")
        return
    entries = load_feedback(account_slug)
    approved_entries = [e for e in entries if e["approved"]]
    rejected_entries = [e for e in entries if not e["approved"]]
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Total de entradas", f"{len(entries)}/{MAX_ENTRIES}")
    col2.metric("✅ Aprovados", len(approved_entries))
    col3.metric("❌ Rejeitados", len(rejected_entries))
    if entries:
        st.markdown("**Histórico (mais recentes primeiro):**")
        for e in reversed(entries):
            badge = "✅" if e["approved"] else "❌"
            reason_part = f" — *{e['reason']}*" if e.get("reason") else ""
            st.markdown(f"{badge} `{e['date']}` {e['text']}{reason_part}")
        st.markdown("---")
        if st.button("🗑️ Limpar feedback desta conta", type="secondary", key="clear_feedback_btn"):
            clear_feedback(account_slug)
            st.success("Feedback desta conta apagado.")
            st.rerun()
    else:
        st.info(f"Sem feedback registrado para **{account_slug}** ainda.")
    other_accounts = [a for a in all_accounts if a != account_slug]
    if other_accounts:
        st.markdown("---")
        st.markdown("**Outras contas com feedback:**")
        for acct in other_accounts:
            acct_entries = load_feedback(acct)
            n_approved = sum(1 for e in acct_entries if e["approved"])
            n_rejected = sum(1 for e in acct_entries if not e["approved"])
            st.markdown(f"- `{acct}` — {len(acct_entries)}/{MAX_ENTRIES} entradas (✅ {n_approved} · ❌ {n_rejected})")


def _page_simulacao(result: dict) -> None:
    account = result["account"]
    personas = result["personas"]
    verdict = result["verdict"]
    render_arc(verdict)
    st.markdown('<div class="ava-section-bar">Comitê simulado</div>', unsafe_allow_html=True)
    cols = st.columns(len(personas))
    for col, p in zip(cols, personas):
        with col:
            source_label = "Dados reais" if p.source.value == "real" else "Arquétipo"
            role_label = _ROLE_LABEL_PT.get(p.role, p.role.value)
            st.markdown(
                f"**{ROLE_ICON.get(p.role, '🧑')} {p.name}**  \n"
                f"{role_label} · {source_label}  \nVeto: {p.decision_power:.2f}"
            )
    if account.seller_opening:
        st.markdown('<div class="ava-section-bar">Sua fala de abertura</div>', unsafe_allow_html=True)
        st.info(account.seller_opening)


def _page_office(result: dict) -> None:
    personas = result["personas"]
    transcript = result["transcript"]
    office_log = result.get("office_log", [])
    st.markdown('<div class="ava-section-bar">Sala de reunião</div>', unsafe_allow_html=True)
    render_office(personas, office_log)
    st.markdown('<div class="ava-section-bar">Transcrição do debate</div>', unsafe_allow_html=True)
    render_pixel_office(transcript)


def _page_veredito(result: dict) -> None:
    account = result["account"]
    verdict = result["verdict"]
    account_slug = account.account_name.lower().replace(" ", "-")

    st.markdown('<div class="ava-section-bar">Principais objeções</div>', unsafe_allow_html=True)
    _render_objections_with_feedback(verdict, account_slug)

    if verdict.blocking_stakeholders:
        st.markdown('<div class="ava-section-bar">Bloqueadores & Contorno</div>', unsafe_allow_html=True)
        st.warning(
            f"**{len(verdict.blocking_stakeholders)} bloqueador(es) identificado(s):**  "
            f"{', '.join(ROLE_ICON.get(s, '🧑') for s in verdict.blocking_stakeholders)}"
        )
        st.markdown("""
        **Como contornar:**
        - Mude de "por que comprar?" para "qual é seu custo de oportunidade do delay?"
        - Traga TCO de 3 anos comparado com alternativa de make (custo incremental interno)
        - Quantifique risco: fallback manual, bug fixing, tempo de mercado perdido
        - Reposicione diferencial: não é "expertise" genérica, é conhecimento proprietário em edge cases específicos
        """)

    if not verdict.consensus_reached:
        st.markdown('<div class="ava-section-bar">Busca de consenso</div>', unsafe_allow_html=True)
        st.metric("Consenso", "0%")
        st.markdown("""
        **Diagnóstico:** Sem consensus total.
        **Próximos passos:**
        1. Identifique qual bloqueador é o mais flexível
        2. Foque em remover 1 objeção crítica antes de avançar
        3. Use a talk track recomendada abaixo
        4. Considere uma conversa 1-to-1 com o Economic Buyer (CFO) antes da próxima reunião
        """)

    if verdict.meddpicc_scorecard:
        st.markdown('<div class="ava-section-bar">Scorecard MEDDPICC ✱</div>', unsafe_allow_html=True)
        with st.expander("O que é MEDDPICC?"):
            st.markdown("""
**MEDDPICC** é o framework de qualificação de oportunidade mais rigoroso do mercado Enterprise:
- **Metrics:** A empresa tem KPIs claros? Vendedor pode defender números de ROI?
- **Economic Buyer:** Quem assina o cheque? Consenso com budget owner?
- **Decision Criteria:** Qual é a prioridade deles (preço, velocidade, suporte)?
- **Decision Process:** Comitê? RFP? Benchmark? Quanto tempo leva?
- **Pain:** Dor está real ou foi neutralizada por alternativa interna?
- **Identified Champion:** Quem dentro deles defende sua solução?
- **Compelling Reason to Act:** Por que NOW? Qual é a urgência?

Score ruim em qualquer dimensão = bloqueador crítico.
            """)
        for dimension, assessment in verdict.meddpicc_scorecard.items():
            st.markdown(f"**{dimension}:**  \n{assessment}\n")

    st.markdown('<div class="ava-section-bar">Plano de ação recomendado</div>', unsafe_allow_html=True)
    render_roadmap(verdict.recommended_talk_track)
    st.markdown('<div class="ava-section-bar">Avaliação de risco</div>', unsafe_allow_html=True)
    st.write(verdict.risk_summary)


def _page_coach(result: dict) -> None:
    verdict = result["verdict"]
    if verdict.seller_coaching:
        sc = verdict.seller_coaching
        st.markdown('<div class="ava-section-bar">Coach — avaliação do seu pitch</div>', unsafe_allow_html=True)
        st.markdown(f"**Nota:** {sc.pitch_grade}")
        if sc.what_landed:
            st.markdown("**O que funcionou:**")
            for item in sc.what_landed:
                st.markdown(f"- {item}")
        if sc.what_backfired:
            st.markdown("**O que saiu pela culatra:**")
            for item in sc.what_backfired:
                st.markdown(f"- {item}")
        if sc.rewrite_suggestions:
            st.markdown("**Sugestões de reescrita:**")
            render_roadmap(sc.rewrite_suggestions)
    else:
        st.info("Preencha **Sua fala de abertura** na barra lateral antes de rodar para receber feedback de coach personalizado.")


def _page_export(result: dict) -> None:
    account = result["account"]
    personas = result["personas"]
    transcript = result["transcript"]
    verdict = result["verdict"]
    account_slug = account.account_name.lower().replace(" ", "-")
    st.markdown('<div class="ava-section-bar">Exportar relatório</div>', unsafe_allow_html=True)
    report_md = build_markdown_report(account, personas, transcript, verdict)
    report_html = build_html_report(account, personas, transcript, verdict)
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button("📄 Baixar relatório (.md)", data=report_md, file_name=f"{account_slug}-report.md", mime="text/markdown", use_container_width=True)
    with dl_col2:
        st.download_button("🌐 Baixar relatório estilizado (.html)", data=report_html, file_name=f"{account_slug}-report.html", mime="text/html", use_container_width=True)


def _page_memory(result: dict) -> None:
    account = result["account"]
    account_slug = account.account_name.lower().replace(" ", "-")
    _render_memory_dashboard(account_slug)


def _render_sidebar() -> tuple:
    with st.sidebar:
        col_label, col_toggle = st.columns([3, 1])
        with col_label:
            st.header("Configuração")
        with col_toggle:
            if "theme_mode" not in st.session_state:
                st.session_state.theme_mode = "dark"
            icon = "🌙" if st.session_state.theme_mode == "dark" else "☀️"
            if st.button(icon, help="Alternar tema", key="theme_toggle"):
                st.session_state.theme_mode = "light" if st.session_state.theme_mode == "dark" else "dark"
                st.rerun()
        if st.session_state.get("theme_mode") == "light":
            _inject_light_theme()

        account_options = {}
        account_files = []
        if ACCOUNTS_DIR.exists():
            account_files = sorted(ACCOUNTS_DIR.glob("*.json"))
            for f in account_files:
                account_options[f.stem] = ("file", f)
        account_options["📤 Carregar JSON customizado"] = ("upload", None)
        default_index = 0 if account_files else len(account_options) - 1

        choice = st.selectbox("Conta", list(account_options.keys()), index=default_index)
        account_type, account_path = account_options[choice]
        account = None

        if account_type == "file":
            account = AccountContext.model_validate(json.loads(account_path.read_text(encoding="utf-8")))
            with st.expander("📋 Dados carregados", expanded=False):
                st.markdown(f"**Empresa:** {account.account_name}")
                st.markdown(f"**Pitch:** {account.pitch_summary[:80]}...")
                st.markdown(f"**Valor:** US$ {account.deal_value_usd:,}" if account.deal_value_usd else "**Valor:** —")
                st.markdown(f"**Comitê:** {', '.join(r.value for r in account.roles_in_committee)}")
        else:
            uploaded = st.file_uploader("AccountContext (.json)", type="json")
            if uploaded is not None:
                account = AccountContext.model_validate(json.load(uploaded))

        seller_opening = st.text_area(
            "Sua fala de abertura (opcional)",
            placeholder="Cole o pitch como você vai dizer. Em branco = war-gaming sem vendedor.",
            height=100,
        )

        if settings.anthropic_api_key:
            st.success("✓ API Key carregada de .env")
            api_key = settings.anthropic_api_key
        else:
            if "anthropic_api_key" not in st.session_state:
                st.session_state.anthropic_api_key = ""
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                value=st.session_state.anthropic_api_key,
                key="api_key_input",
                on_change=lambda: st.session_state.update({"anthropic_api_key": st.session_state.api_key_input}),
            )
            st.caption("💡 Adicione sua chave em um arquivo `.env` para carregar automaticamente")

        max_rounds = st.slider("Máximo de rounds", 1, 5, settings.max_rounds)

        if account:
            _slug = account.account_name.lower().replace(" ", "-")
            _fb = load_feedback(_slug)
            if _fb:
                st.caption(f"🧠 Feedback: {len(_fb)}/{MAX_ENTRIES} entradas")

        run_clicked = st.button("▶️ Rodar simulação", type="primary", use_container_width=True)

    return account, api_key, max_rounds, seller_opening, run_clicked


def main() -> None:
    _inject_avanade_theme()
    
    # Initialize session state for page tracking
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "🎯 Simulação"
    
    navbar_selection = _get_navbar()
    if navbar_selection and navbar_selection != st.session_state.selected_page:
        st.session_state.selected_page = navbar_selection
    
    selected_page = st.session_state.selected_page

    account, api_key, max_rounds, seller_opening, run_clicked = _render_sidebar()

    if run_clicked:
        if account is None:
            st.error("Nenhuma conta carregada. Selecione uma conta ou envie um arquivo.")
            st.stop()
        if not api_key:
            st.error("Informe a Anthropic API Key na barra lateral.")
            st.stop()

        if seller_opening.strip():
            account = account.model_copy(update={"seller_opening": seller_opening.strip()})

        account_slug = account.account_name.lower().replace(" ", "-")
        feedback_block = build_feedback_prompt_block(account_slug)
        personas = PersonaFactory.build_committee(account)
        llm = build_default_client(api_key=api_key)
        app = build_board_graph(llm, feedback_block)
        initial_state = {
            "account": account,
            "personas": personas,
            "round_number": 0,
            "max_rounds": max_rounds,
            "transcript": [],
            "current_index": 0,
            "speaking_order": [],
            "facilitator_decision": "continue",
        }

        st.markdown('<div class="ava-section-bar">Sala de reunião — ao vivo</div>', unsafe_allow_html=True)
        office_container = st.empty()
        agent_defs = build_agent_defs(personas)
        layout, ncols, nrows = build_layout(len(personas))
        keys = [d["key"] for d in agent_defs]
        agent_states = build_agent_states([], keys)
        office_container.html(build_office_html(agent_defs, layout, ncols, nrows, agent_states))

        q: Queue = Queue()
        t = threading.Thread(target=_run_debate_with_events, args=(app, initial_state, q), daemon=True)
        t.start()

        log: list[dict] = []
        transcript = None
        verdict = None
        error_msg = None
        with st.spinner("Rodando o debate do comitê..."):
            while True:
                try:
                    ev = q.get(timeout=180)
                except Empty:
                    st.error("Timeout após 3 minutos.")
                    break
                if ev["event"] in ("start", "done"):
                    log.append(ev)
                    agent_states = build_agent_states(log, keys)
                    office_container.html(build_office_html(agent_defs, layout, ncols, nrows, agent_states))
                elif ev["event"] == "result":
                    transcript = ev["transcript"]
                    verdict = ev["verdict"]
                elif ev["event"] == "error":
                    error_msg = ev.get("error", "erro desconhecido")
                elif ev["event"] == "finished":
                    break

        if error_msg:
            st.error(f"Falha no debate: {error_msg}")
            st.stop()

        st.session_state["result"] = {
            "account": account,
            "personas": personas,
            "transcript": transcript,
            "verdict": verdict,
            "office_log": log,
        }
        st.rerun()

    result = st.session_state.get("result")
    if not result:
        st.markdown(
            """
            <div class="ava-hero">
                <div class="kicker">Sales Digital Twins · Board Simulator</div>
                <h1><b>Simule seu comitê de compras</b></h1>
                <div class="lede">Selecione uma conta na barra lateral e clique em <b>▶️ Rodar simulação</b> para começar.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.info("👈 Configure a conta, API Key e clique em **Rodar simulação** na barra lateral.")
        return

    render_hero(result["account"])

    page_map = {
        "🎯 Simulação": _page_simulacao,
        "🎨 Office": _page_office,
        "📋 Veredito": _page_veredito,
        "👔 Coach": _page_coach,
        "📤 Export": _page_export,
        "🧠 Memory": _page_memory,
    }
    page_fn = page_map.get(selected_page)
    if page_fn:
        page_fn(result)
    else:
        _page_simulacao(result)

    st.markdown('<div class="ava-footnote">Visual: tokens de design Avanade · Squad-pod pixel engine · LangGraph multi-agent debate</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
