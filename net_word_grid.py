"""Net word count analysis based on the translation pricing grid."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from export_xliff import sentence_segments
from text_stats import word_count


GRID_ROWS = [
    ("New / No match", "No useful TM, repetition, or MT leverage; usually full translation effort", 1.00),
    ("50-74% fuzzy", "Low fuzzy TM match; often needs substantial retranslation", 1.00),
    ("75-84% fuzzy", "Medium fuzzy TM match", 0.80),
    ("85-94% fuzzy", "High fuzzy TM match", 0.60),
    ("95-99% fuzzy", "Near-exact TM match", 0.35),
    ("100% match", "Exact TM match, but context may differ", 0.30),
    ("101% / Context match", "Exact segment with same surrounding context", 0.10),
    ("Repetitions", "Repeated segments inside the same file/project", 0.20),
    ("Internal fuzzy", "Similar segments within the same project", 0.60),
    ("Machine translation match", "Pretranslated MT/AI output needing post-editing", 0.75),
    ("Non-translatables / locked", "Numbers, placeholders, locked segments, or client-excluded text", 0.00),
    ("Manual adjustment", "Minimum fee, DTP, terminology, PM, formatting, urgency", 1.00),
]


def analyse_net_words(source_text: str, tm_entries: list[dict[str, str]], base_rate: float) -> dict:
    """Estimate payable net words and cost using the grid categories."""
    if not source_text.strip():
        raise ValueError("Source text is missing.")

    totals = {category: 0 for category, _meaning, _weight in GRID_ROWS}
    seen_segments = []

    for segment in sentence_segments(source_text):
        words = word_count(segment)
        if words == 0:
            continue

        category = _category_for_segment(segment, seen_segments, tm_entries)
        totals[category] += words
        seen_segments.append(segment)

    rows = []
    total_raw = 0
    total_net = 0.0
    total_cost = 0.0
    for category, meaning, weight in GRID_ROWS:
        raw_words = totals[category]
        category_rate = base_rate * weight
        net_words = raw_words * weight
        cost = raw_words * category_rate
        rows.append(
            {
                "Match category": category,
                "Typical meaning": meaning,
                "Raw words": raw_words,
                "Payable weight %": int(weight * 100),
                "Base rate / word": round(base_rate, 4),
                "Category rate / word": round(category_rate, 4),
                "Net words": round(net_words, 2),
                "Cost": round(cost, 2),
            }
        )
        total_raw += raw_words
        total_net += net_words
        total_cost += cost

    return {
        "rows": rows,
        "total_raw_words": total_raw,
        "total_net_words": round(total_net, 2),
        "total_cost": round(total_cost, 2),
    }


def _category_for_segment(
    segment: str,
    previous_segments: list[str],
    tm_entries: list[dict[str, str]],
) -> str:
    normalized = _normalize(segment)
    if _is_nontranslatable(segment):
        return "Non-translatables / locked"
    if any(_normalize(previous) == normalized for previous in previous_segments):
        return "Repetitions"

    best_tm_score = _best_tm_score(segment, tm_entries)
    if best_tm_score == 100:
        return "100% match"
    if 95 <= best_tm_score <= 99:
        return "95-99% fuzzy"
    if 85 <= best_tm_score <= 94:
        return "85-94% fuzzy"
    if 75 <= best_tm_score <= 84:
        return "75-84% fuzzy"
    if 50 <= best_tm_score <= 74:
        return "50-74% fuzzy"

    best_internal_score = _best_internal_score(segment, previous_segments)
    if best_internal_score >= 75:
        return "Internal fuzzy"
    return "New / No match"


def _best_tm_score(segment: str, tm_entries: list[dict[str, str]]) -> int:
    if not tm_entries:
        return 0
    return max(_score(segment, entry.get("source", "")) for entry in tm_entries)


def _best_internal_score(segment: str, previous_segments: list[str]) -> int:
    if not previous_segments:
        return 0
    return max(_score(segment, previous) for previous in previous_segments)


def _score(left: str, right: str) -> int:
    return round(SequenceMatcher(None, _normalize(left), _normalize(right)).ratio() * 100)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _is_nontranslatable(segment: str) -> bool:
    stripped = segment.strip()
    if re.fullmatch(r"[\d\s.,:;/%+\-()]+", stripped):
        return True
    if re.fullmatch(r"(\{[^}]+\}|\[[^\]]+\]|%s|%d|\d+)", stripped):
        return True
    return False
