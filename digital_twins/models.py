"""
Domain models for the Sales Digital Twins system.

Design intent
-------------
Everything that flows through the LangGraph state graph is a Pydantic v2
model. This buys us: (1) validation at every node boundary, so a malformed
LLM response fails loudly instead of corrupting downstream state, and
(2) free JSON schemas if/when this gets exposed behind an API.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StakeholderRole(str, Enum):
    """Canonical buying-committee roles. Extend as needed per industry."""

    SALESMAN = "salesman"  # Sales representative — participates as active responder to objections
    CFO = "cfo"
    CTO = "cto"
    PROCUREMENT = "procurement"
    END_USER = "end_user"
    CHAMPION = "champion"
    LEGAL_COMPLIANCE = "legal_compliance"
    CEO = "ceo"
    SECURITY = "security"


class DataSource(str, Enum):
    """Where a persona's grounding facts came from."""

    REAL = "real"          # grounded in actual account data (CRM, call transcripts, LinkedIn, email)
    ARCHETYPE = "archetype"  # generic fallback persona, no account-specific data available


class Sentiment(str, Enum):
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    SKEPTICAL = "skeptical"
    BLOCKING = "blocking"


class StakeholderProfile(BaseModel):
    """A single stakeholder digital twin definition.

    Built by PersonaFactory, which decides per-role whether to ground this
    in real account data (DataSource.REAL) or fall back to a curated
    archetype (DataSource.ARCHETYPE). The persona agent never knows or
    cares which one it got — it just consumes `system_prompt`.
    """

    role: StakeholderRole
    name: str
    company: str
    source: DataSource
    priorities: list[str] = Field(default_factory=list)
    known_objections: list[str] = Field(default_factory=list)
    decision_power: float = Field(
        ge=0.0, le=1.0, default=0.5,
        description="Relative veto/influence weight in the buying committee (0=no say, 1=hard veto)",
    )
    tone: str = "neutral"
    grounding_facts: list[str] = Field(
        default_factory=list,
        description="Verbatim facts pulled from CRM/LinkedIn/email/call transcripts when source=REAL",
    )
    system_prompt: Optional[str] = Field(
        default=None, description="Fully rendered persona system prompt; filled by PersonaFactory"
    )


class AccountContext(BaseModel):
    """Everything known about the deal/account being rehearsed against."""

    account_name: str
    deal_stage: str
    pitch_summary: str
    proposed_solution: str
    deal_value_usd: Optional[float] = None
    seller_opening: Optional[str] = Field(
        default=None,
        description=(
            "Fala de abertura real do vendedor (o pitch como ele vai/foi dito, "
            "com as palavras dele). Se presente, as personas reagem diretamente "
            "a estas palavras em vez de apenas ao pitch_summary abstrato. Em "
            "branco, o comitê roda de forma autônoma (war-gaming)."
        ),
    )
    real_data: dict[StakeholderRole, list[str]] = Field(
        default_factory=dict,
        description=(
            "Raw facts per role sourced from CRM/transcripts/LinkedIn. "
            "If a role key is absent or its list is empty, PersonaFactory "
            "falls back to the archetype for that role."
        ),
    )
    real_names: dict[StakeholderRole, str] = Field(
        default_factory=dict,
        description=(
            "Optional real person name per role (e.g. 'Diego Barreto' for CEO). "
            "Only used when the role also has real_data; otherwise the archetype's "
            "generic name (e.g. 'Generic CEO') is used."
        ),
    )
    roles_in_committee: list[StakeholderRole] = Field(
        default_factory=lambda: [
            StakeholderRole.CHAMPION,
            StakeholderRole.CTO,
            StakeholderRole.CFO,
            StakeholderRole.PROCUREMENT,
        ],
        description="Which roles sit on this deal's buying committee, and base speaking order.",
    )


class DebateTurn(BaseModel):
    round_number: int
    role: StakeholderRole
    name: str
    statement: str
    objections_raised: list[str] = Field(default_factory=list)
    sentiment: Sentiment


class SellerCoaching(BaseModel):
    """Feedback do Coach sobre a fala de abertura do vendedor.

    Só é preenchido quando AccountContext.seller_opening existe — o Coach
    avalia como o pitch real do vendedor se sustentou diante das objeções
    levantadas no debate (não avalia o comitê, avalia a PESSOA)."""

    pitch_grade: str  # nota curta e honesta, ex: "C+ — forte em ROI, fraco em governança"
    what_landed: list[str] = Field(default_factory=list)
    what_backfired: list[str] = Field(default_factory=list)
    rewrite_suggestions: list[str] = Field(default_factory=list)


class DebateVerdict(BaseModel):
    consensus_reached: bool
    overall_sentiment: Sentiment
    top_objections: list[str]
    blocking_stakeholders: list[StakeholderRole]
    recommended_talk_track: list[str]
    risk_summary: str
    meddpicc_scorecard: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Avaliação tática das dimensões MEDDPICC observáveis no debate "
            "(ex: Metrics, Economic Buyer, Identify Pain, Champion) -> texto "
            "de avaliação. Dimensões que o debate não revelou ficam de fora."
        ),
    )
    seller_coaching: Optional[SellerCoaching] = Field(
        default=None,
        description=(
            "Feedback do Coach sobre a fala de abertura do vendedor. Só "
            "preenchido quando o vendedor forneceu uma fala de abertura "
            "(AccountContext.seller_opening); caso contrário fica None."
        ),
    )


class SimulationRecord(BaseModel):
    """Snapshot serializável de uma simulação completa.

    É o que o CLI salva em reports/<slug>-<ts>.json e o que a calibração
    pós-call (digital_twins.calibration) consome para comparar o que o twin
    PREVIU com o que a call real de fato trouxe — o loop "twin vs realidade"
    do Vertex/Foundry aplicado a vendas.
    """

    created_at: str
    account: AccountContext
    transcript: list[DebateTurn] = Field(default_factory=list)
    verdict: DebateVerdict
