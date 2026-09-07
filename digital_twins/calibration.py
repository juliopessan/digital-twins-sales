"""
Post-call calibration — the "twin vs reality" loop applied to sales.

In industrial digital twins, the twin is continuously compared against the
asset's real sensors; the deviation between simulated and real measures the
twin's fidelity and points to where the model needs retuning. Here the
"sensor" is the real call transcript:

  1. You ran the simulation before the call (the CLI saved a
     SimulationRecord to reports/<slug>-<ts>.json).
  2. The call happened; you have the transcript (Gong/Granola/notes).
  3. This module compares objection by objection: what the twin PREDICTED
     and happened (hit), what it predicted and did not happen (noise), and
     what happened without being predicted (blind spot) — with fidelity per
     persona and concrete suggestions on which facts to add to
     AccountContext.real_data.

CLI usage:

    python -m digital_twins.calibration --simulation reports/account-x.json \
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
        description="Excerpt from the real call confirming the objection (empty if it didn't occur).",
    )


class PersonaCalibration(BaseModel):
    role: StakeholderRole
    matches: list[ObjectionMatch] = Field(default_factory=list)

    @property
    def fidelity(self) -> float:
        """Fraction of the objections predicted by this persona that actually occurred."""
        if not self.matches:
            return 0.0
        return sum(1 for m in self.matches if m.occurred) / len(self.matches)


class CalibrationReport(BaseModel):
    account_name: str
    personas: list[PersonaCalibration] = Field(default_factory=list)
    blind_spots: list[str] = Field(
        default_factory=list,
        description="Objections that came up in the real call but the twin did NOT predict.",
    )
    data_enrichment_suggestions: list[str] = Field(
        default_factory=list,
        description="Concrete facts to add to AccountContext.real_data for the next simulation.",
    )

    @property
    def overall_fidelity(self) -> float:
        all_matches = [m for p in self.personas for m in p.matches]
        if not all_matches:
            return 0.0
        return sum(1 for m in all_matches if m.occurred) / len(all_matches)

    def to_markdown(self) -> str:
        lines = [
            f"# Twin Calibration — {self.account_name}",
            "",
            f"**Overall fidelity: {self.overall_fidelity:.0%}** "
            "(predicted objections that actually occurred on the call)",
            "",
            "| Persona | Fidelity | Predicted | Confirmed |",
            "|---|---|---|---|",
        ]
        for p in self.personas:
            hits = sum(1 for m in p.matches if m.occurred)
            lines.append(f"| {p.role.value} | {p.fidelity:.0%} | {len(p.matches)} | {hits} |")

        lines += ["", "## Hits and noise by persona", ""]
        for p in self.personas:
            lines.append(f"### {p.role.value}")
            for m in p.matches:
                mark = "✅" if m.occurred else "❌"
                lines.append(f"- {mark} {m.predicted_objection}")
                if m.evidence:
                    lines.append(f"  - evidence: \"{m.evidence}\"")
            lines.append("")

        lines += ["## Blind spots (occurred but not predicted)", ""]
        lines += [f"- {b}" for b in self.blind_spots] or ["- (none)"]
        lines += ["", "## Suggested data enrichment (real_data)", ""]
        lines += [f"- {s}" for s in self.data_enrichment_suggestions] or ["- (none)"]
        return "\n".join(lines)


def _collect_predictions(record: SimulationRecord) -> dict[str, list[str]]:
    """Objections predicted per role: from the debate turns + the verdict's top_objections.

    The verdict's top_objections have no role attached — they go to the most
    likely blocking stakeholder's role if identifiable, otherwise they are
    left out of the per-persona count (the LLM still sees them in the
    general block).
    """
    by_role: dict[str, list[str]] = defaultdict(list)
    for turn in record.transcript:
        for obj in turn.objections_raised:
            if obj not in by_role[turn.role.value]:
                by_role[turn.role.value].append(obj)
        # Skeptical/blocking statements are, in practice, objections even
        # when literal matching against known_objections caught nothing.
        if turn.sentiment.value in ("skeptical", "blocking") and not turn.objections_raised:
            by_role[turn.role.value].append(turn.statement)
    return dict(by_role)


_CALIBRATION_SYSTEM_PROMPT = """\
You compare what a SIMULATED buying committee predicted against what
happened on a REAL sales call. For each predicted objection, decide whether
it actually occurred on the call (even in different words — what matters is
the substance) and cite the excerpt from the call that proves it. Then list
objections that came up on the real call and were NOT predicted (blind
spots), and suggest concrete facts about the real stakeholders that, if
added to the account data, would improve the next simulation.

Return STRICTLY a JSON object in this format (keys in English, text in
English; "role" uses exactly the role values provided in the input):
{
  "matches": [
    {"role": "cfo", "predicted_objection": "...", "occurred": true, "evidence": "excerpt from the call"}
  ],
  "blind_spots": ["real objection not predicted", ...],
  "data_enrichment_suggestions": ["concrete fact to add to real_data", ...]
}
Include in "matches" ALL of the predicted objections provided, each with its
occurred true/false verdict.
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
        f"Objections predicted by the twin (by role):\n{predicted_block or '(none)'}\n\n"
        f"Top objections from the simulated verdict (no role assigned):\n{verdict_block or '(none)'}\n\n"
        f"Transcript of the REAL call:\n{call_transcript}"
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
                logger.warning("Calibration returned unknown role %r — ignoring", role_value)
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
        logger.error("Calibration output is not valid JSON (%s); raw=%r", exc, raw)
        blind_spots = ["Calibration failed — the LLM output was not valid JSON; run it again."]

    return CalibrationReport(
        account_name=record.account.account_name,
        personas=list(by_role.values()),
        blind_spots=blind_spots,
        data_enrichment_suggestions=suggestions,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compares a saved simulation against the real call transcript (twin calibration)."
    )
    parser.add_argument("--simulation", required=True, help="reports/<slug>-<ts>.json saved by main")
    parser.add_argument("--call-transcript", required=True, help="text file with the real call transcript")
    parser.add_argument("--out", default=None, help="save the markdown report to this path")
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
        print(f"\nReport saved to: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
