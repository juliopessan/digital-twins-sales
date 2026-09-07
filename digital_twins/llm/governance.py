"""
Token-economy gate for every LLM call, backed by Tollgate
(https://github.com/juliopessan/toolgate) — a deterministic pre-call
admission gate plus an auditable "waste ledger" recording what was
admitted, rejected, and why, per session/artifact.

This wraps an existing LLMClient without changing its interface, so
orchestration/graph.py is the only caller that needs to know it exists.
It fails open: if Tollgate isn't installed, or any call into it raises,
the wrapped client is used ungated and a warning is logged — matching the
"a missed safeguard is better than a crashed debate" pattern already used
by digital_twins/i18n.py's translation safety net. A token-economy layer
must never be the reason a sales rep's rehearsal fails.

Tiers are assigned per calling role (persona/facilitator/synthesizer)
rather than through a bespoke complexity scorer — this project doesn't
send file/repo context the way Tollgate's primary use case does, so its
input-token caps are sized off our own existing max_tokens_* budgets in
config.py (see _ROLE_TIER below), not computed per request.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from digital_twins.llm.client import LLMClient

logger = logging.getLogger(__name__)

_DB_PATH = Path(os.getenv("TOLLGATE_DB", "~/.digital-twins/tollgate.db")).expanduser()

# One tier per node role. Budgets are input/output token caps, not a
# request-by-request score — persona turns are short and frequent
# (max_tokens_persona_turn=700, config.py), the facilitator's decision is
# similarly small, and the synthesizer reads the whole transcript so it
# gets the widest input cap.
_ROLE_TIER = {
    "persona": "daylight",
    "facilitator": "horizon",
    "synthesizer": "starlight",
}

# Tollgate's runtime contract is "no score, no call" — every envelope needs
# a complexity_score, even though we're picking the tier directly rather
# than computing one per request (see module docstring). These are fixed
# midpoints of each tier's documented score band (config/tollgate-dispatch.yaml:
# Daylight 16-30, Horizon 31-45, Starlight 61-80), kept consistent with the
# tier above rather than a free-standing number.
_ROLE_SCORE = {
    "persona": 23.0,
    "facilitator": 38.0,
    "synthesizer": 70.0,
}


# Fallback for a packaging bug in the current tollgate release: its
# pyproject.toml has no package_data/MANIFEST.in entry for the .sql
# migration files, so `pip install` (including straight from the git URL
# in requirements.txt) silently drops them, and WasteLedger.migrate()
# raises FileNotFoundError looking for a migrations/ directory that was
# never installed. This is the exact schema from
# tollgate/governance/store/migrations/002_waste_ledger.sql in the
# project's own source tree — applied only when the packaged file is
# missing, so a future fixed release just uses its own migration instead.
_WASTE_LEDGER_SCHEMA_FALLBACK = """\
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tollgate_sessions (
    session_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    budget_usd REAL,
    spent_usd REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS waste_ledger_events (
    event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    session_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    gate TEXT NOT NULL,
    decision TEXT NOT NULL,
    complexity_score REAL,
    tier TEXT,
    provider TEXT,
    model TEXT,
    tokens_candidate INTEGER NOT NULL DEFAULT 0,
    tokens_admitted INTEGER NOT NULL DEFAULT 0,
    tokens_transmitted INTEGER NOT NULL DEFAULT 0,
    tokens_rejected INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0,
    actual_cost_usd REAL,
    artifact_budget_usd REAL,
    session_budget_usd REAL,
    recompress_attempt INTEGER NOT NULL DEFAULT 0,
    quality_status TEXT,
    evidence_basis TEXT NOT NULL DEFAULT 'estimated',
    reason_code TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (session_id) REFERENCES tollgate_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_waste_ledger_session_time
    ON waste_ledger_events(session_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_waste_ledger_artifact_time
    ON waste_ledger_events(artifact_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_waste_ledger_gate_decision
    ON waste_ledger_events(gate, decision);
"""


def _migrate_with_fallback(ledger) -> None:
    try:
        ledger.migrate()
    except FileNotFoundError:
        logger.warning(
            "Tollgate's packaged migration file is missing (known packaging gap — "
            "see governance.py); applying the schema directly instead."
        )
        with ledger.connect() as connection:
            connection.executescript(_WASTE_LEDGER_SCHEMA_FALLBACK)


def _policies() -> dict:
    from tollgate.governance.runtime.guardian import TierPolicy

    return {
        "solar": TierPolicy("solar", 0, 0, 0),
        "daylight": TierPolicy("daylight", 6_000, 2_000, 2),
        "horizon": TierPolicy("horizon", 10_000, 3_000, 2),
        "twilight": TierPolicy("twilight", 16_000, 4_000, 2),
        "starlight": TierPolicy("starlight", 40_000, 16_000, 2),
        "aurora": TierPolicy("aurora", 80_000, 16_000, 2),
    }


class GovernedLLMClient(LLMClient):
    """Gates `inner`'s calls through a Tollgate Guardian and logs them to
    the waste ledger. `role` selects the tier (see _ROLE_TIER); calls with
    an unrecognized role get the most permissive tier rather than being
    blocked outright — the gate should never invent a new failure mode."""

    def __init__(self, inner: LLMClient, role: str, session_id: str) -> None:
        self._inner = inner
        self._role = role
        self._session_id = session_id
        self._guardian = None
        self._estimate_tokens = None
        try:
            from tollgate.context.tokens import estimate_tokens
            from tollgate.governance.runtime.guardian import Guardian
            from tollgate.governance.store.waste_ledger import WasteLedger

            _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            ledger = WasteLedger(_DB_PATH)
            _migrate_with_fallback(ledger)
            self._guardian = Guardian(ledger, _policies(), estimate_tokens)
            self._estimate_tokens = estimate_tokens
        except Exception as exc:  # pragma: no cover - depends on optional dep
            logger.warning("Tollgate unavailable; running the %s node ungated (%s)", role, exc)

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        if self._guardian is None or self._estimate_tokens is None:
            return self._inner.complete(system=system, user=user, model=model, max_tokens=max_tokens, json_mode=json_mode)

        from tollgate.governance.runtime.guardian import CallEnvelope

        payload = f"{system}\n\n{user}"
        envelope = CallEnvelope(
            session_id=self._session_id,
            project_id="digital-twins-sales",
            artifact_id=f"{self._role}-{uuid.uuid4().hex[:8]}",
            payload=payload,
            candidate_tokens=self._estimate_tokens(payload),
            complexity_score=_ROLE_SCORE.get(self._role, 85.0),
            tier=_ROLE_TIER.get(self._role, "aurora"),
            provider=type(self._inner).__name__,
            model=model,
            estimated_cost_usd=0.0,
        )

        try:
            result = self._guardian.enforce(envelope)
        except Exception as exc:  # noqa: BLE001 - see module docstring: never block a debate
            logger.warning("Tollgate did not admit a %s call, running ungated (%s)", self._role, exc)
            return self._inner.complete(system=system, user=user, model=model, max_tokens=max_tokens, json_mode=json_mode)

        text = self._inner.complete(
            system=system, user=user, model=model, max_tokens=max_tokens, json_mode=json_mode
        )
        try:
            self._guardian.record_completion(
                result,
                actual_cost_usd=0.0,
                output_tokens=self._estimate_tokens(text),
                quality_status="ok",
            )
        except Exception as exc:  # pragma: no cover - audit failures must not break the debate
            logger.warning("Tollgate audit write failed for a %s call (%s)", self._role, exc)
        return text


def with_role(llm: LLMClient, role: str, session_id: str) -> LLMClient:
    """Wrap `llm` for one node role within one debate session."""
    return GovernedLLMClient(llm, role, session_id)
