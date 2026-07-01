"""
Streamlit front-end for the Sales Digital Twins board simulator.

    streamlit run streamlit_app.py

Visual language: Avanade design tokens (palette, typography, components)
applied to the report layout. The live debate is rendered as a pixel-art
"office" canvas — same workflow logic as the Squad Office tab in
juliopessan/arch-review-assistant: a background thread runs the LangGraph
debate via .stream() and pushes start/done events per node into a queue;
the main thread polls the queue inside a spinner and reruns once finished
so the canvas bakes in the accurate final per-persona states. The canvas
engine itself (sprites, desks, bubbles, state machine) is a generalized
port of that project's web/squad_office.py — see digital_twins/office.py.
"""
from __future__ import annotations

import html
import json
import threading
from pathlib import Path
from queue import Empty, Queue

import streamlit as st

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
        deal_stage="Proposta enviada, aguardando revisão do comitê",
        pitch_summary=(
            "Plataforma multiagente de Gen AI para automatizar o processamento de documentos de frete, "
            "substituindo uma equipe de revisão manual de 14 pessoas por uma equipe de supervisão de 3."
        ),
        proposed_solution=(
            "Pipeline agêntico hospedado na Azure: agentes de OCR + extração + tratamento de exceções "
            "com humano no loop, implementação de 18 semanas, $640 mil no Ano 1 (licença + serviços)."
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
                "Publicou no LinkedIn no trimestre passado sobre 'fazer mais com menos' após um congelamento de contratações",
                "Já rejeitou um fornecedor de automação parecido por matemática de ROI pouco clara",
                "Reporta a um CEO que assumiu publicamente o compromisso de reduzir o opex em 15% neste ano fiscal",
            ]
        },
    )


