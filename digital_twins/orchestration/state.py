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

    transcript: Annotated[list[DebateTurn], operator.add]

    speaking_order: list[str]   # StakeholderRole values, this round's order
    current_index: int          # whose turn it is within speaking_order

    facilitator_decision: str   # "continue" | "escalate" | "conclude"
    facilitator_reasoning: str

    verdict: DebateVerdict | None
