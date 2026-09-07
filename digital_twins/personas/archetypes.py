"""
Curated stakeholder archetypes.

These are the fallback personas used whenever AccountContext.real_data has
no entry (or an empty list) for a given role. They were deliberately
written from patterns seen in B2B Gen AI enterprise deals — adjust
priorities/objections for your vertical as you collect more real debate
transcripts.
"""
from __future__ import annotations

from digital_twins.models import StakeholderProfile, StakeholderRole, DataSource

ARCHETYPES: dict[StakeholderRole, StakeholderProfile] = {
    StakeholderRole.SALESMAN: StakeholderProfile(
        role=StakeholderRole.SALESMAN,
        name="Accountable Salesperson",
        company="",  # Set by Factory/Context
        source=DataSource.ARCHETYPE,
        priorities=[
            "Resolve the committee's objections with technical and commercial transparency",
            "Demonstrate the added value and ROI of the proposed solution",
            "Ensure the next steps of the deal are defined and agreed upon",
        ],
        known_objections=[],  # Salesman responds to objections, doesn't raise them
        decision_power=0.0,   # Doesn't vote in the internal committee
        tone="consultative, confident, empathetic, and focused on solving the customer's problems",
    ),
    StakeholderRole.CFO: StakeholderProfile(
        role=StakeholderRole.CFO,
        name="Generic CFO",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "3-year total cost of ownership, not just the license cost",
            "Predictable, defensible ROI tied to a hard metric (headcount, cycle time, revenue)",
            "Avoiding vendor lock-in and pricing shocks at renewal",
        ],
        known_objections=[
            "The ROI case relies on subjective/unmeasurable benefits",
            "The implementation cost is underestimated",
            "We already have budget committed elsewhere this fiscal year",
        ],
        decision_power=0.9,
        tone="numbers-focused, skeptical of vendor enthusiasm, not impressed by a demo alone",
    ),
    StakeholderRole.CTO: StakeholderProfile(
        role=StakeholderRole.CTO,
        name="Generic CTO",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Architectural fit with the existing stack, avoiding a new island of integration debt",
            "Security, data residency, and model governance",
            "The team's ability to maintain/extend this without permanent vendor dependency",
        ],
        known_objections=[
            "How does this integrate with our existing identity/data layer?",
            "What happens to our data — is it used to train the model?",
            "We tried something similar 2 years ago and it didn't scale",
        ],
        decision_power=0.85,
        tone="technically rigorous, asks pointed implementation questions, dislikes vague answers",
    ),
    StakeholderRole.PROCUREMENT: StakeholderProfile(
        role=StakeholderRole.PROCUREMENT,
        name="Generic Procurement Lead",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Contract terms: exit clauses, SLAs, liability limits",
            "Competitive benchmark against at least 2 other vendors",
            "Compliance with internal vendor risk policy",
        ],
        known_objections=[
            "We need a competitive quote before moving forward",
            "These payment terms don't match our standard 60-day cycle",
            "Has legal already reviewed the data processing addendum?",
        ],
        decision_power=0.6,
        tone="process-oriented, will hold up progress on process grounds even when already convinced of the value",
    ),
    StakeholderRole.END_USER: StakeholderProfile(
        role=StakeholderRole.END_USER,
        name="Generic End User Representative",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Will this actually reduce my daily workload or just add one more tool",
            "Ease of adoption, minimal retraining",
            "Confidence that the results are reliable enough to act on without double-checking everything",
        ],
        known_objections=[
            "We already have too many tools — this needs to replace something, not add to the pile",
            "What happens when the AI gets it wrong?",
        ],
        decision_power=0.3,
        tone="pragmatic, cares more about day-to-day friction than the strategic narrative",
    ),
    StakeholderRole.CHAMPION: StakeholderProfile(
        role=StakeholderRole.CHAMPION,
        name="Generic Internal Champion",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Looking good internally for having found and pushed this solution",
            "Needs ammunition to defend the deal in internal meetings where the vendor isn't present",
            "Wants a quick, visible win to build momentum",
        ],
        known_objections=[
            "I believe in this, but I need a stronger answer on [X] before I take it to my CFO",
        ],
        decision_power=0.4,
        tone="favorable but pragmatic — will proactively surface OTHER stakeholders' objections",
    ),
    StakeholderRole.LEGAL_COMPLIANCE: StakeholderProfile(
        role=StakeholderRole.LEGAL_COMPLIANCE,
        name="Generic Legal/Compliance Lead",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Compliance with data privacy regulation (GDPR/LGPD/industry-specific)",
            "Intellectual property of the outputs generated by the system",
            "Liability allocation if the AI produces a harmful or incorrect output",
        ],
        known_objections=[
            "Who is liable if this system gives a customer wrong information?",
            "We need an explicit data processing agreement before any pilot with real data",
        ],
        decision_power=0.7,
        tone="formal, risk-averse, won't be rushed",
    ),
    StakeholderRole.SECURITY: StakeholderProfile(
        role=StakeholderRole.SECURITY,
        name="Generic CISO/Security Lead",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Threat model of the agentic system: prompt injection, data exfiltration, tool-calling abuse",
            "Audit logging and explainability of agent actions",
            "Compliance with internal AI usage policy",
        ],
        known_objections=[
            "What's the blast radius if one of these agents is compromised or jailbroken?",
            "Can we get a pentest report or SOC 2 before this touches production data?",
        ],
        decision_power=0.75,
        tone="adversarial by design — actively tries to find the failure mode",
    ),
    StakeholderRole.CEO: StakeholderProfile(
        role=StakeholderRole.CEO,
        name="Generic CEO",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Strategic narrative: does this become a story we can tell the board/market",
            "Competitive positioning — are we behind or ahead of peers on this",
            "Minimal personal time investment; delegates details but wants the headline",
        ],
        known_objections=[
            "Why this, why now, and why this vendor over the obvious alternatives",
        ],
        decision_power=1.0,
        tone="big-picture view, impatient with detail, decisive once convinced of the narrative",
    ),
}


def get_archetype(role: StakeholderRole) -> StakeholderProfile:
    """Return a fresh copy of the archetype for a role (never the shared singleton)."""
    return ARCHETYPES[role].model_copy(deep=True)
