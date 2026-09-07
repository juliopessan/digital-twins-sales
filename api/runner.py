"""
Runs a debate in a background thread, pushing start/done events into a
RunState so the API can be polled for progress — same event shape as the
archived legacy/streamlit_app.py's _run_debate_with_events, decoupled from
any UI framework.
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


def start_run(account: AccountContext, api_key: str, max_rounds: int, provider: str = "anthropic") -> str:
    run = runs.create()
    thread = threading.Thread(
        target=_execute, args=(run, account, api_key, max_rounds, provider), daemon=True
    )
    thread.start()
    return run.run_id


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

        run.append_event({"event": "start", "agent": FACILITATOR_KEY})
        for step in app.stream(initial_state, stream_mode="updates"):
            for node_name, update in step.items():
                if node_name == "start_round":
                    llm_calls += 0  # heuristic, deterministic reorder — no LLM call
                    run.append_event({"event": "done", "agent": FACILITATOR_KEY})
                    speaking_order = update.get("speaking_order", [])
                    next_idx = 0
                    if speaking_order:
                        run.append_event({"event": "start", "agent": speaking_order[0]})
                elif node_name == "persona_turn":
                    llm_calls += 1
                    turn = update["transcript"][0]
                    transcript.append(turn)
                    run.append_event({"event": "done", "agent": turn.role.value})
                    next_idx += 1
                    if next_idx < len(speaking_order):
                        run.append_event({"event": "start", "agent": speaking_order[next_idx]})
                    else:
                        run.append_event({"event": "start", "agent": FACILITATOR_KEY})
                elif node_name == "evaluate_round":
                    llm_calls += 1
                    run.append_event({"event": "done", "agent": FACILITATOR_KEY})
                    if update.get("facilitator_decision") == "conclude":
                        run.append_event({"event": "start", "agent": SYNTHESIZER_KEY})
                    else:
                        run.append_event({"event": "start", "agent": FACILITATOR_KEY})
                elif node_name == "synthesize":
                    llm_calls += 1
                    verdict = update["verdict"]
                    run.append_event({"event": "done", "agent": SYNTHESIZER_KEY})

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
