"""
FastAPI backend for the Sales Digital Twins web UI.

Wraps the existing digital_twins/ engine without changing it: this is a
thin HTTP layer over PersonaFactory, build_board_graph, reporting, and
research — the same functions the CLI and the Streamlit app already call.

Run: uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from digital_twins.models import AccountContext
from digital_twins.reporting import build_html_report, build_markdown_report
from digital_twins.research import ResearchError, research_stakeholder

from api.runner import start_run
from api.store import runs

ACCOUNTS_DIR = Path(__file__).parent.parent / "accounts"

app = FastAPI(title="Sales Digital Twins API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def _list_account_files() -> list[Path]:
    """Only files that actually parse as an AccountContext — cenarios_exemplo.json
    is a list[ScenarioSpec], not an account, and would otherwise 404 downstream."""
    files = []
    for f in sorted(ACCOUNTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                AccountContext.model_validate(data)
                files.append(f)
        except Exception:
            continue
    return files


@app.get("/api/accounts")
def list_accounts() -> list[dict]:
    out = []
    for f in _list_account_files():
        data = json.loads(f.read_text(encoding="utf-8"))
        out.append(
            {
                "id": f.stem,
                "account_name": data.get("account_name", f.stem),
                "deal_stage": data.get("deal_stage", ""),
                "deal_value_usd": data.get("deal_value_usd"),
            }
        )
    return out


@app.get("/api/accounts/{account_id}")
def get_account(account_id: str) -> dict:
    path = ACCOUNTS_DIR / f"{account_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Account '{account_id}' not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return AccountContext.model_validate(data).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    account: AccountContext
    api_key: str
    max_rounds: int = 3


@app.post("/api/runs")
def create_run(payload: RunRequest) -> dict:
    if not payload.api_key.strip():
        raise HTTPException(400, "Please provide the Anthropic API key.")
    run_id = start_run(payload.account, payload.api_key, payload.max_rounds)
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404, "Run not found.")
    return run.snapshot()


@app.get("/api/runs/{run_id}/report.md", response_class=PlainTextResponse)
def get_run_report_md(run_id: str) -> str:
    result = _require_result(run_id)
    account = AccountContext.model_validate(result["account"])
    from digital_twins.models import DebateTurn, DebateVerdict, StakeholderProfile

    personas = [StakeholderProfile.model_validate(p) for p in result["personas"]]
    transcript = [DebateTurn.model_validate(t) for t in result["transcript"]]
    verdict = DebateVerdict.model_validate(result["verdict"])
    return build_markdown_report(account, personas, transcript, verdict)


@app.get("/api/runs/{run_id}/report.html", response_class=HTMLResponse)
def get_run_report_html(run_id: str) -> str:
    result = _require_result(run_id)
    account = AccountContext.model_validate(result["account"])
    from digital_twins.models import DebateTurn, DebateVerdict, StakeholderProfile

    personas = [StakeholderProfile.model_validate(p) for p in result["personas"]]
    transcript = [DebateTurn.model_validate(t) for t in result["transcript"]]
    verdict = DebateVerdict.model_validate(result["verdict"])
    return build_html_report(account, personas, transcript, verdict)


def _require_result(run_id: str) -> dict:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404, "Run not found.")
    snap = run.snapshot()
    if snap["status"] != "done" or snap["result"] is None:
        raise HTTPException(409, "Run not finished yet.")
    return snap["result"]


# ---------------------------------------------------------------------------
# Research (EXA)
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    name: str
    role_label: str
    company: str
    exa_api_key: str


@app.post("/api/research")
def research(payload: ResearchRequest) -> dict:
    try:
        facts = research_stakeholder(
            payload.name, payload.role_label, payload.company, payload.exa_api_key
        )
    except ResearchError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"facts": facts}

