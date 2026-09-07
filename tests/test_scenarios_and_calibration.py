"""
Tests for the digital twin features:

- scenarios: branch/simulate/compare (pitch what-if)
- calibration: twin vs. reality (predicted objections vs. the real call)

Everything runs with a FakeLLMClient — no API key.
"""
from __future__ import annotations

import json

from digital_twins.calibration import CalibrationReport, _collect_predictions, calibrate
from digital_twins.llm.client import LLMClient
from digital_twins.models import (
    AccountContext,
    DebateTurn,
    DebateVerdict,
    Sentiment,
    SimulationRecord,
    StakeholderRole,
)
from digital_twins.scenarios import (
    ScenarioSpec,
    build_comparison_markdown,
    compute_risk_score,
    run_scenarios,
)


class FakeLLMClient(LLMClient):
    """Distinguishes the call type by the system prompt's content.

    - persona (free text): returns a statement + SENTIMENT tag
    - facilitator (json_mode, decision prompt): concludes right away
    - synthesizer (json_mode, synthesis prompt): fixed verdict
    - calibration (json_mode, calibration prompt): fixed matches
    """

    def complete(self, *, system, user, model, max_tokens, json_mode=False):
        if not json_mode:
            return "I need to see the ROI on this before approving anything.\nSENTIMENT: skeptical"
        if "facilitator" in system:
            return json.dumps({"decision": "conclude", "reasoning": "positions are clear"})
        if "SIMULATED buying committee" in system:
            return json.dumps(
                {
                    "matches": [
                        {
                            "role": "cfo",
                            "predicted_objection": "unclear ROI",
                            "occurred": True,
                            "evidence": "didn't see the return on that number",
                        },
                        {
                            "role": "cto",
                            "predicted_objection": "integration with legacy systems",
                            "occurred": False,
                            "evidence": "",
                        },
                    ],
                    "blind_spots": ["vendor lock-in concern"],
                    "data_enrichment_suggestions": ["CFO cited a 12-month payback target"],
                }
            )
        # synthesizer
        return json.dumps(
            {
                "consensus_reached": False,
                "overall_sentiment": "skeptical",
                "top_objections": ["unclear ROI"],
                "blocking_stakeholders": ["cfo"],
                "recommended_talk_track": ["Open with a TCO table"],
                "risk_summary": "CFO is skeptical.",
                "meddpicc_scorecard": {},
            }
        )


def _account() -> AccountContext:
    return AccountContext(
        account_name="Test Account",
        deal_stage="Proposal",
        pitch_summary="Base pitch.",
        proposed_solution="Base solution for $100k.",
        deal_value_usd=100_000,
        roles_in_committee=[StakeholderRole.CHAMPION, StakeholderRole.CFO],
    )


# --------------------------------------------------------------------------
# scenarios


def test_scenario_spec_applies_only_overrides():
    base = _account()
    spec = ScenarioSpec(name="with-poc", proposed_solution="6-week POC", deal_value_usd=90_000)
    branched = spec.apply(base)

    assert branched.proposed_solution == "6-week POC"
    assert branched.deal_value_usd == 90_000
    # Fields not overridden inherit from the base; the base is not mutated.
    assert branched.pitch_summary == base.pitch_summary
    assert base.deal_value_usd == 100_000


def test_compute_risk_score_orders_sensibly():
    good = DebateVerdict(
        consensus_reached=True,
        overall_sentiment=Sentiment.SUPPORTIVE,
        top_objections=[],
        blocking_stakeholders=[],
        recommended_talk_track=[],
        risk_summary="",
    )
    bad = DebateVerdict(
        consensus_reached=False,
        overall_sentiment=Sentiment.BLOCKING,
        top_objections=["x"],
        blocking_stakeholders=[StakeholderRole.CFO, StakeholderRole.PROCUREMENT],
        recommended_talk_track=[],
        risk_summary="",
    )
    assert compute_risk_score(good) < compute_risk_score(bad)
    assert compute_risk_score(good) == 0.0
    assert compute_risk_score(bad) == 3.0 + 2.0 + 1.0


def test_run_scenarios_end_to_end_with_fake_llm():
    base = _account()
    specs = [
        ScenarioSpec(name="full-price", description="as-is"),
        ScenarioSpec(name="with-poc", proposed_solution="paid POC", deal_value_usd=90_000),
    ]
    outcomes = run_scenarios(base, specs, FakeLLMClient(), max_rounds=1)

    assert len(outcomes) == 2
    assert {o.scenario.name for o in outcomes} == {"full-price", "with-poc"}
    # Sorted by increasing risk.
    assert outcomes[0].risk_score <= outcomes[1].risk_score
    # Each scenario ran a full debate (every persona spoke).
    for o in outcomes:
        # PersonaFactory prepends the salesman to the declared committee.
        assert {t.role for t in o.transcript} >= {StakeholderRole.CHAMPION, StakeholderRole.CFO}

    md = build_comparison_markdown(base, outcomes)
    assert "Scenario Comparison" in md
    assert "full-price" in md and "with-poc" in md
    assert "Recommended scenario" in md


# --------------------------------------------------------------------------
# calibration


def _record() -> SimulationRecord:
    return SimulationRecord(
        created_at="2026-07-09T00:00:00+00:00",
        account=_account(),
        transcript=[
            DebateTurn(
                round_number=1,
                role=StakeholderRole.CFO,
                name="CFO",
                statement="Unclear ROI on this number.",
                objections_raised=["unclear ROI"],
                sentiment=Sentiment.SKEPTICAL,
            ),
            DebateTurn(
                round_number=1,
                role=StakeholderRole.CHAMPION,
                name="Champion",
                statement="I'm on board, but we need ammunition.",
                objections_raised=[],
                sentiment=Sentiment.SUPPORTIVE,
            ),
        ],
        verdict=DebateVerdict(
            consensus_reached=False,
            overall_sentiment=Sentiment.SKEPTICAL,
            top_objections=["unclear ROI"],
            blocking_stakeholders=[StakeholderRole.CFO],
            recommended_talk_track=[],
            risk_summary="",
        ),
    )


def test_collect_predictions_uses_objections_and_skeptical_statements():
    record = _record()
    preds = _collect_predictions(record)
    assert preds["cfo"] == ["unclear ROI"]
    # Champion was supportive with no objection — doesn't become a prediction.
    assert "champion" not in preds


def test_calibrate_builds_report_from_llm_matches():
    report = calibrate(_record(), "Transcript: didn't see the return on that number...", FakeLLMClient())

    assert isinstance(report, CalibrationReport)
    roles = {p.role for p in report.personas}
    assert roles == {StakeholderRole.CFO, StakeholderRole.CTO}
    cfo = next(p for p in report.personas if p.role == StakeholderRole.CFO)
    assert cfo.fidelity == 1.0
    assert report.overall_fidelity == 0.5
    assert report.blind_spots == ["vendor lock-in concern"]
    assert report.data_enrichment_suggestions

    md = report.to_markdown()
    assert "Overall fidelity: 50%" in md
    assert "Blind spots" in md
