"""
Calibração pós-call — o loop "twin vs realidade" do Palantir Vertex aplicado
a vendas.

No Vertex, o digital twin é continuamente comparado com os sensores reais do
ativo; o desvio entre simulado e real mede a fidelidade do twin e aponta onde
o modelo precisa ser retunado. Aqui o "sensor" é a transcrição da call real:

  1. Você rodou a simulação antes da call (o CLI salvou um SimulationRecord
     em reports/<slug>-<ts>.json).
  2. A call aconteceu; você tem a transcrição (Gong/Granola/notas).
  3. Este módulo compara objeção a objeção: o que o twin PREVIU e aconteceu
     (acerto), o que previu e não aconteceu (ruído) e o que aconteceu sem
     ter sido previsto (ponto cego) — com fidelidade por persona e sugestões
     concretas de quais fatos adicionar em AccountContext.real_data.

Uso via CLI:

    python -m digital_twins.calibration --simulation reports/conta-x.json \
        --call-transcript call.txt
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict

from pydantic import BaseModel, Field

from digital_twins.config import settings
from digital_twins.llm.client import LLMClient, build_default_client
from digital_twins.models import SimulationRecord, StakeholderRole

logger = logging.getLogger(__name__)


class ObjectionMatch(BaseModel):
    predicted_objection: str
    occurred: bool
    evidence: str = Field(
        default="",
        description="Trecho da call real que confirma a objeção (vazio se não ocorreu).",
    )


class PersonaCalibration(BaseModel):
    role: StakeholderRole
    matches: list[ObjectionMatch] = Field(default_factory=list)

    @property
    def fidelity(self) -> float:
        """Fração das objeções previstas por esta persona que ocorreram de fato."""
        if not self.matches:
            return 0.0
        return sum(1 for m in self.matches if m.occurred) / len(self.matches)


class CalibrationReport(BaseModel):
    account_name: str
    personas: list[PersonaCalibration] = Field(default_factory=list)
    blind_spots: list[str] = Field(
        default_factory=list,
        description="Objeções que apareceram na call real mas o twin NÃO previu.",
    )
    data_enrichment_suggestions: list[str] = Field(
        default_factory=list,
        description="Fatos concretos a adicionar em AccountContext.real_data para a próxima simulação.",
    )

    @property
    def overall_fidelity(self) -> float:
        all_matches = [m for p in self.personas for m in p.matches]
        if not all_matches:
            return 0.0
        return sum(1 for m in all_matches if m.occurred) / len(all_matches)

    def to_markdown(self) -> str:
        lines = [
            f"# Calibração do twin — {self.account_name}",
            "",
            f"**Fidelidade geral: {self.overall_fidelity:.0%}** "
            "(objeções previstas que ocorreram de fato na call)",
            "",
            "| Persona | Fidelidade | Previstas | Confirmadas |",
            "|---|---|---|---|",
        ]
        for p in self.personas:
            hits = sum(1 for m in p.matches if m.occurred)
            lines.append(f"| {p.role.value} | {p.fidelity:.0%} | {len(p.matches)} | {hits} |")

        lines += ["", "## Acertos e ruído por persona", ""]
        for p in self.personas:
            lines.append(f"### {p.role.value}")
            for m in p.matches:
                mark = "✅" if m.occurred else "❌"
                lines.append(f"- {mark} {m.predicted_objection}")
                if m.evidence:
                    lines.append(f"  - evidência: \"{m.evidence}\"")
            lines.append("")

        lines += ["## Pontos cegos (ocorreram e não foram previstos)", ""]
        lines += [f"- {b}" for b in self.blind_spots] or ["- (nenhum)"]
        lines += ["", "## Enriquecimento de dados sugerido (real_data)", ""]
        lines += [f"- {s}" for s in self.data_enrichment_suggestions] or ["- (nenhum)"]
        return "\n".join(lines)


def _collect_predictions(record: SimulationRecord) -> dict[str, list[str]]:
    """Objeções previstas por papel: das falas do debate + top_objections do veredito.

    As top_objections do veredito não têm papel — vão para o papel do
    stakeholder bloqueador mais provável se identificável, senão ficam de
    fora da conta por-persona (o LLM ainda as vê no bloco geral).
    """
    by_role: dict[str, list[str]] = defaultdict(list)
    for turn in record.transcript:
        for obj in turn.objections_raised:
            if obj not in by_role[turn.role.value]:
                by_role[turn.role.value].append(obj)
        # Falas céticas/bloqueadoras são, na prática, objeções mesmo quando o
        # matching literal com known_objections não capturou nada.
        if turn.sentiment.value in ("skeptical", "blocking") and not turn.objections_raised:
            by_role[turn.role.value].append(turn.statement)
    return dict(by_role)


_CALIBRATION_SYSTEM_PROMPT = """\
Você compara o que um comitê de compra SIMULADO previu com o que aconteceu
numa call de vendas REAL. Para cada objeção prevista, decida se ela ocorreu
de fato na call (mesmo com outras palavras — o que importa é a substância) e
cite o trecho da call que comprova. Depois liste objeções que apareceram na
call real e NÃO estavam previstas (pontos cegos), e sugira fatos concretos
sobre os stakeholders reais que, se adicionados aos dados da conta,
melhorariam a próxima simulação.

