"""
CLI entry point.

    python -m digital_twins.main --mock                 # no API key needed, deterministic demo
    python -m digital_twins.main                          # real Claude calls (needs ANTHROPIC_API_KEY)
    python -m digital_twins.main --account my_deal.json   # load a real AccountContext from disk

Output: full transcript printed round-by-round, then the final verdict.
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
    """A worked example: enterprise Gen AI deal, CFO has real grounding data, rest are archetypes."""
    return AccountContext(
        account_name="Northwind Logistics",
        deal_stage="Proposal sent, awaiting committee review",
        pitch_summary=(
            "Multi-agent Gen AI platform to automate freight document processing, "
            "replacing a 14-person manual review team with a 3-person oversight team."
        ),
        proposed_solution=(
            "Azure-hosted agentic pipeline: OCR + extraction agents + human-in-the-loop "
            "exception handling, 18-week implementation, $640k Year 1 (license + services)."
        ),
        deal_value_usd=640_000,
        roles_in_committee=[
            StakeholderRole.CHAMPION,
            StakeholderRole.CTO,
            StakeholderRole.CFO,
            StakeholderRole.PROCUREMENT,
        ],
        real_data={
            # Only the CFO has real grounding — everyone else falls back to archetype.
            StakeholderRole.CFO: [
                "Posted on LinkedIn last quarter about 'doing more with less' after a hiring freeze",
                "Previously rejected a similar automation vendor (different category) over unclear ROI math",
                "Reports directly to a CEO who publicly committed to 15% opex reduction this fiscal year",
            ]
        },
    )


def _load_account(path: str) -> AccountContext:
    with open(path, "r", encoding="utf-8") as f:
        return AccountContext.model_validate(json.load(f))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a sales digital-twins board debate.")
    parser.add_argument("--mock", action="store_true", help="Use MockLLMClient (no API key needed)")
    parser.add_argument("--account", type=str, default=None, help="Path to a JSON AccountContext file")
    parser.add_argument("--max-rounds", type=int, default=settings.max_rounds)
    parser.add_argument(
        "--report-dir", type=str, default="reports",
        help="Directory to write the sales-facing Markdown report into (default: reports/)",
    )
    parser.add_argument("--no-report", action="store_true", help="Skip writing the Markdown report")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    account = _load_account(args.account) if args.account else _sample_account()
    personas = PersonaFactory.build_committee(account)

    print(f"\n=== Board: {account.account_name} ({account.deal_stage}) ===")
    for p in personas:
        tag = "REAL" if p.source.value == "real" else "ARCHETYPE"
        print(f"  - {p.name} [{p.role.value}] ({tag}, veto={p.decision_power})")
    print()

    llm = build_default_client(mock=args.mock)
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
            print(f"\n--- Round {last_round} ---")
        print(f"[{turn.sentiment.value:>10}] {turn.name}: {turn.statement}")

    verdict = final_state["verdict"]
    print("\n=== VERDICT ===")
    print(f"Consensus reached: {verdict.consensus_reached}")
    print(f"Overall sentiment: {verdict.overall_sentiment.value}")
    print(f"Blocking stakeholders: {[r.value for r in verdict.blocking_stakeholders]}")
    print("\nTop objections:")
    for o in verdict.top_objections:
        print(f"  - {o}")
    print("\nRecommended talk track:")
    for t in verdict.recommended_talk_track:
        print(f"  - {t}")
    print(f"\nRisk summary: {verdict.risk_summary}")

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

        print(f"\nReport written to: {md_path}")
        print(f"Styled HTML report written to: {html_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