def _inject_light_theme() -> None:
    """Light theme override with light background and dark text."""
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background-color: #ffffff !important;
            color: #1a1a1a !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f5f5f5 !important;
        }
        .ava-hero {
            background: linear-gradient(135deg, #FF5800 0%, #890078 100%) !important;
        }
        .ava-arc {
            background: #ffffff !important;
            border-top: 4px solid #FF5800;
        }
        [data-testid="stMarkdownContainer"], [data-testid="stText"] {
            color: #1a1a1a !important;
        }
        input, select, textarea {
            background-color: #ffffff !important;
            color: #1a1a1a !important;
            border: 1px solid #cccccc !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _inject_avanade_theme() -> None:
    st.markdown(
        """
        <style>
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
            <h1>Simulação de comitê — <b>{html.escape(account.account_name)}</b></h1>
            <div class="lede">{html.escape(account.pitch_summary)}</div>
            <div class="lede" style="margin-top:8px; font-weight:600;">
                Estágio: {html.escape(account.deal_stage)} &nbsp;·&nbsp; Valor: {value}
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


_PIXEL_TRANSCRIPT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
body { margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
.pixel-office {
    background: #333333;
    background-image:
        linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
    background-size: 24px 24px;
    border-radius: 8px; padding: 24px; box-sizing: border-box;
}
.pixel-round-label {
    font-family: 'Press Start 2P', monospace; font-size: 11px; color: #FFD700;
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
.pixel-text { font-size: 14px; color: #333333; line-height: 1.5; }
"""


def render_pixel_office(transcript) -> None:
    """Renders the transcript as a standalone HTML document via st.html
    instead of st.markdown(unsafe_allow_html=True). A single large block of
    concatenated <div>s passed through Streamlit's CommonMark markdown parser
    can lose track mid-document (a blank line between divs ends the "raw
    HTML block" early), causing later turns to render as literal text/code
    instead of HTML. An iframe sidesteps markdown parsing entirely."""
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
                    <span class="pixel-name" style="background:{sent_color};">{html.escape(turn.name)} · {sent_label}</span>
                    <div class="pixel-text">{html.escape(turn.statement)}</div>
                </div>
            </div>"""
        )
    parts.append("</div>")
    inner_html = "".join(parts)
    full_html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_PIXEL_TRANSCRIPT_CSS}</style></head><body>{inner_html}</body></html>'
    st.html(full_html)


def _run_debate_with_events(app, initial_state: dict, q: Queue) -> None:
    """Runs the LangGraph debate via .stream(), pushing start/done events into
    `q` per node so the office canvas can show accurate per-persona states on
    the rerun after completion. Same thread+queue pattern as arch-review-assistant's
    EventSquad — lookahead is used to emit a "start" event for whoever speaks next
    *before* blocking on the LLM call for their turn."""
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


def render_office(personas, log: list[dict]) -> None:
    agent_defs = build_agent_defs(personas)
    layout, ncols, nrows = build_layout(len(personas))
    keys = [d["key"] for d in agent_defs]
    agent_states = build_agent_states(log, keys)
    office_html = build_office_html(agent_defs, layout, ncols, nrows, agent_states)
    st.html(office_html)


def render_roadmap(items: list[str]) -> None:
    for i, item in enumerate(items, start=1):
        st.markdown(
            f"""
            <div class="ava-roadmap-step">
                <div class="ava-roadmap-num">{i}</div>
                <p>{html.escape(item)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


_ROLE_LABEL_PT = {
    StakeholderRole.CEO: "CEO",
    StakeholderRole.CTO: "CTO",
    StakeholderRole.CFO: "CFO",
    StakeholderRole.PROCUREMENT: "Procurement",
    StakeholderRole.CHAMPION: "Champion interno",
    StakeholderRole.END_USER: "Usuário final",
    StakeholderRole.LEGAL_COMPLIANCE: "Jurídico/Compliance",
    StakeholderRole.SECURITY: "Segurança",
}


def render_manual_account_form() -> AccountContext | None:
    """Form to build an AccountContext from scratch: company, pitch, committee
    roles, and one real stakeholder (name + known facts) grounded as the
    digital twin instead of a generic archetype. The facts field can be
    filled by hand or auto-populated via EXA web research."""
    account_name = st.text_input("Empresa", placeholder="Ex: iFood")
    pitch_summary = st.text_area("Resumo do pitch", placeholder="O que está sendo vendido e para quem")
    proposed_solution = st.text_area("Solução proposta", placeholder="Detalhes técnicos/comerciais da proposta")
    deal_stage = st.text_input("Estágio do deal", value="Proposal sent, awaiting committee review")
    deal_value = st.number_input("Valor do deal (US$)", min_value=0, value=0, step=10_000)

    committee_roles = st.multiselect(
        "Papéis no comitê",
        options=list(StakeholderRole),
        default=[StakeholderRole.CHAMPION, StakeholderRole.CTO, StakeholderRole.CFO, StakeholderRole.PROCUREMENT],
        format_func=lambda r: _ROLE_LABEL_PT.get(r, r.value),
    )

    st.markdown("**Stakeholder real (digital twin)**")
    if not committee_roles:
        st.caption("Selecione ao menos um papel no comitê acima.")
        real_role = None
    else:
        real_role = st.selectbox(
            "Qual papel é o stakeholder real?",
            options=committee_roles,
            format_func=lambda r: _ROLE_LABEL_PT.get(r, r.value),
        )
    stakeholder_name = st.text_input("Nome do stakeholder", placeholder="Ex: Diego Barreto")

    exa_key = st.text_input(
        "EXA API Key (opcional, para pesquisa automática)",
        value=settings.exa_api_key or "",
        type="password",
    )
    st.caption("Usada só em memória nesta sessão — não é salva em disco.")
    research_clicked = st.button("🔎 Pesquisar fatos com EXA", use_container_width=True)

    if research_clicked:
        if not (account_name and stakeholder_name and real_role and exa_key):
            st.error("Preencha empresa, nome do stakeholder, papel e a EXA API Key antes de pesquisar.")
        else:
            with st.spinner("Pesquisando fatos públicos..."):
                try:
                    role_label = _ROLE_LABEL_PT.get(real_role, real_role.value)
                    facts = research_stakeholder(stakeholder_name, role_label, account_name, exa_key)
                    st.session_state["manual_facts_input"] = "\n".join(facts)
                except ResearchError as exc:
                    st.error(str(exc))
            st.rerun()

    stakeholder_facts = st.text_area(
        "Fatos conhecidos sobre essa pessoa (um por linha)",
        placeholder="Ex: Assumiu como CEO em 2026\nFoco declarado em IA generativa e consolidação do iFood Pago",
        height=120,
        key="manual_facts_input",
    )
    st.caption(
        "Sem fatos preenchidos, esse papel também cai para o arquétipo genérico. "
        "Os demais papéis do comitê são sempre arquétipos."
    )

    if not account_name or not pitch_summary or not proposed_solution or not committee_roles:
        return None

    real_data = {}
    real_names = {}
    facts = [line.strip() for line in stakeholder_facts.splitlines() if line.strip()]
    if real_role and facts:
        real_data[real_role] = facts
        if stakeholder_name:
            real_names[real_role] = stakeholder_name

    return AccountContext(
        account_name=account_name,
        deal_stage=deal_stage,
        pitch_summary=pitch_summary,
        proposed_solution=proposed_solution,
        deal_value_usd=deal_value or None,
        roles_in_committee=committee_roles,
        real_data=real_data,
        real_names=real_names,
    )


# ── Feedback UI helpers ────────────────────────────────────────────────────────


def _render_objections_with_feedback(verdict, account_slug: str) -> None:
    """Renders top_objections with 👍/👎 feedback buttons (Feedback Loop)."""
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
                if st.button("👍", key=f"approve_{account_slug}_{i}", help="Aprovar — buscar padrões similares em futuras simulações"):
                    add_feedback(account_slug, obj, approved=True)
                    st.rerun()
            elif existing["approved"] and st.button("↩", key=f"undo_approve_{account_slug}_{i}", help="Desfazer aprovação"):
                remove_feedback(account_slug, obj)
                st.rerun()

        with col_reject:
            if existing is None:
                if st.button("👎", key=f"reject_{account_slug}_{i}", help="Rejeitar — não levantar novamente em futuras simulações"):
                    st.session_state.feedback_modal[i] = {"text": obj, "step": "reason"}
                    st.rerun()
            elif not existing["approved"] and st.button("↩", key=f"undo_reject_{account_slug}_{i}", help="Desfazer rejeição"):
                remove_feedback(account_slug, obj)
                st.rerun()

        # Rejection modal: capture optional reason
        if st.session_state.feedback_modal.get(i, {}).get("step") == "reason":
            with st.container(border=True):
                st.caption(f"Rejeitando: *{obj}*")
                reason = st.text_input(
                    "Por que rejeitar? (opcional)",
                    key=f"reason_{account_slug}_{i}",
                    placeholder="Ex: Já temos WAF que mitiga isso",
                )
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
        st.caption(f"💾 Feedback desta conta: {used}/{MAX_ENTRIES} entradas · veja a aba 🧠 Memory para detalhes")


def _render_memory_dashboard(account_slug: str) -> None:
    """Memory tab: Feedback Loop dashboard."""
    st.markdown('<div class="ava-section-bar">Feedback Loop — Sistema Imune</div>', unsafe_allow_html=True)
    st.markdown(
        "Inspirado no princípio: *\u201cAgents are 30% of the work. The other 70% is the immune system.\u201d*  \n"
        "Aprovações e rejeições condicionam simulações futuras via injeção direta no prompt de sistema.",
        unsafe_allow_html=False,
    )

    all_accounts = all_accounts_with_feedback()
    if not all_accounts:
        st.info(
            "Nenhum feedback registrado ainda.  \n"
            "Aprove (👍) ou rejeite (👎) objeções na aba **📋 Veredito** para alimentar o sistema."
        )
        return

    # ── Current account ───────────────────────────────────────────────────────
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

    # ── Other accounts summary ────────────────────────────────────────────────
    other_accounts = [a for a in all_accounts if a != account_slug]
    if other_accounts:
        st.markdown("---")
        st.markdown("**Outras contas com feedback:**")
        for acct in other_accounts:
            acct_entries = load_feedback(acct)
            n_approved = sum(1 for e in acct_entries if e["approved"])
            n_rejected = sum(1 for e in acct_entries if not e["approved"])
            st.markdown(
                f"- `{acct}` — {len(acct_entries)}/{MAX_ENTRIES} entradas "
                f"(✅ {n_approved} · ❌ {n_rejected})"
            )


def main() -> None:
    # Load favicon
    favicon_path = Path(__file__).parent / "favicon.ico"
    with open(favicon_path, "rb") as f:
        favicon = f.read()
    
    st.set_page_config(
        page_title="Sales Digital Twins — Board Simulator",
        layout="wide",
        page_icon=favicon
    )
    _inject_avanade_theme()

    with st.sidebar:
        # Theme toggle
        col_theme_label, col_theme_toggle = st.columns([3, 1])
        with col_theme_label:
            st.header("Configuração da rodada")
        with col_theme_toggle:
            if "theme_mode" not in st.session_state:
                st.session_state.theme_mode = "dark"
            
            theme_icon = "🌙" if st.session_state.theme_mode == "dark" else "☀️"
            if st.button(theme_icon, help="Alternar tema (light/dark)", key="theme_toggle"):
                st.session_state.theme_mode = "light" if st.session_state.theme_mode == "dark" else "dark"
                st.rerun()
        
        if st.session_state.theme_mode == "light":
            _inject_light_theme()

        # Build account options: all JSON files from accounts/ + upload option
        account_options = {}
        account_files = []
        if ACCOUNTS_DIR.exists():
            account_files = sorted(ACCOUNTS_DIR.glob("*.json"))
            for f in account_files:
                account_options[f.stem] = ("file", f)
        account_options["📤 Carregar JSON customizado"] = ("upload", None)

        # Default to first account file if available, else show upload option
        default_index = 0
        if not account_files:
            default_index = len(account_options) - 1  # Point to upload option

        choice = st.selectbox("Conta", list(account_options.keys()), index=default_index)
        
        # Load account based on selection
        uploaded = None
        account = None
        account_type, account_path = account_options[choice]

        if account_type == "file":
            account = AccountContext.model_validate(json.loads(account_path.read_text(encoding="utf-8")))
            with st.expander("📋 Dados carregados", expanded=False):
                st.markdown(f"**Empresa:** {account.account_name}")
                st.markdown(f"**Pitch:** {account.pitch_summary}")
                st.markdown(f"**Solução:** {account.proposed_solution}")
                st.markdown(f"**Valor:** ${account.deal_value_usd:,}")
                st.markdown(f"**Comitê:** {', '.join(r.value for r in account.roles_in_committee)}")
        elif account_type == "upload":
            uploaded = st.file_uploader("AccountContext (.json)", type="json")
            if uploaded is not None:
                account = AccountContext.model_validate(json.load(uploaded))
                with st.expander("📋 Dados carregados", expanded=True):
                    st.markdown(f"**Empresa:** {account.account_name}")
                    st.markdown(f"**Pitch:** {account.pitch_summary}")
                    st.markdown(f"**Solução:** {account.proposed_solution}")
                    st.markdown(f"**Valor:** ${account.deal_value_usd:,}")
                    st.markdown(f"**Comitê:** {', '.join(r.value for r in account.roles_in_committee)}")

        seller_opening = st.text_area(
            "Sua fala de abertura (opcional)",
            placeholder="Cole o pitch como você vai dizer. Se preenchido, as personas reagem às suas palavras reais. Em branco, o comitê debate sozinho (war-gaming).",
            height=100,
        )

        # API key
        if "anthropic_api_key" not in st.session_state:
            st.session_state.anthropic_api_key = settings.anthropic_api_key or ""

        if settings.anthropic_api_key:
            st.success("✓ API Key carregada de variável de ambiente (.env)")
            api_key = settings.anthropic_api_key
        else:
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                value=st.session_state.anthropic_api_key,
                key="api_key_input",
                on_change=lambda: st.session_state.update({"anthropic_api_key": st.session_state.api_key_input}),
            )
            st.caption("💡 Dica: Adicione sua chave em um arquivo `.env` para carregar automaticamente")

        max_rounds = st.slider("Máximo de rounds", 1, 5, settings.max_rounds)

        # Feedback summary badge
        if account:
            _slug_preview = account.account_name.lower().replace(" ", "-")
            _fb = load_feedback(_slug_preview)
            if _fb:
                st.caption(f"🧠 Feedback desta conta: {len(_fb)}/{MAX_ENTRIES} entradas")

        run_clicked = st.button("Rodar simulação", type="primary", use_container_width=True)

    # ── Run ───────────────────────────────────────────────────────────────────
    if run_clicked:
        if account is None:
            st.error("Nenhuma conta foi carregada. Selecione uma conta existente ou envie um arquivo customizado.")
            st.stop()

        if not api_key:
            st.error("Informe a Anthropic API Key na barra lateral antes de rodar.")
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

        st.markdown('<div class="ava-section-bar">Sala de reunião</div>', unsafe_allow_html=True)
        office_container = st.empty()
        # Initial render com log vazio
        agent_defs = build_agent_defs(personas)
        layout, ncols, nrows = build_layout(len(personas))
        keys = [d["key"] for d in agent_defs]
        agent_states = build_agent_states([], keys)
        office_html = build_office_html(agent_defs, layout, ncols, nrows, agent_states)
        office_container.html(office_html)

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
                    st.error("O debate expirou após 3 minutos.")
                    break
                if ev["event"] in ("start", "done"):
                    log.append(ev)
                    # ✨ Real-time office canvas update
                    agent_defs = build_agent_defs(personas)
                    layout, ncols, nrows = build_layout(len(personas))
                    keys = [d["key"] for d in agent_defs]
                    agent_states = build_agent_states(log, keys)
                    office_html = build_office_html(agent_defs, layout, ncols, nrows, agent_states)
                    office_container.html(office_html)
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

    # ── Results (tabs) ────────────────────────────────────────────────────────
    result = st.session_state.get("result")
    if not result:
        st.info("Configure a conta na barra lateral e clique em **Rodar simulação** para começar.")
        return

    account = result["account"]
    personas = result["personas"]
    transcript = result["transcript"]
    verdict = result["verdict"]
    office_log = result.get("office_log", [])
    account_slug = account.account_name.lower().replace(" ", "-")

    render_hero(account)

    tab_sim, tab_office, tab_verdict, tab_coach, tab_export, tab_memory = st.tabs(
        ["🎯 Simulação", "🎨 Office", "📋 Veredito", "👔 Coach", "📤 Export", "🧠 Memory"]
    )

    # ── Tab 🎯 Simulação ──────────────────────────────────────────────────────
    with tab_sim:
        render_arc(verdict)

        st.markdown('<div class="ava-section-bar">Comitê simulado</div>', unsafe_allow_html=True)
        cols = st.columns(len(personas))
        for col, p in zip(cols, personas):
            with col:
                source_label = "Dados reais" if p.source.value == "real" else "Arquétipo"
                st.markdown(
                    f"**{ROLE_ICON.get(p.role, '🧑')} {p.name}**  \n"
                    f"{p.role.value} · {source_label}  \nVeto: {p.decision_power:.2f}"
                )

        if account.seller_opening:
            st.markdown('<div class="ava-section-bar">Sua fala de abertura</div>', unsafe_allow_html=True)
            st.info(account.seller_opening)

    # ── Tab 🎨 Office ─────────────────────────────────────────────────────────
    with tab_office:
        st.markdown('<div class="ava-section-bar">Sala de reunião</div>', unsafe_allow_html=True)
        render_office(personas, office_log)

        st.markdown('<div class="ava-section-bar">Transcrição do debate</div>', unsafe_allow_html=True)
        render_pixel_office(transcript)

    # ── Tab 📋 Veredito ───────────────────────────────────────────────────────
    with tab_verdict:
        st.markdown('<div class="ava-section-bar">Principais objeções</div>', unsafe_allow_html=True)
        _render_objections_with_feedback(verdict, account_slug)

        # Blockers & Breakthrough Strategies
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

        # Consensus Likelihood
        consensus_pct = 100 if verdict.consensus_reached else 0
        if not verdict.consensus_reached:
            st.markdown('<div class="ava-section-bar">Busca de consenso</div>', unsafe_allow_html=True)
            st.metric("Consenso", f"{consensus_pct}%")
            st.markdown(f"""
            **Diagnóstico:** Sem consensus total.  
            **Próximos passos:**
            1. Identifique qual bloqueador (CEO/CFO/CTO/Procurement) é o mais flexível
            2. Foque em remover 1 objeção crítica antes de avançar
            3. Use a talk track recomendada abaixo, testada contra cada bloqueador
            4. Considere uma conversa 1-to-1 com o Economic Buyer (CFO) antes da próxima reunião de comitê
            """)

        if verdict.meddpicc_scorecard:
            st.markdown('<div class="ava-section-bar">Scorecard MEDDPICC <span style="font-size:11px; opacity:0.7;">*</span></div>', unsafe_allow_html=True)
            st.markdown("""
            <details>
            <summary style="cursor:pointer; font-weight:600; color:#FF5800;">O que é MEDDPICC?</summary>
            <p style="margin-top:8px; font-size:13px; line-height:1.6;">
            <b>MEDDPICC</b> é o framework de qualificação de oportunidade mais rigoroso do mercado Enterprise:
            <ul style="margin:8px 0;">
            <li><b>Metrics:</b> A empresa tem KPIs claros? Vendedor pode defender números de ROI?</li>
            <li><b>Economic Buyer:</b> Quem assina o cheque? Consenso com budget owner?</li>
            <li><b>Decision Criteria:</b> Qual é a prioridade deles (preço, velocidade, suporte)?</li>
            <li><b>Decision Process:</b> Comitê? RFP? Benchmark? Quanto tempo leva?</li>
            <li><b>Pain:</b> Dor está real ou foi neutralizada por alternativa interna (make vs. buy)?</li>
            <li><b>Identified Champion:</b> Quem dentro deles defende sua solução?</li>
            <li><b>Compelling Reason to Act:</b> Por que NOW? Qual é a urgência vs. fazer internamente?</li>
            </ul>
            Score ruim em qualquer dimensão = bloqueador crítico.
            </p>
            </details>
            """, unsafe_allow_html=True)
            
            for dimension, assessment in verdict.meddpicc_scorecard.items():
                st.markdown(f"**{dimension}:**  \n{assessment}\n")

        st.markdown('<div class="ava-section-bar">Plano de ação recomendado</div>', unsafe_allow_html=True)
        render_roadmap(verdict.recommended_talk_track)

        st.markdown('<div class="ava-section-bar">Avaliação de risco</div>', unsafe_allow_html=True)
        st.write(verdict.risk_summary)

    # ── Tab 👔 Coach ──────────────────────────────────────────────────────────
    with tab_coach:
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
            st.info(
                "Preencha **Sua fala de abertura** na barra lateral antes de rodar "
                "para receber feedback de coach personalizado."
            )

    # ── Tab 📤 Export ─────────────────────────────────────────────────────────
    with tab_export:
        st.markdown('<div class="ava-section-bar">Exportar relatório</div>', unsafe_allow_html=True)
        report_md = build_markdown_report(account, personas, transcript, verdict)
        report_html = build_html_report(account, personas, transcript, verdict)
        slug = account_slug
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "📄 Baixar relatório (.md)",
                data=report_md,
                file_name=f"{slug}-report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            st.download_button(
                "🌐 Baixar relatório estilizado (.html)",
                data=report_html,
                file_name=f"{slug}-report.html",
                mime="text/html",
                use_container_width=True,
            )

    # ── Tab 🧠 Memory ─────────────────────────────────────────────────────────
    with tab_memory:
        _render_memory_dashboard(account_slug)

    st.markdown(
        '<div class="ava-footnote">Visual: tokens de design Avanade Style Guide v1.1 · '
        "Conversa renderizada em estilo pixel-art próprio, inspirado em pixel-agents-hq/pixel-agents "
        "(reimplementado nativamente — aquele projeto é um visualizador de sessões Claude Code em "
        "VS Code/terminal, não uma biblioteca Python embutível).</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
