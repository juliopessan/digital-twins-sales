"""
Streamlit front-end for the Sales Digital Twins board simulator.

    streamlit run streamlit_app.py

Visual language: custom design tokens (palette, typography, components)
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
import streamlit.components.v1 as components

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
    office_canvas_height,
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

# Custom thermal gradient family, used as a deterministic per-role color cycle.
ROLE_COLOR_CYCLE = ["#FFD700", "#FFB414", "#FF5800", "#B43C14", "#C80000", "#890078"]

SENTIMENT_COLOR = {
    "supportive": "#00A650",
    "neutral": "#7f7f7f",
    "skeptical": "#FFB414",
    "blocking": "#C80000",
}
SENTIMENT_LABEL_EN = {
    "supportive": "Supportive",
    "neutral": "Neutral",
    "skeptical": "Skeptical",
    "blocking": "Blocking",
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
            "Agentic pipeline hosted on Azure: OCR + extraction + exception-handling agents "
            "with a human in the loop, 18-week rollout, $640K in Year 1 (license + services)."
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
                "Already rejected a similar automation vendor over unclear ROI math",
                "Reports to a CEO who publicly committed to cutting opex 15% this fiscal year",
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
        .dt-hero {
            background: linear-gradient(135deg, #FF5800 0%, #890078 100%) !important;
        }
        .dt-arc {
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


def _inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --dt-orange: #FF5800;
            --dt-dark-orange: #DC4600;
            --dt-grey-80: #333333;
            --dt-grey-60: #666666;
            --dt-grey-40: #999999;
            --dt-grey-20: #cccccc;
            --dt-grey-10: #e5e5e5;
            --dt-solar: #FFD700;
            --dt-aurora: #890078;
        }

        html, body, [class*="css"] {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            color: var(--dt-grey-80);
        }

        .dt-hero {
            background: linear-gradient(135deg, #FF5800 0%, #890078 100%);
            color: #fff;
            padding: 40px 36px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            margin-bottom: 24px;
        }
        .dt-hero::after {
            content: "";
            position: absolute;
            right: -100px; top: -100px;
            width: 360px; height: 360px;
            background: radial-gradient(circle, rgba(255,215,0,.45) 0%, rgba(255,215,0,0) 70%);
        }
        .dt-hero h1 { font-weight: 300; font-size: 34px; margin: 0 0 6px 0; }
        .dt-hero h1 b { font-weight: 700; }
        .dt-hero .kicker {
            font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase;
            opacity: .9; margin-bottom: 10px;
        }
        .dt-hero .lede { font-weight: 300; opacity: .95; max-width: 70ch; }

        .dt-arc {
            background: #fff; border-top: 4px solid var(--dt-orange);
            box-shadow: 0 4px 12px rgba(0,0,0,0.10);
            border-radius: 4px; display: flex; margin-bottom: 24px;
        }
        .dt-arc-cell { flex: 1; padding: 18px 16px; border-right: 1px solid var(--dt-grey-10); text-align: center; }
        .dt-arc-cell:last-child { border-right: none; }
        .dt-arc-big { font-weight: 700; font-size: 28px; color: var(--dt-dark-orange); }
        .dt-arc-label { font-weight: 600; font-size: 12.5px; color: var(--dt-grey-80); margin-top: 4px; }

        .dt-section-bar {
            border-left: 4px solid var(--dt-orange);
            padding-left: 12px; margin: 28px 0 12px 0;
            font-weight: 600; font-size: 19px; color: var(--dt-grey-80);
        }

        .dt-roadmap-step {
            background: #fff; border: 1px solid var(--dt-grey-10); border-radius: 8px;
            padding: 14px 16px; margin-bottom: 10px; display: flex; gap: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        }
        .dt-roadmap-num {
            flex: 0 0 30px; height: 30px; border-radius: 50%;
            background: linear-gradient(135deg, #FFD700 0%, #FF5800 100%);
            color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center;
            font-size: 13px;
        }
        .dt-roadmap-step p { margin: 0; font-size: 14px; color: var(--dt-grey-80); }

        .dt-footnote { font-size: 11.5px; color: var(--dt-grey-40); margin-top: 18px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(account: AccountContext) -> None:
    value = f"US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "—"
    st.markdown(
        f"""
        <div class="dt-hero">
            <div class="kicker">Sales Digital Twins · Board Simulator</div>
            <h1>Committee simulation — <b>{html.escape(account.account_name)}</b></h1>
            <div class="lede">{html.escape(account.pitch_summary)}</div>
            <div class="lede" style="margin-top:8px; font-weight:600;">
                Stage: {html.escape(account.deal_stage)} &nbsp;·&nbsp; Value: {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_arc(verdict) -> None:
    consensus = "Yes" if verdict.consensus_reached else "No"
    sentiment = SENTIMENT_LABEL_EN.get(verdict.overall_sentiment.value, verdict.overall_sentiment.value)
    blockers = len(verdict.blocking_stakeholders)
    st.markdown(
        f"""
        <div class="dt-arc">
            <div class="dt-arc-cell"><div class="dt-arc-big">{consensus}</div><div class="dt-arc-label">Consensus reached</div></div>
            <div class="dt-arc-cell"><div class="dt-arc-big">{sentiment}</div><div class="dt-arc-label">Overall sentiment</div></div>
            <div class="dt-arc-cell"><div class="dt-arc-big">{blockers}</div><div class="dt-arc-label">Blocking stakeholders</div></div>
            <div class="dt-arc-cell"><div class="dt-arc-big">{len(verdict.top_objections)}</div><div class="dt-arc-label">Objections raised</div></div>
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
    """Renders the transcript as a standalone HTML document inside a
    components.html iframe. st.markdown(unsafe_allow_html=True) can lose
    track mid-document (a blank line between divs ends the "raw HTML block"
    early) and st.html sanitizes/inlines the content without isolation — the
    components.html iframe avoids both problems and gets its own scroll."""
    parts = ['<div class="pixel-office">']
    last_round = 0
    for turn in transcript:
        if turn.round_number != last_round:
            last_round = turn.round_number
            parts.append(f'<div class="pixel-round-label">ROUND {last_round}</div>')
        icon = ROLE_ICON.get(turn.role, "🧑")
        color = _role_color(turn.role.value)
        sent_color = SENTIMENT_COLOR.get(turn.sentiment.value, "#666")
        sent_label = SENTIMENT_LABEL_EN.get(turn.sentiment.value, turn.sentiment.value)
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
    # Height proportional to the number of turns, with a cap — above that the iframe scrolls.
    height = min(900, 120 + 130 * max(1, len(transcript)))
    components.html(full_html, height=height, scrolling=True)


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
    """IMPORTANT: the office canvas is pure JavaScript (requestAnimationFrame,
    sprites, BFS). st.html does NOT execute <script> — it rendered an empty
    block. components.html runs in an iframe with JS enabled."""
    agent_defs = build_agent_defs(personas)
    layout, ncols, nrows = build_layout(len(personas))
    keys = [d["key"] for d in agent_defs]
    agent_states = build_agent_states(log, keys)
    office_html = build_office_html(agent_defs, layout, ncols, nrows, agent_states)
    components.html(office_html, height=office_canvas_height(nrows), scrolling=False)


def render_roadmap(items: list[str]) -> None:
    for i, item in enumerate(items, start=1):
        st.markdown(
            f"""
            <div class="dt-roadmap-step">
                <div class="dt-roadmap-num">{i}</div>
                <p>{html.escape(item)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


_ROLE_LABEL_EN = {
    StakeholderRole.CEO: "CEO",
    StakeholderRole.CTO: "CTO",
    StakeholderRole.CFO: "CFO",
    StakeholderRole.PROCUREMENT: "Procurement",
    StakeholderRole.CHAMPION: "Internal Champion",
    StakeholderRole.END_USER: "End User",
    StakeholderRole.LEGAL_COMPLIANCE: "Legal/Compliance",
    StakeholderRole.SECURITY: "Security",
}


def render_manual_account_form() -> AccountContext | None:
    """Form to build an AccountContext from scratch: company, pitch, committee
    roles, and one real stakeholder (name + known facts) grounded as the
    digital twin instead of a generic archetype. The facts field can be
    filled by hand or auto-populated via EXA web research."""
    account_name = st.text_input("Company", placeholder="E.g.: iFood")
    pitch_summary = st.text_area("Pitch summary", placeholder="What's being sold and to whom")
    proposed_solution = st.text_area("Proposed solution", placeholder="Technical/commercial details of the proposal")
    deal_stage = st.text_input("Deal stage", value="Proposal sent, awaiting committee review")
    deal_value = st.number_input("Deal value (US$)", min_value=0, value=0, step=10_000)

    committee_roles = st.multiselect(
        "Committee roles",
        options=list(StakeholderRole),
        default=[StakeholderRole.CHAMPION, StakeholderRole.CTO, StakeholderRole.CFO, StakeholderRole.PROCUREMENT],
        format_func=lambda r: _ROLE_LABEL_EN.get(r, r.value),
    )

    st.markdown("**Real stakeholder (digital twin)**")
    if not committee_roles:
        st.caption("Select at least one committee role above.")
        real_role = None
    else:
        real_role = st.selectbox(
            "Which role is the real stakeholder?",
            options=committee_roles,
            format_func=lambda r: _ROLE_LABEL_EN.get(r, r.value),
        )
    stakeholder_name = st.text_input("Stakeholder name", placeholder="E.g.: Diego Barreto")

    exa_key = st.text_input(
        "EXA API Key (optional, for automatic research)",
        value=settings.exa_api_key or "",
        type="password",
    )
    st.caption("Used only in memory for this session — never saved to disk.")
    research_clicked = st.button("🔎 Research facts with EXA", use_container_width=True)

    if research_clicked:
        if not (account_name and stakeholder_name and real_role and exa_key):
            st.error("Fill in company, stakeholder name, role, and the EXA API Key before researching.")
        else:
            with st.spinner("Researching public facts..."):
                try:
                    role_label = _ROLE_LABEL_EN.get(real_role, real_role.value)
                    facts = research_stakeholder(stakeholder_name, role_label, account_name, exa_key)
                    st.session_state["manual_facts_input"] = "\n".join(facts)
                except ResearchError as exc:
                    st.error(str(exc))
            st.rerun()

    stakeholder_facts = st.text_area(
        "Known facts about this person (one per line)",
        placeholder="E.g.: Became CEO in 2026\nStated focus on generative AI and consolidating iFood Pago",
        height=120,
        key="manual_facts_input",
    )
    st.caption(
        "With no facts filled in, this role also falls back to the generic archetype. "
        "The other committee roles are always archetypes."
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
                reason_part = f" *(reason: {existing['reason']})*" if existing.get("reason") else ""
                st.markdown(f"~~{obj}~~{reason_part} ❌")

        with col_approve:
            if existing is None:
                if st.button("👍", key=f"approve_{account_slug}_{i}", help="Approve — look for similar patterns in future simulations"):
                    add_feedback(account_slug, obj, approved=True)
                    st.rerun()
            elif existing["approved"] and st.button("↩", key=f"undo_approve_{account_slug}_{i}", help="Undo approval"):
                remove_feedback(account_slug, obj)
                st.rerun()

        with col_reject:
            if existing is None:
                if st.button("👎", key=f"reject_{account_slug}_{i}", help="Reject — don't raise this again in future simulations"):
                    st.session_state.feedback_modal[i] = {"text": obj, "step": "reason"}
                    st.rerun()
            elif not existing["approved"] and st.button("↩", key=f"undo_reject_{account_slug}_{i}", help="Undo rejection"):
                remove_feedback(account_slug, obj)
                st.rerun()

        # Rejection modal: capture optional reason
        if st.session_state.feedback_modal.get(i, {}).get("step") == "reason":
            with st.container(border=True):
                st.caption(f"Rejecting: *{obj}*")
                reason = st.text_input(
                    "Why reject? (optional)",
                    key=f"reason_{account_slug}_{i}",
                    placeholder="E.g.: We already have a WAF that mitigates this",
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Confirm rejection", key=f"confirm_{account_slug}_{i}", type="primary"):
                        add_feedback(account_slug, obj, approved=False, reason=reason or None)
                        del st.session_state.feedback_modal[i]
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"cancel_{account_slug}_{i}"):
                        del st.session_state.feedback_modal[i]
                        st.rerun()

    if not verdict.top_objections:
        st.info("No objections recorded in this simulation.")

    used = len(feedback_entries)
    if used > 0:
        st.caption(f"💾 Feedback for this account: {used}/{MAX_ENTRIES} entries · see the 🧠 Memory tab for details")


def _render_memory_dashboard(account_slug: str) -> None:
    """Memory tab: Feedback Loop dashboard."""
    st.markdown('<div class="dt-section-bar">Feedback Loop — Immune System</div>', unsafe_allow_html=True)
    st.markdown(
        "Inspired by the principle: *\u201cAgents are 30% of the work. The other 70% is the immune system.\u201d*  \n"
        "Approvals and rejections shape future simulations via direct injection into the system prompt.",
        unsafe_allow_html=False,
    )

    all_accounts = all_accounts_with_feedback()
    if not all_accounts:
        st.info(
            "No feedback recorded yet.  \n"
            "Approve (👍) or reject (👎) objections in the **📋 Verdict** tab to feed the system."
        )
        return

    # ── Current account ───────────────────────────────────────────────────────
    entries = load_feedback(account_slug)
    approved_entries = [e for e in entries if e["approved"]]
    rejected_entries = [e for e in entries if not e["approved"]]

    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Total entries", f"{len(entries)}/{MAX_ENTRIES}")
    col2.metric("✅ Approved", len(approved_entries))
    col3.metric("❌ Rejected", len(rejected_entries))

    if entries:
        st.markdown("**History (most recent first):**")
        for e in reversed(entries):
            badge = "✅" if e["approved"] else "❌"
            reason_part = f" — *{e['reason']}*" if e.get("reason") else ""
            st.markdown(f"{badge} `{e['date']}` {e['text']}{reason_part}")

        st.markdown("---")
        if st.button("🗑️ Clear feedback for this account", type="secondary", key="clear_feedback_btn"):
            clear_feedback(account_slug)
            st.success("Feedback for this account cleared.")
            st.rerun()
    else:
        st.info(f"No feedback recorded for **{account_slug}** yet.")

    # ── Other accounts summary ────────────────────────────────────────────────
    other_accounts = [a for a in all_accounts if a != account_slug]
    if other_accounts:
        st.markdown("---")
        st.markdown("**Other accounts with feedback:**")
        for acct in other_accounts:
            acct_entries = load_feedback(acct)
            n_approved = sum(1 for e in acct_entries if e["approved"])
            n_rejected = sum(1 for e in acct_entries if not e["approved"])
            st.markdown(
                f"- `{acct}` — {len(acct_entries)}/{MAX_ENTRIES} entries "
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
    _inject_theme()

    with st.sidebar:
        # Theme toggle
        col_theme_label, col_theme_toggle = st.columns([3, 1])
        with col_theme_label:
            st.header("Round configuration")
        with col_theme_toggle:
            if "theme_mode" not in st.session_state:
                st.session_state.theme_mode = "dark"
            
            theme_icon = "🌙" if st.session_state.theme_mode == "dark" else "☀️"
            if st.button(theme_icon, help="Toggle theme (light/dark)", key="theme_toggle"):
                st.session_state.theme_mode = "light" if st.session_state.theme_mode == "dark" else "dark"
                st.rerun()
        
        if st.session_state.theme_mode == "light":
            _inject_light_theme()

        # Build account options: all JSON files from accounts/ + upload option
        account_options = {}
        account_files = []
        if ACCOUNTS_DIR.exists():
            # Only list JSONs that are actually an AccountContext (JSON object) —
            # the folder also holds scenario lists (e.g. cenarios_exemplo.json),
            # which would break model_validate on selection.
            account_files = [
                f for f in sorted(ACCOUNTS_DIR.glob("*.json"))
                if f.read_text(encoding="utf-8").lstrip()[:1] == "{"
            ]
            for f in account_files:
                account_options[f.stem] = ("file", f)
        account_options["📤 Upload custom JSON"] = ("upload", None)

        # Default to first account file if available, else show upload option
        default_index = 0
        if not account_files:
            default_index = len(account_options) - 1  # Point to upload option

        choice = st.selectbox("Account", list(account_options.keys()), index=default_index)
        
        # Load account based on selection
        uploaded = None
        account = None
        account_type, account_path = account_options[choice]

        if account_type == "file":
            account = AccountContext.model_validate(json.loads(account_path.read_text(encoding="utf-8")))
            with st.expander("📋 Loaded data", expanded=False):
                st.markdown(f"**Company:** {account.account_name}")
                st.markdown(f"**Pitch:** {account.pitch_summary}")
                st.markdown(f"**Solution:** {account.proposed_solution}")
                st.markdown(f"**Value:** US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "**Value:** —")
                st.markdown(f"**Committee:** {', '.join(r.value for r in account.roles_in_committee)}")
        elif account_type == "upload":
            uploaded = st.file_uploader("AccountContext (.json)", type="json")
            if uploaded is not None:
                account = AccountContext.model_validate(json.load(uploaded))
                with st.expander("📋 Loaded data", expanded=True):
                    st.markdown(f"**Company:** {account.account_name}")
                    st.markdown(f"**Pitch:** {account.pitch_summary}")
                    st.markdown(f"**Solution:** {account.proposed_solution}")
                    st.markdown(f"**Value:** US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "**Value:** —")
                    st.markdown(f"**Committee:** {', '.join(r.value for r in account.roles_in_committee)}")

        seller_opening = st.text_area(
            "Your opening pitch (optional)",
            placeholder="Paste the pitch as you'll say it. If filled in, the personas react to your real words. Left blank, the committee debates on its own (war-gaming).",
            height=100,
        )

        # API key
        if "anthropic_api_key" not in st.session_state:
            st.session_state.anthropic_api_key = settings.anthropic_api_key or ""

        if settings.anthropic_api_key:
            st.success("✓ API Key loaded from environment variable (.env)")
            api_key = settings.anthropic_api_key
        else:
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                value=st.session_state.anthropic_api_key,
                key="api_key_input",
                on_change=lambda: st.session_state.update({"anthropic_api_key": st.session_state.api_key_input}),
            )
            st.caption("💡 Tip: Add your key to an `.env` file to load it automatically")

        max_rounds = st.slider("Maximum rounds", 1, 5, settings.max_rounds)

        # Feedback summary badge
        if account:
            _slug_preview = account.account_name.lower().replace(" ", "-")
            _fb = load_feedback(_slug_preview)
            if _fb:
                st.caption(f"🧠 Feedback for this account: {len(_fb)}/{MAX_ENTRIES} entries")

        run_clicked = st.button("Run simulation", type="primary", use_container_width=True)

    # ── Run ───────────────────────────────────────────────────────────────────
    if run_clicked:
        if account is None:
            st.error("No account loaded. Select an existing account or upload a custom file.")
            st.stop()

        if not api_key:
            st.error("Enter the Anthropic API Key in the sidebar before running.")
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

        st.markdown('<div class="dt-section-bar">Meeting room</div>', unsafe_allow_html=True)
        office_container = st.empty()
        # Layout is fixed during the run — compute it once outside the loop.
        agent_defs = build_agent_defs(personas)
        layout, ncols, nrows = build_layout(len(personas))
        keys = [d["key"] for d in agent_defs]
        canvas_height = office_canvas_height(nrows)

        def _paint_office(current_log: list[dict]) -> None:
            agent_states = build_agent_states(current_log, keys)
            office_html = build_office_html(agent_defs, layout, ncols, nrows, agent_states)
            with office_container:
                components.html(office_html, height=canvas_height, scrolling=False)

        _paint_office([])

        q: Queue = Queue()
        t = threading.Thread(target=_run_debate_with_events, args=(app, initial_state, q), daemon=True)
        t.start()

        log: list[dict] = []
        transcript = None
        verdict = None
        error_msg = None
        with st.spinner("Running the committee debate..."):
            while True:
                try:
                    ev = q.get(timeout=180)
                except Empty:
                    st.error("The debate timed out after 3 minutes.")
                    break
                if ev["event"] in ("start", "done"):
                    log.append(ev)
                    # ✨ Real-time office canvas update
                    _paint_office(log)
                elif ev["event"] == "result":
                    transcript = ev["transcript"]
                    verdict = ev["verdict"]
                elif ev["event"] == "error":
                    error_msg = ev.get("error", "unknown error")
                    log.append(ev)
                    _paint_office(log)
                elif ev["event"] == "finished":
                    break

        if error_msg:
            st.error(f"Debate failed: {error_msg}")
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
        st.info("Configure the account in the sidebar and click **Run simulation** to get started.")
        return

    account = result["account"]
    personas = result["personas"]
    transcript = result["transcript"]
    verdict = result["verdict"]
    office_log = result.get("office_log", [])
    account_slug = account.account_name.lower().replace(" ", "-")

    render_hero(account)

    tab_sim, tab_office, tab_verdict, tab_coach, tab_export, tab_memory = st.tabs(
        ["🎯 Simulation", "🎨 Office", "📋 Verdict", "👔 Coach", "📤 Export", "🧠 Memory"]
    )

    # ── Tab 🎯 Simulation ─────────────────────────────────────────────────────
    with tab_sim:
        render_arc(verdict)

        st.markdown('<div class="dt-section-bar">Simulated committee</div>', unsafe_allow_html=True)
        cols = st.columns(len(personas))
        for col, p in zip(cols, personas):
            with col:
                source_label = "Real data" if p.source.value == "real" else "Archetype"
                st.markdown(
                    f"**{ROLE_ICON.get(p.role, '🧑')} {p.name}**  \n"
                    f"{p.role.value} · {source_label}  \nVeto: {p.decision_power:.2f}"
                )

        if account.seller_opening:
            st.markdown('<div class="dt-section-bar">Your opening pitch</div>', unsafe_allow_html=True)
            st.info(account.seller_opening)

    # ── Tab 🎨 Office ─────────────────────────────────────────────────────────
    with tab_office:
        st.markdown('<div class="dt-section-bar">Meeting room</div>', unsafe_allow_html=True)
        render_office(personas, office_log)

        st.markdown('<div class="dt-section-bar">Debate transcript</div>', unsafe_allow_html=True)
        render_pixel_office(transcript)

    # ── Tab 📋 Verdict ────────────────────────────────────────────────────────
    with tab_verdict:
        st.markdown('<div class="dt-section-bar">Top objections</div>', unsafe_allow_html=True)
        _render_objections_with_feedback(verdict, account_slug)

        # Blockers & Breakthrough Strategies
        if verdict.blocking_stakeholders:
            st.markdown('<div class="dt-section-bar">Blockers & Workarounds</div>', unsafe_allow_html=True)
            st.warning(
                f"**{len(verdict.blocking_stakeholders)} blocker(s) identified:**  "
                f"{', '.join(ROLE_ICON.get(s, '🧑') for s in verdict.blocking_stakeholders)}"
            )
            st.markdown("""
            **How to work around it:**
            - Shift from "why buy?" to "what's your opportunity cost of delaying?"
            - Bring a 3-year TCO compared to the build-it-yourself alternative (internal incremental cost)
            - Quantify the risk: manual fallback, bug fixing, lost time-to-market
            - Reposition the differentiator: it's not generic "expertise," it's proprietary knowledge of specific edge cases
            """)

        # Consensus Likelihood
        consensus_pct = 100 if verdict.consensus_reached else 0
        if not verdict.consensus_reached:
            st.markdown('<div class="dt-section-bar">Building consensus</div>', unsafe_allow_html=True)
            st.metric("Consensus", f"{consensus_pct}%")
            st.markdown(f"""
            **Diagnosis:** No full consensus.  
            **Next steps:**
            1. Identify which blocker (CEO/CFO/CTO/Procurement) is the most flexible
            2. Focus on removing 1 critical objection before moving forward
            3. Use the recommended talk track below, tested against each blocker
            4. Consider a 1-to-1 conversation with the Economic Buyer (CFO) before the next committee meeting
            """)

        if verdict.meddpicc_scorecard:
            st.markdown('<div class="dt-section-bar">MEDDPICC Scorecard <span style="font-size:11px; opacity:0.7;">*</span></div>', unsafe_allow_html=True)
            st.markdown("""
            <details>
            <summary style="cursor:pointer; font-weight:600; color:#FF5800;">What is MEDDPICC?</summary>
            <p style="margin-top:8px; font-size:13px; line-height:1.6;">
            <b>MEDDPICC</b> is the most rigorous opportunity qualification framework in the Enterprise market:
            <ul style="margin:8px 0;">
            <li><b>Metrics:</b> Does the company have clear KPIs? Can the seller defend ROI numbers?</li>
            <li><b>Economic Buyer:</b> Who signs the check? Alignment with the budget owner?</li>
            <li><b>Decision Criteria:</b> What's their priority (price, speed, support)?</li>
            <li><b>Decision Process:</b> Committee? RFP? Benchmark? How long does it take?</li>
            <li><b>Pain:</b> Is the pain real, or has it been neutralized by an internal alternative (make vs. buy)?</li>
            <li><b>Identified Champion:</b> Who inside the company champions your solution?</li>
            <li><b>Compelling Reason to Act:</b> Why NOW? What's the urgency vs. building it in-house?</li>
            </ul>
            A poor score on any dimension = critical blocker.
            </p>
            </details>
            """, unsafe_allow_html=True)
            
            for dimension, assessment in verdict.meddpicc_scorecard.items():
                st.markdown(f"**{dimension}:**  \n{assessment}\n")

        st.markdown('<div class="dt-section-bar">Recommended action plan</div>', unsafe_allow_html=True)
        render_roadmap(verdict.recommended_talk_track)

        st.markdown('<div class="dt-section-bar">Risk assessment</div>', unsafe_allow_html=True)
        st.write(verdict.risk_summary)

    # ── Tab 👔 Coach ──────────────────────────────────────────────────────────
    with tab_coach:
        if verdict.seller_coaching:
            sc = verdict.seller_coaching
            st.markdown('<div class="dt-section-bar">Coach — assessment of your pitch</div>', unsafe_allow_html=True)
            st.markdown(f"**Grade:** {sc.pitch_grade}")
            if sc.what_landed:
                st.markdown("**What worked:**")
                for item in sc.what_landed:
                    st.markdown(f"- {item}")
            if sc.what_backfired:
                st.markdown("**What backfired:**")
                for item in sc.what_backfired:
                    st.markdown(f"- {item}")
            if sc.rewrite_suggestions:
                st.markdown("**Rewrite suggestions:**")
                render_roadmap(sc.rewrite_suggestions)
        else:
            st.info(
                "Fill in **Your opening pitch** in the sidebar before running "
                "to get personalized coach feedback."
            )

    # ── Tab 📤 Export ─────────────────────────────────────────────────────────
    with tab_export:
        st.markdown('<div class="dt-section-bar">Export report</div>', unsafe_allow_html=True)
        report_md = build_markdown_report(account, personas, transcript, verdict)
        report_html = build_html_report(account, personas, transcript, verdict)
        slug = account_slug
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "📄 Download report (.md)",
                data=report_md,
                file_name=f"{slug}-report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            st.download_button(
                "🌐 Download styled report (.html)",
                data=report_html,
                file_name=f"{slug}-report.html",
                mime="text/html",
                use_container_width=True,
            )

    # ── Tab 🧠 Memory ─────────────────────────────────────────────────────────
    with tab_memory:
        _render_memory_dashboard(account_slug)

    st.markdown(
        '<div class="dt-footnote">Visual: proprietary design tokens v1.1 · '
        "Conversation rendered in a custom pixel-art style, inspired by pixel-agents-hq/pixel-agents "
        "(reimplemented natively — that project is a Claude Code session viewer for "
        "VS Code/terminal, not an embeddable Python library).</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
