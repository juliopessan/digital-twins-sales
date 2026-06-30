"""Synthesizer: turns the full transcript into a DebateVerdict the sales rep can act on."""
from __future__ import annotations

import json
import logging

from digital_twins.config import settings
from digital_twins.i18n import to_pt_br, to_pt_br_list
from digital_twins.llm.client import LLMClient
from digital_twins.models import DebateVerdict, Sentiment, StakeholderRole
from digital_twins.orchestration.state import BoardState

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
Você está sintetizando a transcrição de um debate simulado de comitê de
compra em um veredito acionável para o vendedor que vai enfrentar esse
comitê de verdade.

Retorne ESTRITAMENTE um objeto JSON com este formato. As CHAVES e os
VALORES de "overall_sentiment" e "blocking_stakeholders" devem ficar
exatamente em inglês, como mostrado abaixo — apenas o CONTEÚDO textual
(objeções, talk track, resumo de risco) deve estar em português:
{
  "consensus_reached": bool,
  "overall_sentiment": "supportive" | "neutral" | "skeptical" | "blocking",
  "top_objections": [string, ...],          // em português
  "blocking_stakeholders": [string, ...]    // DEVE usar apenas estes valores exatos de papel:
                                             // "cfo", "cto", "procurement", "end_user",
                                             // "champion", "legal_compliance", "ceo", "security"
  "recommended_talk_track": [string, ...],  // conselho concreto e específico para a próxima call, em português
  "risk_summary": string                    // em português
}

Seja específico e tático. "Endereçar melhor as preocupações" é inútil;
"Abrir com uma tabela de TCO de 3 anos antes de qualquer demo de feature,
porque a objeção do CFO foi especificamente sobre custo de integração
oculto" é útil.
"""


def make_synthesize_node(llm: LLMClient):
    def synthesize(state: BoardState) -> dict:
        transcript = state.get("transcript", [])
        full_text = "\n".join(
            f"[Rodada {t.round_number}] {t.name} ({t.sentiment.value}): {t.statement}" for t in transcript
        )

        raw = llm.complete(
            system=_SYNTHESIS_SYSTEM_PROMPT,
            user=f"Transcrição completa:\n{full_text}",
            model=settings.synthesizer_model,
            max_tokens=settings.max_tokens_synthesis,
            json_mode=True,
        )

        try:
            parsed = json.loads(raw)
            verdict = DebateVerdict(
                consensus_reached=parsed["consensus_reached"],
                overall_sentiment=Sentiment(parsed["overall_sentiment"]),
                top_objections=to_pt_br_list(parsed["top_objections"]),
                blocking_stakeholders=[StakeholderRole(r) for r in parsed["blocking_stakeholders"]],
                recommended_talk_track=to_pt_br_list(parsed["recommended_talk_track"]),
                risk_summary=to_pt_br(parsed["risk_summary"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Synthesizer output failed validation (%s); raw=%r", exc, raw)
            verdict = DebateVerdict(
                consensus_reached=False,
                overall_sentiment=Sentiment.NEUTRAL,
                top_objections=["A síntese falhou — veja os logs; a transcrição bruta ainda está disponível."],
                blocking_stakeholders=[],
                recommended_talk_track=["Rode a síntese de novo ou revise a transcrição manualmente."],
                risk_summary=f"Erro de parsing do Synthesizer: {exc}",
            )

        return {"verdict": verdict}

    return synthesize
