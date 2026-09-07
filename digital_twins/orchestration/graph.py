"""
Graph assembly.

Topology (hierarchical supervisor pattern):

    START
      |
      v
  [start_round]  <---------------------------+   (Facilitator: sets speaking_order)
      |                                       |
      v                                       |
  [persona_turn] --(more in order?)--+        |
      ^                              |        |
      +------------------------------+        |
      | (round_complete)                      |
      v                                       |
  [evaluate_round]  (Facilitator judges round) |
      |                                       |
      +--(continue/escalate)------------------+
      |
      +--(conclude)--> [synthesize] --> END

start_round and evaluate_round are both "the Facilitator" — they're split
into two functions because LangGraph nodes are single-purpose, but
conceptually they're one supervisor making two kinds of decisions
(who speaks, and whether the round resolved anything).
"""
from __future__ import annotations

import uuid

from langgraph.graph import StateGraph, START, END

from digital_twins.agents.facilitator import (
    make_evaluate_round_node,
    route_after_evaluation,
    start_round,
)
from digital_twins.agents.persona_agent import make_persona_turn_node, more_personas_left
from digital_twins.agents.synthesizer import make_synthesize_node
from digital_twins.llm.client import LLMClient
from digital_twins.llm.governance import with_role
from digital_twins.orchestration.state import BoardState


def build_board_graph(llm: LLMClient, feedback_block: str = ""):
    """Assemble and compile the hierarchical debate graph for a given LLMClient.

    Every node's calls are gated through Tollgate (digital_twins/llm/governance.py)
    under one shared session id, so a debate's persona/facilitator/synthesizer
    calls all land in the same waste-ledger session for cost/audit reporting.
    """
    graph = StateGraph(BoardState)
    session_id = str(uuid.uuid4())

    graph.add_node("start_round", start_round)
    graph.add_node("persona_turn", make_persona_turn_node(with_role(llm, "persona", session_id), feedback_block))
    graph.add_node("evaluate_round", make_evaluate_round_node(with_role(llm, "facilitator", session_id)))
    graph.add_node("synthesize", make_synthesize_node(with_role(llm, "synthesizer", session_id), feedback_block))

    graph.add_edge(START, "start_round")
    graph.add_edge("start_round", "persona_turn")

    graph.add_conditional_edges(
        "persona_turn",
        more_personas_left,
        {"next_persona": "persona_turn", "round_complete": "evaluate_round"},
    )

    graph.add_conditional_edges(
        "evaluate_round",
        route_after_evaluation,
        {"next_round": "start_round", "synthesize": "synthesize"},
    )

    graph.add_edge("synthesize", END)

    return graph.compile()
