"""Feedback Loop — immune system for committee simulations.

Saves objection approvals/rejections in per-account FIFO queues
(max MAX_ENTRIES) at:
    ~/.digital-twins/feedback/<account_slug>.json

Each entry:
    {"date": "YYYY-MM-DD", "text": str, "approved": bool, "reason": str | None}

The feedback block is injected into the personas' and the Synthesizer's
system prompts so future simulations avoid rejected objections and pay
attention to approved patterns.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

FEEDBACK_DIR = Path.home() / ".digital-twins" / "feedback"
MAX_ENTRIES = 30


def _feedback_path(account_slug: str) -> Path:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    return FEEDBACK_DIR / f"{account_slug}.json"


def _load(account_slug: str) -> list[dict]:
    path = _feedback_path(account_slug)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(account_slug: str, entries: list[dict]) -> None:
    path = _feedback_path(account_slug)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def add_feedback(
    account_slug: str,
    text: str,
    approved: bool,
    reason: str | None = None,
) -> None:
    """Adds a feedback entry; maintains a FIFO with a max of MAX_ENTRIES."""
    entries = _load(account_slug)
    entry: dict = {
        "date": date.today().isoformat(),
        "text": text,
        "approved": approved,
        "reason": reason or None,
    }
    entries.append(entry)
    entries = entries[-MAX_ENTRIES:]
    _save(account_slug, entries)


def load_feedback(account_slug: str) -> list[dict]:
    """Returns all feedback entries for an account."""
    return _load(account_slug)


def remove_feedback(account_slug: str, text: str) -> None:
    """Removes a specific feedback entry by its text."""
    entries = _load(account_slug)
    entries = [e for e in entries if e["text"] != text]
    _save(account_slug, entries)


def clear_feedback(account_slug: str) -> None:
    """Deletes all feedback for an account."""
    path = _feedback_path(account_slug)
    if path.exists():
        path.unlink()


def all_accounts_with_feedback() -> list[str]:
    """Returns the list of account_slugs that have a feedback file."""
    if not FEEDBACK_DIR.exists():
        return []
    return [f.stem for f in sorted(FEEDBACK_DIR.glob("*.json"))]


def build_feedback_prompt_block(account_slug: str) -> str:
    """Returns a formatted block for injection into system prompts.

    Returns an empty string if there is no feedback on record.
    """
    entries = _load(account_slug)
    if not entries:
        return ""

    rejected = [e for e in entries if not e["approved"]]
    approved = [e for e in entries if e["approved"]]

    lines = [
        "## Feedback from Previous Simulations (consult BEFORE generating)",
    ]

    if rejected:
        lines.append("### ❌ REJECTED — do NOT raise again:")
        for e in rejected:
            reason_part = f" — {e['reason']}" if e.get("reason") else ""
            lines.append(f'  - [{e["date"]}] "{e["text"]}"{reason_part}')

    if approved:
        lines.append("### ✅ APPROVED — look for similar questions:")
        for e in approved:
            lines.append(f'  - [{e["date"]}] "{e["text"]}"')

    return "\n".join(lines)
