"""
Testes das features de digital twin:

- scenarios: branch/simulate/compare (what-if de pitch)
- calibration: twin vs realidade (objeções previstas vs call real)

Tudo roda com um FakeLLMClient — sem API key.
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
    """Distingue o tipo de chamada pelo conteúdo do system prompt.

    - persona (texto livre): devolve fala + tag SENTIMENT
    - facilitador (json_mode, prompt de decisão): conclui na hora
    - synthesizer (json_mode, prompt de síntese): veredito fixo
    - calibração (json_mode, prompt de calibração): matches fixos
    """

    def complete(self, *, system, user, model, max_tokens, json_mode=False):
        if not json_mode:
            return "Preciso ver o ROI disso antes de aprovar qualquer coisa.\nSENTIMENT: skeptical"
        if "facilitador" in system:
            return json.dumps({"decision": "conclude", "reasoning": "posições claras"})
        if "comitê de compra SIMULADO" in system:
            return json.dumps(
                {
                    "matches": [
                        {
                            "role": "cfo",
                            "predicted_objection": "ROI pouco claro",
                            "occurred": True,
                            "evidence": "não vi retorno nesse número",
                        },
                        {
                            "role": "cto",
                            "predicted_objection": "integração com legado",
                            "occurred": False,
                            "evidence": "",
                        },
                    ],
                    "blind_spots": ["preocupação com lock-in de fornecedor"],
                    "data_enrichment_suggestions": ["CFO citou meta de payback de 12 meses"],
                }
            )
        # synthesizer
        return json.dumps(
            {
                "consensus_reached": False,
                "overall_sentiment": "skeptical",
                "top_objections": ["ROI pouco claro"],
                "blocking_stakeholders": ["cfo"],
                "recommended_talk_track": ["Abrir com tabela de TCO"],
                "risk_summary": "CFO cético.",
                "meddpicc_scorecard": {},
            }
        )


def _account() -> AccountContext:
    return AccountContext(
        account_name="Conta Teste",
        deal_stage="Proposta",
        pitch_summary="Pitch base.",
        proposed_solution="Solução base por $100k.",
        deal_value_usd=100_000,
        roles_in_committee=[StakeholderRole.CHAMPION, StakeholderRole.CFO],
    )


# --------------------------------------------------------------------------
# scenarios


def test_scenario_spec_applies_only_overrides():
    base = _account()
    spec = ScenarioSpec(name="com-poc", proposed_solution="POC de 6 semanas", deal_value_usd=90_000)
    branched = spec.apply(base)

    assert branched.proposed_solution == "POC de 6 semanas"
    assert branched.deal_value_usd == 90_000
    # Campos não sobrescritos herdam do base; o base não é mutado.
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
        ScenarioSpec(name="preco-cheio", description="como está"),
        ScenarioSpec(name="com-poc", proposed_solution="POC paga", deal_value_usd=90_000),
    ]
    outcomes = run_scenarios(base, specs, FakeLLMClient(), max_rounds=1)

    assert len(outcomes) == 2
    assert {o.scenario.name for o in outcomes} == {"preco-cheio", "com-poc"}
    # Ordenado por risco crescente.
    assert outcomes[0].risk_score <= outcomes[1].risk_score
    # Cada cenário rodou um debate completo (todas as personas falaram).
    for o in outcomes:
        # A PersonaFactory prepõe o salesman ao comitê declarado.
        assert {t.role for t in o.transcript} >= {StakeholderRole.CHAMPION, StakeholderRole.CFO}

    md = build_comparison_markdown(base, outcomes)
    assert "Comparativo de cenários" in md
    assert "preco-cheio" in md and "com-poc" in md
    assert "Cenário recomendado" in md


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
                statement="ROI pouco claro nesse número.",
                objections_raised=["ROI pouco claro"],
                sentiment=Sentiment.SKEPTICAL,
            ),
            DebateTurn(
                round_number=1,
                role=StakeholderRole.CHAMPION,
                name="Champion",
                statement="Eu apoio, mas precisamos de munição.",
                objections_raised=[],
                sentiment=Sentiment.SUPPORTIVE,
            ),
        ],
        verdict=DebateVerdict(
            consensus_reached=False,
            overall_sentiment=Sentiment.SKEPTICAL,
            top_objections=["ROI pouco claro"],
            blocking_stakeholders=[StakeholderRole.CFO],
            recommended_talk_track=[],
            risk_summary="",
        ),
    )


def test_collect_predictions_uses_objections_and_skeptical_statements():
    record = _record()
    preds = _collect_predictions(record)
    assert preds["cfo"] == ["ROI pouco claro"]
    # Champion foi supportive sem objeção — não vira previsão.
    assert "champion" not in preds


def test_calibrate_builds_report_from_llm_matches():
    report = calibrate(_record(), "Transcrição: não vi retorno nesse número...", FakeLLMClient())

    assert isinstance(report, CalibrationReport)
    roles = {p.role for p in report.personas}
    assert roles == {StakeholderRole.CFO, StakeholderRole.CTO}
    cfo = next(p for p in report.personas if p.role == StakeholderRole.CFO)
    assert cfo.fidelity == 1.0
    assert report.overall_fidelity == 0.5
    assert report.blind_spots == ["preocupação com lock-in de fornecedor"]
    assert report.data_enrichment_suggestions

    md = report.to_markdown()
    assert "Fidelidade geral: 50%" in md
    assert "Pontos cegos" in md
