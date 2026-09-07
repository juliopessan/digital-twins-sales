"""
LangGraph state definition.

`transcript` uses `operator.add` as its reducer — every node that appends
turns just returns `{"transcript": [new_turn]}` and LangGraph concatenates
it onto the running list automatically. This is the standard LangGraph
pattern for accumulating history across nodes without each node having to
read-modify-write the full list.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from digital_twins.models import AccountContext, DebateTurn, DebateVerdict, StakeholderProfile


class BoardState(TypedDict, total=False):
    account: AccountContext
    personas: list[StakeholderProfile]

    round_number: int
    max_rounds: int

    # Per-run model override (set by callers that support multiple LLM
    # providers, e.g. api/runner.py). Falls back to config.settings.*_model
    # when absent — CLI and the legacy Streamlit apps never set these.
    model_persona: str
    model_facilitator: str
    model_synthesizer: str

    transcript: Annotated[list[DebateTurn], operator.add]

    speaking_order: list[str]   # StakeholderRole values, this round's order
    current_index: int          # whose turn it is within speaking_order

    facilitator_decision: str   # "continue" | "escalate" | "conclude"
    facilitator_reasoning: str

    verdict: DebateVerdict | None
