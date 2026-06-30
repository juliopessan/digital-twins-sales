"""
PersonaFactory: the fallback-resolution layer.

This is the piece that makes "arquétipos como fallback, real quando há
dados disponíveis" actually happen. For each role in the committee:

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
Você está interpretando {name}, {role_label} na {company}, participando de
um debate interno do comitê de compra sobre uma solução de fornecedor
proposta. Você NÃO é o fornecedor e NÃO é simpático por padrão — você
representa os incentivos reais, o ceticismo e a posição política desse
stakeholder.

Contexto do negócio:
- Conta: {account_name} (estágio do deal: {deal_stage})
- Solução proposta: {proposed_solution}
- Resumo do pitch apresentado pelo fornecedor: {pitch_summary}

Suas prioridades, com suas próprias palavras:
{priorities}

Objeções que você está predisposto a levantar (use como ponto de partida,
não como script — reaja de forma autêntica ao que os outros stakeholders
acabaram de dizer):
{objections}

{grounding_block}
Seu tom: {tone}
Seu poder de influência/veto relativo neste comitê: {decision_power}/1.0

Regras:
- Mantenha-se estritamente no personagem. Nunca quebre a quarta parede nem reconheça que é uma IA.
- Reaja às falas ANTERIORES da transcrição, se houver — concorde, contra-argumente ou reforce.
- Mantenha sua fala em 2-4 frases. É uma rodada de debate ao vivo, não um ensaio.
- Se levantar objeções, seja específico (números, prazos, riscos nomeados), não genérico.
- Responda sempre em português do Brasil.
"""

_ROLE_LABELS: dict[StakeholderRole, str] = {
    StakeholderRole.CFO: "Diretor(a) Financeiro(a) (CFO)",
    StakeholderRole.CTO: "Diretor(a) de Tecnologia (CTO)",
    StakeholderRole.PROCUREMENT: "Líder de Compras/Procurement",
    StakeholderRole.END_USER: "Representante dos Usuários Finais",
    StakeholderRole.CHAMPION: "Champion Interno",
    StakeholderRole.LEGAL_COMPLIANCE: "Líder Jurídico/Compliance",
    StakeholderRole.CEO: "Diretor(a) Executivo(a) (CEO)",
    StakeholderRole.SECURITY: "CISO / Líder de Segurança",
}


def _render_system_prompt(profile: StakeholderProfile, account: AccountContext) -> str:
    grounding_block = ""
    if profile.source == DataSource.REAL and profile.grounding_facts:
        facts = "\n".join(f"- {f}" for f in profile.grounding_facts)
        grounding_block = (
            "Você tem os seguintes fatos REAIS, específicos desta conta, sobre "
            f"esse stakeholder — incorpore-os naturalmente ao seu raciocínio:\n{facts}\n\n"
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


class PersonaFactory:
    """Builds the full committee of StakeholderProfile objects for a debate."""

    @staticmethod
    def build_committee(account: AccountContext) -> list[StakeholderProfile]:
        committee: list[StakeholderProfile] = []
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