Retorne ESTRITAMENTE um objeto JSON neste formato (chaves em inglês, textos
em português; "role" usa exatamente os valores de papel fornecidos no input):
{
  "matches": [
    {"role": "cfo", "predicted_objection": "...", "occurred": true, "evidence": "trecho da call"}
  ],
  "blind_spots": ["objeção real não prevista", ...],
  "data_enrichment_suggestions": ["fato concreto a adicionar em real_data", ...]
}
Inclua em "matches" TODAS as objeções previstas fornecidas, cada uma com seu
veredito occurred true/false.
"""


def calibrate(
    record: SimulationRecord,
    call_transcript: str,
    llm: LLMClient,
) -> CalibrationReport:
    predictions = _collect_predictions(record)

    predicted_block = "\n".join(
        f"- [{role}] {obj}" for role, objs in predictions.items() for obj in objs
    )
    verdict_block = "\n".join(f"- {o}" for o in record.verdict.top_objections)

    user = (
        f"Objeções previstas pelo twin (por papel):\n{predicted_block or '(nenhuma)'}\n\n"
        f"Top objeções do veredito simulado (sem papel atribuído):\n{verdict_block or '(nenhuma)'}\n\n"
        f"Transcrição da call REAL:\n{call_transcript}"
    )

    raw = llm.complete(
        system=_CALIBRATION_SYSTEM_PROMPT,
        user=user,
        model=settings.synthesizer_model,
        max_tokens=settings.max_tokens_synthesis,
        json_mode=True,
    )

    by_role: dict[str, PersonaCalibration] = {}
    blind_spots: list[str] = []
    suggestions: list[str] = []
    try:
        parsed = json.loads(raw)
        for m in parsed.get("matches", []):
            role_value = m.get("role", "")
            try:
                role = StakeholderRole(role_value)
            except ValueError:
                logger.warning("Calibração retornou papel desconhecido %r — ignorando", role_value)
                continue
            entry = by_role.setdefault(role.value, PersonaCalibration(role=role))
            entry.matches.append(
                ObjectionMatch(
                    predicted_objection=m.get("predicted_objection", ""),
                    occurred=bool(m.get("occurred", False)),
                    evidence=m.get("evidence", "") or "",
                )
            )
        blind_spots = [str(b) for b in parsed.get("blind_spots", [])]
        suggestions = [str(s) for s in parsed.get("data_enrichment_suggestions", [])]
    except json.JSONDecodeError as exc:
        logger.error("Saída da calibração não é JSON válido (%s); raw=%r", exc, raw)
        blind_spots = ["A calibração falhou — saída do LLM não era JSON válido; rode novamente."]

    return CalibrationReport(
        account_name=record.account.account_name,
        personas=list(by_role.values()),
        blind_spots=blind_spots,
        data_enrichment_suggestions=suggestions,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara uma simulação salva com a transcrição da call real (calibração do twin)."
    )
    parser.add_argument("--simulation", required=True, help="reports/<slug>-<ts>.json salvo pelo main")
    parser.add_argument("--call-transcript", required=True, help="arquivo texto com a transcrição da call real")
    parser.add_argument("--out", default=None, help="salvar o relatório markdown neste caminho")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    with open(args.simulation, "r", encoding="utf-8") as f:
        record = SimulationRecord.model_validate(json.load(f))
    with open(args.call_transcript, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    report = calibrate(record, transcript_text, build_default_client())
    md = report.to_markdown()
    print(md)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\nRelatório salvo em: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
