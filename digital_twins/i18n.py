"""
Safety net for PT-BR output.

The agent prompts already instruct every node to answer in Portuguese, but
LLMs occasionally drift to English regardless of instructions — especially
on short strings or under token pressure. Rather than re-tuning prompt
wording every time that happens, this module detects non-Portuguese text
and translates it automatically before it reaches the transcript, the
verdict, or any report.

Fails open: if detection or translation breaks (no network, langdetect
choking on a very short string, etc.), the original text is returned
unchanged rather than raising — a missed translation is much better than a
crashed debate.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def to_pt_br(text: str) -> str:
    if not text or not text.strip():
        return text
    try:
        from langdetect import LangDetectException, detect

        try:
            if detect(text) == "pt":
                return text
        except LangDetectException:
            # Too short / ambiguous to detect — leave as-is rather than guess.
            return text

        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="auto", target="pt").translate(text) or text
    except Exception as exc:
        logger.warning("to_pt_br: tradução automática falhou, mantendo texto original (%s)", exc)
        return text


def to_pt_br_list(items: list[str]) -> list[str]:
    return [to_pt_br(item) for item in items]
