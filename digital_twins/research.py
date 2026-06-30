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

_SYSTEM_PROMPT = """\
Respond ONLY as a bulleted list of concise, specific, factual statements —
one fact per line, each line starting with "- ". No preamble, no concluding
remarks, no disclaimers. Each fact should be something a B2B sales rep could
use to understand this person's priorities, incentives, or recent public
statements (career history, stated strategic priorities, public statements,
prior vendor decisions, reporting line, etc). If little is publicly known,
return fewer facts rather than inventing generic ones.
"""


class ResearchError(RuntimeError):
    """Raised when Exa research fails (bad key, no results, network error)."""


def research_stakeholder(name: str, role_label: str, company: str, api_key: str) -> list[str]:
    """Returns a list of fact strings grounded by Exa's Answer API, with a
    trailing 'Fontes:' line listing the cited source URLs."""
    try:
        from exa_py import Exa
    except ImportError as exc:
        raise ResearchError("exa_py não está instalado (pip install exa_py).") from exc

    query = f"What are recent, specific, publicly known facts about {name}, {role_label} at {company}?"

    try:
        exa = Exa(api_key=api_key)
        response = exa.answer(query, system_prompt=_SYSTEM_PROMPT)
    except Exception as exc:
        raise ResearchError(f"Falha na pesquisa EXA: {exc}") from exc

    raw_answer = response.answer if isinstance(response.answer, str) else str(response.answer)
    facts = [line.strip().lstrip("-•").strip() for line in raw_answer.splitlines()]
    facts = [f for f in facts if len(f) > 8]

    if not facts:
        raise ResearchError(f"EXA não encontrou fatos públicos sobre '{name}' em '{company}'.")

    sources = sorted({c.url for c in response.citations if getattr(c, "url", None)})[:3]
    if sources:
        facts.append("Fontes: " + ", ".join(sources))

    return facts
