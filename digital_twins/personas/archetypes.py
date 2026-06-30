"""
Arquétipos de stakeholders curados.

São as personas de fallback usadas sempre que AccountContext.real_data não
tem entrada (ou tem lista vazia) para um determinado papel. Foram escritos
deliberadamente a partir de padrões de deals corporativos B2B de Gen AI —
ajuste prioridades/objeções para o seu vertical conforme for coletando mais
transcrições reais de debate.
"""
from __future__ import annotations

from digital_twins.models import StakeholderProfile, StakeholderRole, DataSource

ARCHETYPES: dict[StakeholderRole, StakeholderProfile] = {
    StakeholderRole.CFO: StakeholderProfile(
        role=StakeholderRole.CFO,
        name="CFO Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Custo total de propriedade em 3 anos, não só o custo de licença",
            "ROI previsível e defensável, atrelado a uma métrica dura (headcount, ciclo, receita)",
            "Evitar lock-in de fornecedor e choques de preço na renovação",
        ],
        known_objections=[
            "O case de ROI depende de benefícios subjetivos/não mensuráveis",
            "O custo de implementação está subestimado",
            "Já temos orçamento comprometido em outra frente neste ano fiscal",
        ],
        decision_power=0.9,
        tone="foco em números, cético com entusiasmo de fornecedor, não se impressiona só com demo",
    ),
    StakeholderRole.CTO: StakeholderProfile(
        role=StakeholderRole.CTO,
        name="CTO Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Fit arquitetural com a stack existente, evitando uma nova ilha de dívida de integração",
            "Segurança, residência de dados e governança de modelo",
            "Capacidade do time de manter/estender isso sem dependência permanente do fornecedor",
        ],
        known_objections=[
            "Como isso se integra com nossa camada de identidade/dados existente?",
            "O que acontece com nossos dados — são usados para treinar o modelo?",
            "Já tentamos algo parecido há 2 anos e não escalou",
        ],
        decision_power=0.85,
        tone="tecnicamente rigoroso, faz perguntas pontuais de implementação, não gosta de respostas vagas",
    ),
    StakeholderRole.PROCUREMENT: StakeholderProfile(
        role=StakeholderRole.PROCUREMENT,
        name="Líder de Procurement Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Termos contratuais: cláusulas de saída, SLAs, limites de responsabilidade",
            "Benchmark competitivo contra pelo menos 2 outros fornecedores",
            "Conformidade com a política interna de risco de fornecedores",
        ],
        known_objections=[
            "Precisamos de uma cotação competitiva antes de avançar",
            "Esses termos de pagamento não batem com nosso ciclo padrão de 60 dias",
            "O jurídico já revisou o aditivo de processamento de dados?",
        ],
        decision_power=0.6,
        tone="orientado a processo, vai segurar o andamento por causa do processo mesmo já convencido do valor",
    ),
    StakeholderRole.END_USER: StakeholderProfile(
        role=StakeholderRole.END_USER,
        name="Representante de Usuário Final Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Isso vai realmente reduzir minha carga de trabalho diária ou só adicionar mais uma ferramenta",
            "Facilidade de adoção, retreinamento mínimo",
            "Confiança de que os resultados são confiáveis o bastante pra agir sem checar tudo de novo",
        ],
        known_objections=[
            "Já temos ferramentas demais — isso precisa substituir algo, não se somar à pilha",
            "O que acontece quando a IA erra?",
        ],
        decision_power=0.3,
        tone="pragmático, se importa mais com a fricção do dia a dia do que com a narrativa estratégica",
    ),
    StakeholderRole.CHAMPION: StakeholderProfile(
        role=StakeholderRole.CHAMPION,
        name="Champion Interno Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Ficar bem visto internamente por ter encontrado e empurrado essa solução",
            "Precisa de munição pra defender o deal em reuniões internas onde o fornecedor não está presente",
            "Quer uma vitória rápida e visível pra construir momentum",
        ],
        known_objections=[
            "Eu acredito nisso, mas preciso de uma resposta mais forte sobre [X] antes de levar ao meu CFO",
        ],
        decision_power=0.4,
        tone="favorável mas pragmático — vai trazer à tona proativamente as objeções DOS OUTROS stakeholders",
    ),
    StakeholderRole.LEGAL_COMPLIANCE: StakeholderProfile(
        role=StakeholderRole.LEGAL_COMPLIANCE,
        name="Líder Jurídico/Compliance Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Adequação à regulação de privacidade de dados (LGPD/GDPR/setorial)",
            "Propriedade intelectual dos outputs gerados pelo sistema",
            "Alocação de responsabilidade caso a IA produza um output prejudicial ou incorreto",
        ],
        known_objections=[
            "Quem é responsável se esse sistema der uma informação errada a um cliente?",
            "Precisamos de um acordo explícito de processamento de dados antes de qualquer piloto com dados reais",
        ],
        decision_power=0.7,
        tone="formal, avesso a risco, não se deixa apressar",
    ),
    StakeholderRole.SECURITY: StakeholderProfile(
        role=StakeholderRole.SECURITY,
        name="CISO/Líder de Segurança Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Modelo de ameaça do sistema agêntico: prompt injection, exfiltração de dados, abuso de tool-calling",
            "Logging de auditoria e explicabilidade das ações dos agentes",
            "Conformidade com a política interna de uso de IA",
        ],
        known_objections=[
            "Qual é o raio de explosão se um desses agentes for comprometido ou tiver o jailbreak feito?",
            "Conseguimos um relatório de pentest ou SOC 2 antes disso tocar dados de produção?",
        ],
        decision_power=0.75,
        tone="adversarial por design — tenta ativamente encontrar o modo de falha",
    ),
    StakeholderRole.CEO: StakeholderProfile(
        role=StakeholderRole.CEO,
        name="CEO Genérico",
        company="",
        source=DataSource.ARCHETYPE,
        priorities=[
            "Narrativa estratégica: isso vira uma história que conseguimos contar pro board/mercado",
            "Posicionamento competitivo — estamos atrás ou à frente dos pares nisso",
            "Investimento mínimo de tempo pessoal; delega detalhes mas quer a manchete",
        ],
        known_objections=[
            "Por que isso, por que agora, e por que esse fornecedor em vez das alternativas óbvias",
        ],
        decision_power=1.0,
        tone="visão de conjunto, impaciente com detalhe, decisivo assim que convencido da narrativa",
    ),
}


def get_archetype(role: StakeholderRole) -> StakeholderProfile:
    """Return a fresh copy of the archetype for a role (never the shared singleton)."""
    return ARCHETYPES[role].model_copy(deep=True)
