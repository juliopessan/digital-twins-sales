"""
Optional EXA-powered stakeholder research.

Used by the Streamlit manual-account form: instead of hand-typing facts
about a real stakeholder, a rep types a company + person name and this
pulls a grounded, cited answer from the web via Exa's Answer API.

This is the same "real grounding" step done manually for the iFood test
account (web search -> curated facts in real_data) — automated here so it
doesn't require a separate research pass per account.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

_SYSTEM_PROMPT = """\
Respond ONLY as a bulleted list of concise, specific, factual statements —
one fact per line, each line starting with "- ". No preamble, no concluding
remarks, no disclaimers. Each fact should be something a B2B sales rep could
use to understand this person's priorities, incentives, or recent public
statements (career history, stated strategic priorities, public statements,
prior vendor decisions, reporting line, etc). If little is publicly known,
return fewer facts rather than inventing generic ones.
"""


# Used when only a role + company are known (no name): the first line tells us
# who the person is, so the seller can confirm we grounded the right one.
_ROLE_ONLY_SYSTEM_PROMPT = """\
Identify the CURRENT person in the given role at the given company, then list
concise, specific, factual statements about them. Format strictly as:
first line "Name: <full name>" (or "Name: Unknown" if you cannot identify a
single specific person confidently), then one fact per line starting with
"- ". No preamble, no disclaimers. Prefer fewer facts over generic filler.
"""


class ResearchError(RuntimeError):
    """Raised when Exa research fails (bad key, no results, network error)."""


@dataclass
class StakeholderResearch:
    name: str = ""
    facts: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def _research(name: str | None, role_label: str, company: str, api_key: str) -> StakeholderResearch:
    try:
        from exa_py import Exa
    except ImportError as exc:
        raise ResearchError("exa_py is not installed (pip install exa_py).") from exc

    if name:
        query = f"What are recent, specific, publicly known facts about {name}, {role_label} at {company}?"
        system_prompt = _SYSTEM_PROMPT
    else:
        query = f"Who is the current {role_label} at {company}, and what are recent, specific, publicly known facts about them?"
        system_prompt = _ROLE_ONLY_SYSTEM_PROMPT

    try:
        exa = Exa(api_key=api_key)
        response = exa.answer(query, system_prompt=system_prompt)
    except Exception as exc:
        raise ResearchError(f"EXA research failed: {exc}") from exc

    raw_answer = response.answer if isinstance(response.answer, str) else str(response.answer)
    lines = [line.strip() for line in raw_answer.splitlines() if line.strip()]

    found_name = name or ""
    if not name and lines and lines[0].lower().startswith("name:"):
        candidate = lines[0].split(":", 1)[1].strip().strip("*")
        found_name = "" if candidate.lower() in ("", "unknown") else candidate
        lines = lines[1:]

    facts = [ln.lstrip("-•").strip() for ln in lines]
    facts = [f for f in facts if len(f) > 8]
    if not facts:
        who = name or role_label
        raise ResearchError(f"EXA found no public facts about '{who}' at '{company}'.")

    sources = sorted({c.url for c in response.citations if getattr(c, "url", None)})[:4]
    return StakeholderResearch(name=found_name, facts=facts, sources=sources)


def research_stakeholder(name: str, role_label: str, company: str, api_key: str) -> list[str]:
    """Returns a list of fact strings grounded by Exa's Answer API, with a
    trailing 'Sources:' line listing the cited source URLs."""
    r = _research(name, role_label, company, api_key)
    facts = list(r.facts)
    if r.sources:
        facts.append("Sources: " + ", ".join(r.sources[:3]))
    return facts


def research_committee(
    company: str, people: list[tuple[str, str, str | None]], api_key: str, max_workers: int = 4
) -> dict[str, StakeholderResearch | ResearchError]:
    """Research several roles in parallel. `people` is (role, role_label, name|None).
    One role failing never fails the batch: its slot holds the ResearchError."""

    def one(item: tuple[str, str, str | None]):
        role, label, name = item
        try:
            return role, _research(name or None, label, company, api_key)
        except ResearchError as exc:
            return role, exc

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return dict(pool.map(one, people))
