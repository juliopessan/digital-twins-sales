"""
CLI entry point.

    python -m digital_twins.main                          # needs ANTHROPIC_API_KEY
    python -m digital_twins.main --account my_account.json  # loads a real AccountContext from disk

Output: full transcript round by round, followed by the final verdict.
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
from digital_twins.models import AccountContext, SimulationRecord, StakeholderRole
from digital_twins.orchestration.graph import build_board_graph
from digital_twins.personas.resolver import PersonaFactory
from digital_twins.reporting import build_html_report, build_markdown_report
from digital_twins.scenarios import ScenarioSpec, build_comparison_markdown, run_scenarios


def _sample_account() -> AccountContext:
    """Working example: corporate Gen AI deal, CFO with real grounding data, the rest archetypes."""
    return AccountContext(
        account_name="Northwind Logistics",
        deal_stage="Proposal sent, awaiting committee review",
        pitch_summary=(
            "Multi-agent Gen AI platform to automate freight document processing, "
            "replacing a 14-person manual review team with a 3-person oversight team."
        ),
        proposed_solution=(
            "Agentic pipeline hosted on Azure: OCR + extraction + exception-handling agents "
            "with a human in the loop, 18-week rollout, $640k in Year 1 (license + services)."
        ),
        deal_value_usd=640_000,
        roles_in_committee=[
            StakeholderRole.CHAMPION,
            StakeholderRole.CTO,
            StakeholderRole.CFO,
            StakeholderRole.PROCUREMENT,
        ],
        real_data={
            # Only the CFO has real grounding data — the rest fall back to the archetype.
            StakeholderRole.CFO: [
                "Posted on LinkedIn last quarter about 'doing more with less' after a hiring freeze",
                "Already rejected a similar automation vendor (different category) over unclear ROI math",
                "Reports directly to a CEO who publicly committed to cutting opex by 15% this fiscal year",
            ]
        },
    )


def _load_account(path: str) -> AccountContext:
    with open(path, "r", encoding="utf-8") as f:
        return AccountContext.model_validate(json.load(f))


def main() -> int:
    parser = argparse.ArgumentParser(description="Runs a buying-committee simulation with sales digital twins.")
    parser.add_argument("--account", type=str, default=None, help="Path to an AccountContext JSON file")
    parser.add_argument("--max-rounds", type=int, default=settings.max_rounds)
    parser.add_argument(
        "--report-dir", type=str, default="reports",
        help="Directory to save the sales-team report to (default: reports/)",
    )
    parser.add_argument("--no-report", action="store_true", help="Do not generate the report")
    parser.add_argument(
        "--scenarios", type=str, default=None,
        help=(
            "Path to a JSON file with a list of what-if scenarios (ScenarioSpec). "
            "Instead of a single debate, runs one debate per scenario and generates "
            "a side-by-side comparison sorted by risk."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    account = _load_account(args.account) if args.account else _sample_account()

    if args.scenarios:
        return _run_scenario_mode(account, args)

    personas = PersonaFactory.build_committee(account)

    print(f"\n=== Committee: {account.account_name} ({account.deal_stage}) ===")
    for p in personas:
        tag = "REAL" if p.source.value == "real" else "ARCHETYPE"
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
    print("\nRecommended action plan:")
    for t in verdict.recommended_talk_track:
        print(f"  - {t}")
    print(f"\nRisk assessment: {verdict.risk_summary}")

    if verdict.meddpicc_scorecard:
        print("\nMEDDPICC scorecard:")
        for dimension, assessment in verdict.meddpicc_scorecard.items():
            print(f"  - {dimension}: {assessment}")

    if verdict.seller_coaching:
        sc = verdict.seller_coaching
        print("\n=== COACH — EVALUATION OF YOUR PITCH ===")
        print(f"Grade: {sc.pitch_grade}")
        if sc.what_landed:
            print("What landed:")
            for item in sc.what_landed:
                print(f"  - {item}")
        if sc.what_backfired:
            print("What backfired:")
            for item in sc.what_backfired:
                print(f"  - {item}")
        if sc.rewrite_suggestions:
            print("Rewrite suggestions:")
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

        # Full snapshot for post-call calibration (digital_twins.calibration):
        # later compares what the twin predicted with the real call transcript.
        record = SimulationRecord(
            created_at=datetime.now(timezone.utc).isoformat(),
            account=account,
            transcript=transcript,
            verdict=verdict,
        )
        json_path = report_dir / f"{slug}-{timestamp}.json"
        json_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        print(f"\nReport saved to: {md_path}")
        print(f"Styled (HTML) report saved to: {html_path}")
        print(f"Post-call calibration snapshot saved to: {json_path}")
        print(
            "After the real call: python -m digital_twins.calibration "
            f"--simulation {json_path} --call-transcript <file.txt>"
        )

    return 0


def _run_scenario_mode(account: AccountContext, args) -> int:
    """What-if scenario mode: one debate per deal variant, compared by risk."""
    with open(args.scenarios, "r", encoding="utf-8") as f:
        specs = [ScenarioSpec.model_validate(s) for s in json.load(f)]
    if not specs:
        print("Scenario file is empty — nothing to run.")
        return 1

    print(f"\n=== What-if scenarios: {account.account_name} ({len(specs)} branches) ===")
    for s in specs:
        print(f"  - {s.name}" + (f": {s.description}" if s.description else ""))

    llm = build_default_client()
    outcomes = run_scenarios(account, specs, llm, max_rounds=args.max_rounds)

    comparison = build_comparison_markdown(account, outcomes)
    print("\n" + comparison)

    if not args.no_report:
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", account.account_name.lower()).strip("-")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        cmp_path = report_dir / f"{slug}-scenarios-{timestamp}.md"
        cmp_path.write_text(comparison, encoding="utf-8")
        print(f"\nComparison saved to: {cmp_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
