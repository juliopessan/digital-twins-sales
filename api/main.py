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
from digital_twins.research import ResearchError, research_committee, research_stakeholder

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
    provider: str = "anthropic"  # "anthropic" | "deepseek"
    max_rounds: int = 3


@app.post("/api/runs")
def create_run(payload: RunRequest) -> dict:
    if payload.provider not in ("anthropic", "deepseek"):
        raise HTTPException(400, f"Unknown provider '{payload.provider}'.")
    if not payload.api_key.strip():
        raise HTTPException(400, f"Please provide the {payload.provider.title()} API key.")
    run_id = start_run(payload.account, payload.api_key, payload.max_rounds, payload.provider)
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



# ---------------------------------------------------------------------------
# Opening-pitch suggestion
# ---------------------------------------------------------------------------

class PitchRequest(BaseModel):
    account: AccountContext
    api_key: str
    provider: str = "anthropic"


@app.post("/api/pitch")
def suggest_pitch(payload: PitchRequest) -> dict:
    """Draft an opening statement from the account's pitch and committee, as
    a starting point the seller edits before running the simulation."""
    from digital_twins.config import settings
    from digital_twins.llm.client import build_default_client
    from digital_twins.models import StakeholderRole

    if payload.provider not in ("anthropic", "deepseek"):
        raise HTTPException(400, f"Unknown provider '{payload.provider}'.")
    if not payload.api_key.strip():
        raise HTTPException(400, f"Please provide the {payload.provider.title()} API key.")

    account = payload.account
    committee = ", ".join(
        r.value.replace("_", " ").upper() if r in (StakeholderRole.CEO, StakeholderRole.CTO, StakeholderRole.CFO)
        else r.value.replace("_", " ").title()
        for r in account.roles_in_committee
    )
    model = settings.deepseek_model if payload.provider == "deepseek" else settings.persona_model
    try:
        llm = build_default_client(api_key=payload.api_key.strip(), provider=payload.provider)
        text = llm.complete(
            system=(
                "You are a B2B sales coach. Write a natural, focused, persuasive opening "
                "pitch in English, spoken in first person by the seller. No markdown, "
                "headings, or lists."
            ),
            user=(
                f"Write a ~90-second opening pitch for {account.account_name}.\n"
                f"Deal stage: {account.deal_stage}\n"
                f"Problem/pitch: {account.pitch_summary}\n"
                f"Proposed solution: {account.proposed_solution}\n"
                f"Buying committee in the room: {committee}\n"
                "Anticipate what this committee will care about, and include the value, "
                "the differentiator, and a concrete next step."
            ),
            model=model,
            max_tokens=1500,
        )
    except Exception as exc:  # noqa: BLE001 - surface provider errors to the UI
        raise HTTPException(502, f"Could not generate the pitch: {exc}") from exc
    return {"pitch": text.strip()}


# ---------------------------------------------------------------------------
# Committee mapping (EXA, all roles at once)
# ---------------------------------------------------------------------------

class CommitteeMember(BaseModel):
    role: str
    role_label: str
    name: str | None = None


class CommitteeResearchRequest(BaseModel):
    company: str
    members: list[CommitteeMember]
    exa_api_key: str


@app.post("/api/research/committee")
def research_committee_endpoint(payload: CommitteeResearchRequest) -> dict:
    """Research every committee role in parallel so the seller can review the
    facts (with sources) before any of them is injected into a persona."""
    from digital_twins.models import StakeholderRole

    if not payload.exa_api_key.strip():
        raise HTTPException(400, "Please provide the EXA API key.")
    if not payload.company.strip():
        raise HTTPException(400, "Company name is required.")
    if not payload.members or len(payload.members) > 8:
        raise HTTPException(400, "Provide between 1 and 8 committee members.")

    people = []
    for m in payload.members:
        try:
            role = StakeholderRole(m.role)
        except ValueError:
            raise HTTPException(400, f"Unknown role '{m.role}'.") from None
        if role == StakeholderRole.SALESMAN:
            raise HTTPException(400, "The salesperson isn't part of the buying committee.")
        people.append((role.value, m.role_label[:60], (m.name or "").strip()[:120] or None))

    outcome = research_committee(payload.company.strip(), people, payload.exa_api_key.strip())
    results = []
    for role, res in outcome.items():
        if isinstance(res, ResearchError):
            results.append({"role": role, "name": "", "facts": [], "sources": [], "error": str(res)})
        else:
            results.append({"role": role, "name": res.name, "facts": res.facts, "sources": res.sources, "error": None})
    return {"results": results}
