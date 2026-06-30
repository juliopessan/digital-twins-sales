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

from langgraph.graph import StateGraph, START, END

from digital_twins.agents.facilitator import (
    make_evaluate_round_node,
    route_after_evaluation,
    start_round,
)
from digital_twins.agents.persona_agent import make_persona_turn_node, more_personas_left
from digital_twins.agents.synthesizer import make_synthesize_node
from digital_twins.llm.client import LLMClient
from digital_twins.orchestration.state import BoardState


def build_board_graph(llm: LLMClient):
    """Assemble and compile the hierarchical debate graph for a given LLMClient."""
    graph = StateGraph(BoardState)

    graph.add_node("start_round", start_round)
    graph.add_node("persona_turn", make_persona_turn_node(llm))
    graph.add_node("evaluate_round", make_evaluate_round_node(llm))
    graph.add_node("synthesize", make_synthesize_node(llm))

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
