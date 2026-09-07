"""
PersonaFactory: the fallback-resolution layer.

This is the piece that makes "archetypes as fallback, real when data is
available" actually happen. For each role in the committee:

  1. Look up AccountContext.real_data[role].
  2. If it has >=1 fact, build a REAL persona grounded in those facts.
  3. Otherwise, clone the ARCHETYPE for that role.

Either way, the output is the same StakeholderProfile shape with a fully
rendered system_prompt — downstream agent code never needs to branch on
DataSource again.
"""
from __future__ import annotations

from digital_twins.models import AccountContext, DataSource, StakeholderProfile, StakeholderRole
from digital_twins.personas.archetypes import get_archetype

_BASE_INSTRUCTIONS = """\
You are playing {name}, {role_label} at {company}, participating in an
internal buying committee debate about a proposed vendor solution. You are
NOT the vendor and you are NOT friendly by default — you represent this
stakeholder's real incentives, skepticism, and political position.

Business context:
- Account: {account_name} (deal stage: {deal_stage})
- Proposed solution: {proposed_solution}
- Summary of the vendor's pitch: {pitch_summary}

Your priorities, in your own words:
{priorities}

Objections you are predisposed to raise (use as a starting point, not a
script — react authentically to what the other stakeholders just said):
{objections}

{grounding_block}
Your tone: {tone}
Your relative influence/veto power in this committee: {decision_power}/1.0

Rules:
- Stay strictly in character. Never break the fourth wall or acknowledge you are an AI.
- React to PRIOR statements in the transcript, if any — agree, counter-argue, or reinforce.
- Keep your statement to 2-4 sentences. This is a live debate round, not an essay.
- If you raise objections, be specific (numbers, timelines, named risks), not generic.
- Always respond in English.
"""

_ROLE_LABELS: dict[StakeholderRole, str] = {
    StakeholderRole.SALESMAN: "Salesperson",
    StakeholderRole.CFO: "Chief Financial Officer (CFO)",
    StakeholderRole.CTO: "Chief Technology Officer (CTO)",
    StakeholderRole.PROCUREMENT: "Procurement Lead",
    StakeholderRole.END_USER: "End User Representative",
    StakeholderRole.CHAMPION: "Internal Champion",
    StakeholderRole.LEGAL_COMPLIANCE: "Legal/Compliance Lead",
    StakeholderRole.CEO: "Chief Executive Officer (CEO)",
    StakeholderRole.SECURITY: "CISO / Security Lead",
}


def _render_system_prompt(profile: StakeholderProfile, account: AccountContext) -> str:
    grounding_block = ""
    if profile.source == DataSource.REAL and profile.grounding_facts:
        facts = "\n".join(f"- {f}" for f in profile.grounding_facts)
        grounding_block = (
            "You have the following REAL, account-specific facts about this "
            f"stakeholder — weave them naturally into your reasoning:\n{facts}\n\n"
        )

    return _BASE_INSTRUCTIONS.format(
        name=profile.name,
        role_label=_ROLE_LABELS[profile.role],
        company=profile.company or account.account_name,
        account_name=account.account_name,
        deal_stage=account.deal_stage,
        proposed_solution=account.proposed_solution,
        pitch_summary=account.pitch_summary,
        priorities="\n".join(f"- {p}" for p in profile.priorities) or "- (none specified)",
        objections="\n".join(f"- {o}" for o in profile.known_objections) or "- (none specified)",
        grounding_block=grounding_block,
        tone=profile.tone,
        decision_power=profile.decision_power,
    )


def _render_salesman_prompt(account: AccountContext) -> str:
    """Specialized prompt for the Salesman agent responding to committee objections."""
    deal_value_str = f"US$ {account.deal_value_usd:,.0f}" if account.deal_value_usd else "(not provided)"
    return f"""\
You are the SALESPERSON/REPRESENTATIVE of the proposed solution. You are
participating in an internal buying committee debate at {account.account_name}.

Deal context:
- Deal stage: {account.deal_stage}
- Solution: {account.proposed_solution}
- Estimated value: {deal_value_str}

Your mission in this debate is to:
1. Listen empathetically to the objections and concerns raised by the committee
2. Respond DIRECTLY, CONCRETELY, and CONSTRUCTIVELY with data/examples
3. Connect the solution to each stakeholder's specific incentives
4. Not be defensive, but confident in the solution's real benefits
5. If you don't know how to answer something, admit it — don't bluff

Fundamental rule: You are NOT here to win "at all costs". You are here to
help the committee make an INFORMED decision. If you identify a legitimate
objection you cannot resolve, say so.

Style rules:
- Keep it to 2-4 sentences per turn. This is a live debate, not an email.
- Always respond in English.
- Use data/numbers when possible (customer cases, market benchmarks, ROI).
- Never break the fourth wall or acknowledge you are an AI.
- You are the real SALESPERSON, with the real vulnerabilities of a deal.
"""


class PersonaFactory:
    """Builds the full committee of StakeholderProfile objects for a debate."""

    @staticmethod
    def build_committee(account: AccountContext) -> list[StakeholderProfile]:
        """
        Build the committee: SALESMAN first (opens), then other roles.
        """
        committee: list[StakeholderProfile] = []
        
        # Add SALESMAN as first speaker (always participates)
        salesman = get_archetype(StakeholderRole.SALESMAN)
        salesman.company = account.account_name
        # Salesman's system prompt is rendered differently in persona_agent.py
        salesman.system_prompt = _render_salesman_prompt(account)
        committee.append(salesman)
        
        # Add committee members in order
        for role in account.roles_in_committee:
            real_facts = account.real_data.get(role, [])
            if real_facts:
                profile = PersonaFactory._build_real(role, real_facts, account)
            else:
                profile = get_archetype(role)
                profile.company = account.account_name
            profile.system_prompt = _render_system_prompt(profile, account)
            committee.append(profile)
        return committee

    @staticmethod
    def _build_real(
        role: StakeholderRole, real_facts: list[str], account: AccountContext
    ) -> StakeholderProfile:
        """
        Build a REAL persona on top of the archetype's priors.

        Design choice: even a "real" persona inherits the archetype's
        priorities/objections/decision_power as a structural prior — what
        changes is `grounding_facts`, which gets injected into the prompt
        and should dominate the archetype's generic assumptions. This
        avoids needing a fully separate real-persona schema, and means a
        partially-known stakeholder (e.g. you know their LinkedIn title but
        nothing else) still degrades gracefully instead of producing an
        empty persona.
        """
        base = get_archetype(role)
        base.source = DataSource.REAL
        base.company = account.account_name
        base.grounding_facts = real_facts
        real_name = account.real_names.get(role)
        if real_name:
            base.name = real_name
        return base
