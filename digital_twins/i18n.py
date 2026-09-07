"""
Safety net for English output.

The agent prompts already instruct every node to answer in English, but
LLMs occasionally drift to another language regardless of instructions —
especially on short strings or under token pressure. Rather than
re-tuning prompt wording every time that happens, this module detects
non-English text and translates it automatically before it reaches the
transcript, the verdict, or any report.

Fails open: if detection or translation breaks (no network, langdetect
choking on a very short string, etc.), the original text is returned
unchanged rather than raising — a missed translation is much better than a
crashed debate.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def to_en(text: str) -> str:
    if not text or not text.strip():
        return text
    try:
        from langdetect import LangDetectException, detect

        try:
            if detect(text) == "en":
                return text
        except LangDetectException:
            # Too short / ambiguous to detect — leave as-is rather than guess.
            return text

        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="auto", target="en").translate(text) or text
    except Exception as exc:
        logger.warning("to_en: automatic translation failed, keeping original text (%s)", exc)
        return text


def to_en_list(items: list[str]) -> list[str]:
    return [to_en(item) for item in items]
