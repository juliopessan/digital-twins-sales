"""
CLI entry point.

    python -m digital_twins.main                          # precisa de ANTHROPIC_API_KEY
    python -m digital_twins.main --account minha_conta.json  # carrega uma AccountContext real do disco

Saída: transcrição completa rodada a rodada, seguida do veredito final.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from digital_twins.config import settings
from digital_twins.llm.client import build_default_client
from digital_twins.models import AccountContext, StakeholderRole
from digital_twins.orchestration.graph import build_board_graph
from digital_twins.personas.resolver import PersonaFactory
from digital_twins.reporting import build_html_report, build_markdown_report


def _sample_account() -> AccountContext:
    """Exemplo de trabalho: deal corporativo de Gen AI, CFO com dados reais de embasamento, resto arquétipos."""
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
            # Apenas o CFO tem embasamento real — os demais caem para o arquétipo.
            StakeholderRole.CFO: [
                "Publicou no LinkedIn no trimestre passado sobre 'fazer mais com menos' após um congelamento de contratações",
                "Já rejeitou um fornecedor de automação parecido (categoria diferente) por matemática de ROI pouco clara",
                "Reporta diretamente a um CEO que assumiu publicamente o compromisso de reduzir o opex em 15% neste ano fiscal",
            ]
        },
    )


def _load_account(path: str) -> AccountContext:
    with open(path, "r", encoding="utf-8") as f:
        return AccountContext.model_validate(json.load(f))


def main() -> int:
    parser = argparse.ArgumentParser(description="Roda uma simulação de comitê de compra com digital twins de vendas.")
    parser.add_argument("--account", type=str, default=None, help="Caminho para um arquivo JSON de AccountContext")
    parser.add_argument("--max-rounds", type=int, default=settings.max_rounds)
    parser.add_argument(
        "--report-dir", type=str, default="reports",
        help="Diretório onde salvar o relatório para o time de vendas (padrão: reports/)",
    )
    parser.add_argument("--no-report", action="store_true", help="Não gerar o relatório")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    account = _load_account(args.account) if args.account else _sample_account()
    personas = PersonaFactory.build_committee(account)

    print(f"\n=== Comitê: {account.account_name} ({account.deal_stage}) ===")
    for p in personas:
        tag = "REAL" if p.source.value == "real" else "ARQUÉTIPO"
        print(f"  - {p.name} [{p.role.value}] ({tag}, veto={p.decision_power})")
    print()

    llm = build_default_client()
    app = build_board_graph(llm)

    initial_state = {
        "account": account,
        "personas": personas,
        "round_number": 0,
        "max_rounds": args.max_rounds,
        "transcript": [],
        "current_index": 0,
        "speaking_order": [],
        "facilitator_decision": "continue",
    }

    final_state = app.invoke(initial_state)

    last_round = 0
    for turn in final_state["transcript"]:
        if turn.round_number != last_round:
            last_round = turn.round_number
            print(f"\n--- Rodada {last_round} ---")
        print(f"[{turn.sentiment.value:>10}] {turn.name}: {turn.statement}")

    verdict = final_state["verdict"]
    print("\n=== VEREDITO ===")
    print(f"Consenso atingido: {verdict.consensus_reached}")
    print(f"Sentimento geral: {verdict.overall_sentiment.value}")
    print(f"Stakeholders bloqueadores: {[r.value for r in verdict.blocking_stakeholders]}")
    print("\nPrincipais objeções:")
    for o in verdict.top_objections:
        print(f"  - {o}")
    print("\nPlano de ação recomendado:")
    for t in verdict.recommended_talk_track:
        print(f"  - {t}")
    print(f"\nAvaliação de risco: {verdict.risk_summary}")

    if verdict.meddpicc_scorecard:
        print("\nScorecard MEDDPICC:")
        for dimension, assessment in verdict.meddpicc_scorecard.items():
            print(f"  - {dimension}: {assessment}")

    if verdict.seller_coaching:
        sc = verdict.seller_coaching
        print("\n=== COACH — AVALIAÇÃO DO SEU PITCH ===")
        print(f"Nota: {sc.pitch_grade}")
        if sc.what_landed:
            print("O que funcionou:")
            for item in sc.what_landed:
                print(f"  - {item}")
        if sc.what_backfired:
            print("O que saiu pela culatra:")
            for item in sc.what_backfired:
                print(f"  - {item}")
        if sc.rewrite_suggestions:
            print("Sugestões de reescrita:")
            for item in sc.rewrite_suggestions:
                print(f"  - {item}")

    if not args.no_report:
        transcript = final_state["transcript"]
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", account.account_name.lower()).strip("-")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        md_report = build_markdown_report(account, personas, transcript, verdict)
        md_path = report_dir / f"{slug}-{timestamp}.md"
        md_path.write_text(md_report, encoding="utf-8")

        html_report = build_html_report(account, personas, transcript, verdict)
        html_path = report_dir / f"{slug}-{timestamp}.html"
        html_path.write_text(html_report, encoding="utf-8")

        print(f"\nRelatório salvo em: {md_path}")
        print(f"Relatório estilizado (HTML) salvo em: {html_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
