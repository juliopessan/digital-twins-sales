"""Synthesizer: turns the full transcript into a DebateVerdict the sales rep can act on."""
from __future__ import annotations

import json
import logging

from digital_twins.config import settings
from digital_twins.i18n import to_pt_br, to_pt_br_list
from digital_twins.llm.client import LLMClient
from digital_twins.models import DebateVerdict, SellerCoaching, Sentiment, StakeholderRole
from digital_twins.orchestration.state import BoardState

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
Você está sintetizando a transcrição de um debate simulado de comitê de
compra em um veredito acionável para o vendedor que vai enfrentar esse
comitê de verdade.

Além do veredito geral, avalie o debate sob a ótica do framework de vendas
enterprise MEDDPICC — mas SÓ para as dimensões que o debate realmente
revelou evidência (não invente avaliação para o que não apareceu):
- "Metrics": foi possível provar ROI/métricas concretas para quem decide o orçamento?
- "Economic Buyer": o stakeholder de maior poder de veto tendeu a bloquear ou apoiar, e por quê?
- "Identify Pain": a dor técnica/operacional levantada foi endereçada por algum outro stakeholder (ex: o Champion) durante o debate?
- "Champion": o Champion interno (se houver) trouxe munição real ou só ficou na defensiva?
Inclua apenas as dimensões acima que tiverem evidência clara na transcrição.

Retorne ESTRITAMENTE um objeto JSON com este formato. As CHAVES e os
VALORES de "overall_sentiment" e "blocking_stakeholders" devem ficar
exatamente em inglês, como mostrado abaixo — apenas o CONTEÚDO textual
(objeções, talk track, resumo de risco, scorecard) deve estar em português:
{
  "consensus_reached": bool,
  "overall_sentiment": "supportive" | "neutral" | "skeptical" | "blocking",
  "top_objections": [string, ...],          // em português
  "blocking_stakeholders": [string, ...]    // DEVE usar apenas estes valores exatos de papel:
                                             // "cfo", "cto", "procurement", "end_user",
                                             // "champion", "legal_compliance", "ceo", "security", "salesman"
  "recommended_talk_track": [string, ...],  // conselho concreto e específico para a próxima call, em português
  "risk_summary": string,                   // em português
  "meddpicc_scorecard": {                   // em português, só dimensões com evidência (pode ser {})
    "Metrics": string,
    "Economic Buyer": string,
    "Identify Pain": string,
    "Champion": string
  }
}

Seja específico e tático. "Endereçar melhor as preocupações" é inútil;
"Abrir com uma tabela de TCO de 3 anos antes de qualquer demo de feature,
porque a objeção do CFO foi especificamente sobre custo de integração
oculto" é útil.
"""

_SELLER_COACHING_ADDENDUM = """\

IMPORTANTE: houve uma fala de abertura REAL do vendedor (fornecida no início
do input). Além do veredito acima, atue como um coach de vendas e avalie o
DESEMPENHO DO VENDEDOR — como as PALAVRAS dele se sustentaram (ou não)
diante das objeções que o comitê levantou no debate. Não avalie o comitê
aqui; avalie a pessoa que fez o pitch.

Adicione ao mesmo JSON o campo "seller_coaching" com este formato (tudo em
português):
"seller_coaching": {
  "pitch_grade": string,            // nota curta e honesta, ex: "C+ — forte em ROI, fraco em governança"
  "what_landed": [string, ...],     // afirmações da fala dele que ressoaram ou não foram contestadas
  "what_backfired": [string, ...],  // afirmações que foram atacadas e que ele não sustentaria
  "rewrite_suggestions": [string, ...] // reescritas concretas: "em vez de X, diga Y porque Z"
}
"""


def _parse_seller_coaching(sc: dict | None) -> SellerCoaching | None:
    if not sc:
        return None
    return SellerCoaching(
        pitch_grade=to_pt_br(sc.get("pitch_grade", "")),
        what_landed=to_pt_br_list(sc.get("what_landed", [])),
        what_backfired=to_pt_br_list(sc.get("what_backfired", [])),
        rewrite_suggestions=to_pt_br_list(sc.get("rewrite_suggestions", [])),
    )


def make_synthesize_node(llm: LLMClient, feedback_block: str = ""):
    def synthesize(state: BoardState) -> dict:
        transcript = state.get("transcript", [])
        full_text = "\n".join(
            f"[Rodada {t.round_number}] {t.name} ({t.sentiment.value}): {t.statement}" for t in transcript
        )

        account = state["account"]
        system_prompt = _SYNTHESIS_SYSTEM_PROMPT
        if feedback_block:
            system_prompt = feedback_block + "\n\n" + system_prompt
        user_content = f"Transcrição completa:\n{full_text}"
        if account.seller_opening:
            system_prompt = _SYNTHESIS_SYSTEM_PROMPT + _SELLER_COACHING_ADDENDUM
            user_content = (
                f'Fala de abertura do vendedor:\n"{account.seller_opening}"\n\n' + user_content
            )

        raw = llm.complete(
            system=system_prompt,
            user=user_content,
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
                meddpicc_scorecard={
                    dim: to_pt_br(assessment)
                    for dim, assessment in parsed.get("meddpicc_scorecard", {}).items()
                },
                seller_coaching=_parse_seller_coaching(parsed.get("seller_coaching")),
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
