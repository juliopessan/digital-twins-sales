"""Tests for the office engine (agent state and iframe sizing)."""
from __future__ import annotations

from digital_twins.models import AccountContext, StakeholderRole
from digital_twins.office import (
    build_agent_defs,
    build_agent_states,
    build_layout,
    build_office_html,
    office_canvas_height,
)
from digital_twins.personas.resolver import PersonaFactory


def _personas():
    account = AccountContext(
        account_name="Account",
        deal_stage="Proposal",
        pitch_summary="p",
        proposed_solution="s",
        roles_in_committee=[StakeholderRole.CHAMPION, StakeholderRole.CFO],
    )
    return PersonaFactory.build_committee(account)


def test_build_agent_states_lifecycle():
    keys = ["facilitator", "cfo"]
    log = [
        {"event": "start", "agent": "facilitator"},
        {"event": "done", "agent": "facilitator"},
        {"event": "start", "agent": "cfo"},
    ]
    states = build_agent_states(log, keys)
    assert states["facilitator"]["status"] == "done"
    assert states["cfo"]["status"] == "running"


def test_build_agent_states_global_error_marks_running_agents():
    """A global error (agent outside of keys, e.g. 'squad') takes down whoever
    was running — without this, the character keeps typing forever after an
    exception in the debate."""
    keys = ["facilitator", "cfo"]
    log = [
        {"event": "start", "agent": "facilitator"},
        {"event": "done", "agent": "facilitator"},
        {"event": "start", "agent": "cfo"},
        {"event": "error", "agent": "squad", "error": "boom"},
    ]
    states = build_agent_states(log, keys)
    assert states["cfo"]["status"] == "error"
    # Whoever already finished isn't retroactively marked as an error.
    assert states["facilitator"]["status"] == "done"


def test_office_canvas_height_grows_with_rows():
    assert office_canvas_height(3) > office_canvas_height(2) > 0


def test_build_office_html_embeds_state_and_is_full_document():
    personas = _personas()
    defs = build_agent_defs(personas)
    layout, ncols, nrows = build_layout(len(personas))
    states = build_agent_states([], [d["key"] for d in defs])
    html = build_office_html(defs, layout, ncols, nrows, states)
    # Full document with JS — must run inside components.html (iframe),
    # never st.html (which doesn't execute <script>).
    assert html.startswith("<!DOCTYPE html>")
    assert "<script>" in html
    assert "requestAnimationFrame" in html
    for d in defs:
        assert d["key"] in html
