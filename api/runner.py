"""
Runs a debate in a background thread, pushing rich progress events into a
RunState so the API can be polled and the frontend can narrate the debate
turn by turn instead of showing a bare, repeating list of agent names.

Each event carries enough state to render a story on its own — phase,
round number, a statement preview, sentiment, the facilitator's own
reasoning, and a server-computed progress fraction — so the frontend never
has to reverse-engineer round/phase from a flat start/done agent log.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timezone

from digital_twins.config import settings
from digital_twins.constants import FACILITATOR_KEY, SYNTHESIZER_KEY
from digital_twins.llm.client import build_default_client
from digital_twins.models import AccountContext, DebateVerdict, StakeholderProfile
from digital_twins.orchestration.graph import build_board_graph

from api.store import RunState, runs

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _preview(text: str, limit: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def start_run(account: AccountContext, api_key: str, max_rounds: int, provider: str = "anthropic") -> str:
    run = runs.create(max_rounds=max_rounds)
    thread = threading.Thread(
        target=_execute, args=(run, account, api_key, max_rounds, provider), daemon=True
    )
    thread.start()
    return run.run_id


class _Progress:
    """Server-computed progress fraction, so the frontend never has to guess.

    Budgeted in "units": each round costs (ordering + one per speaker +
    evaluating); synthesis costs 2 more at the very end. If the facilitator
    concludes before max_rounds, the bar simply jumps ahead on synthesis
    rather than crawling — treated as a feature, not a bug: it's honest
    about not knowing the round count in advance.
    """

    def __init__(self, max_rounds: int, committee_size: int) -> None:
        self.total = max(max_rounds * (committee_size + 2) + 2, 1)
        self.done = 0

    def step(self) -> float:
        self.done += 1
        return min(self.done / self.total, 0.98)


def _execute(
    run: RunState, account: AccountContext, api_key: str, max_rounds: int, provider: str = "anthropic"
) -> None:
    from digital_twins.personas.resolver import PersonaFactory

    if provider == "deepseek":
        model_persona = model_facilitator = model_synthesizer = settings.deepseek_model
    else:
        model_persona = settings.persona_model
        model_facilitator = settings.facilitator_model
        model_synthesizer = settings.synthesizer_model

    t0 = time.monotonic()
    llm_calls = 0
    try:
        personas: list[StakeholderProfile] = PersonaFactory.build_committee(account)
        llm = build_default_client(api_key=api_key, provider=provider)
        app = build_board_graph(llm)
        progress = _Progress(max_rounds, len(personas))

        def emit(event: str, agent: str, phase: str, round_number: int, **extra) -> None:
            run.append_event(
                {
                    "event": event,
                    "agent": agent,
                    "phase": phase,
                    "round": round_number,
                    "progress": progress.step() if event == "done" else min(progress.done / progress.total, 0.98),
                    **extra,
                }
            )

        initial_state = {
            "account": account,
            "personas": personas,
            "round_number": 0,
            "max_rounds": max_rounds,
            "transcript": [],
            "current_index": 0,
            "speaking_order": [],
            "facilitator_decision": "continue",
            "model_persona": model_persona,
            "model_facilitator": model_facilitator,
            "model_synthesizer": model_synthesizer,
        }

        transcript: list = []
        verdict: DebateVerdict | None = None
        speaking_order: list[str] = []
        next_idx = 0
        round_number = 0

        emit("start", FACILITATOR_KEY, "ordering", round_number + 1)
        for step in app.stream(initial_state, stream_mode="updates"):
            for node_name, update in step.items():
                if node_name == "start_round":
                    llm_calls += 0  # heuristic, deterministic reorder — no LLM call
                    round_number = update.get("round_number", round_number + 1)
                    emit("done", FACILITATOR_KEY, "ordering", round_number)
                    speaking_order = update.get("speaking_order", [])
                    next_idx = 0
                    if speaking_order:
                        emit("start", speaking_order[0], "speaking", round_number)
                elif node_name == "persona_turn":
                    llm_calls += 1
                    turn = update["transcript"][0]
                    transcript.append(turn)
                    emit(
                        "done",
                        turn.role.value,
                        "speaking",
                        round_number,
                        sentiment=turn.sentiment.value,
                        preview=_preview(turn.statement),
                        objections=len(turn.objections_raised),
                    )
                    next_idx += 1
                    if next_idx < len(speaking_order):
                        emit("start", speaking_order[next_idx], "speaking", round_number)
                    else:
                        emit("start", FACILITATOR_KEY, "evaluating", round_number)
                elif node_name == "evaluate_round":
                    llm_calls += 1
                    decision = update.get("facilitator_decision", "continue")
                    emit(
                        "done",
                        FACILITATOR_KEY,
                        "evaluating",
                        round_number,
                        decision=decision,
                        reasoning=_preview(update.get("facilitator_reasoning", ""), 120),
                    )
                    if decision == "conclude":
                        emit("start", SYNTHESIZER_KEY, "synthesizing", round_number)
                    else:
                        emit("start", FACILITATOR_KEY, "ordering", round_number + 1)
                elif node_name == "synthesize":
                    llm_calls += 1
                    verdict = update["verdict"]
                    emit("done", SYNTHESIZER_KEY, "synthesizing", round_number)

        duration_seconds = round(time.monotonic() - t0, 1)
        with run.lock:
            run.result = {
                "account": account.model_dump(mode="json"),
                "personas": [p.model_dump(mode="json") for p in personas],
                "transcript": [t.model_dump(mode="json") for t in transcript],
                "verdict": verdict.model_dump(mode="json") if verdict else None,
                "duration_seconds": duration_seconds,
                "llm_calls": llm_calls,
                "model_persona": model_persona,
                "model_facilitator": model_facilitator,
                "model_synthesizer": model_synthesizer,
                "slug": slugify(account.account_name),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            run.status = "done"
            run.finished_at = run.result["finished_at"]
    except Exception as exc:
        logger.exception("Run %s failed", run.run_id)
        with run.lock:
            run.status = "error"
            run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc).isoformat()
