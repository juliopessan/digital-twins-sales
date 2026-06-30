"""
Smoke tests using MockLLMClient — validate graph wiring, state reduction,
and persona fallback logic without spending a single real token.
"""
from __future__ import annotations

from digital_twins.llm.client import MockLLMClient
from digital_twins.models import AccountContext, DataSource, StakeholderRole
from digital_twins.orchestration.graph import build_board_graph
from digital_twins.personas.resolver import PersonaFactory


def _make_account(with_real_cfo: bool = True) -> AccountContext:
    return AccountContext(
        account_name="Test Co",
        deal_stage="Discovery",
        pitch_summary="A multi-agent pipeline for X.",
        proposed_solution="Agentic system Y.",
        roles_in_committee=[StakeholderRole.CHAMPION, StakeholderRole.CFO, StakeholderRole.CTO],
        real_data={StakeholderRole.CFO: ["Mentioned budget freeze in last earnings call"]}
        if with_real_cfo
        else {},
    )


def test_persona_factory_falls_back_to_archetype_when_no_real_data():
    account = _make_account(with_real_cfo=False)
    committee = PersonaFactory.build_committee(account)
    assert all(p.source == DataSource.ARCHETYPE for p in committee)
    assert all(p.system_prompt for p in committee)


def test_persona_factory_uses_real_data_when_present():
    account = _make_account(with_real_cfo=True)
    committee = PersonaFactory.build_committee(account)
    cfo = next(p for p in committee if p.role == StakeholderRole.CFO)
    other = next(p for p in committee if p.role == StakeholderRole.CHAMPION)

    assert cfo.source == DataSource.REAL
    assert "budget freeze" in cfo.system_prompt
    assert other.source == DataSource.ARCHETYPE


def test_full_graph_runs_end_to_end_with_mock_client():
    account = _make_account()
    personas = PersonaFactory.build_committee(account)
    llm = MockLLMClient()
    app = build_board_graph(llm)

    initial_state = {
        "account": account,
        "personas": personas,
        "round_number": 0,
        "max_rounds": 2,
        "transcript": [],
        "current_index": 0,
        "speaking_order": [],
        "facilitator_decision": "continue",
    }

    final_state = app.invoke(initial_state)

    # Every persona should have spoken at least once.
    spoken_roles = {t.role for t in final_state["transcript"]}
    expected_roles = {p.role for p in personas}
    assert spoken_roles == expected_roles

    # Synthesis must have produced a valid verdict.
    assert final_state["verdict"] is not None
    assert final_state["verdict"].top_objections

    # Hard stop respected: never exceeds max_rounds.
    assert max(t.round_number for t in final_state["transcript"]) <= 2
