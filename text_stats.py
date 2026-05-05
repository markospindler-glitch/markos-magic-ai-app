"""Text statistics helpers."""

from __future__ import annotations

import re


def word_count(text: str) -> int:
    """Count words in a practical, language-agnostic way."""
    return len(re.findall(r"\b[\w'-]+\b", text or "", flags=re.UNICODE))


def char_count(text: str) -> int:
    """Count characters excluding no content special handling."""
    return len(text or "")


def stats_label(text: str) -> str:
    """Return a compact word/character count label."""
    return f"{word_count(text):,} words | {char_count(text):,} characters"
