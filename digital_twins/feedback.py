"""Feedback Loop — sistema imune para simulações de comitê.

Salva aprovações/rejeições de objeções em filas FIFO por conta
(máx. MAX_ENTRIES) em:
    ~/.digital-twins/feedback/<account_slug>.json

Cada entrada:
    {"date": "YYYY-MM-DD", "text": str, "approved": bool, "reason": str | None}

O bloco de feedback é injetado nos prompts de sistema das personas e do
Synthesizer para que simulações futuras evitem objeções rejeitadas e
prestem atenção em padrões aprovados.
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
    """Adiciona uma entrada de feedback; mantém FIFO com max MAX_ENTRIES."""
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
    """Retorna todas as entradas de feedback de uma conta."""
    return _load(account_slug)


def remove_feedback(account_slug: str, text: str) -> None:
    """Remove uma entrada específica de feedback pelo texto."""
    entries = _load(account_slug)
    entries = [e for e in entries if e["text"] != text]
    _save(account_slug, entries)


def clear_feedback(account_slug: str) -> None:
    """Apaga todo o feedback de uma conta."""
    path = _feedback_path(account_slug)
    if path.exists():
        path.unlink()


def all_accounts_with_feedback() -> list[str]:
    """Retorna lista de account_slugs que têm arquivo de feedback."""
    if not FEEDBACK_DIR.exists():
        return []
    return [f.stem for f in sorted(FEEDBACK_DIR.glob("*.json"))]


def build_feedback_prompt_block(account_slug: str) -> str:
    """Retorna bloco formatado para injeção em prompts de sistema.

    Retorna string vazia se não houver feedback registrado.
    """
    entries = _load(account_slug)
    if not entries:
        return ""

    rejected = [e for e in entries if not e["approved"]]
    approved = [e for e in entries if e["approved"]]

    lines = [
        "## Feedback de Simulações Anteriores (consulte ANTES de gerar)",
    ]

    if rejected:
        lines.append("### ❌ REJEITADOS — NÃO levante novamente:")
        for e in rejected:
            reason_part = f" — {e['reason']}" if e.get("reason") else ""
            lines.append(f'  - [{e["date"]}] "{e["text"]}"{reason_part}')

    if approved:
        lines.append("### ✅ APROVADOS — busque questões similares:")
        for e in approved:
            lines.append(f'  - [{e["date"]}] "{e["text"]}"')

    return "\n".join(lines)
