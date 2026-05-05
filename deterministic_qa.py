"""Small rule-based QA checks that run before the GPT QA report."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*(?:%?)")
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>\"]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r"\{\{\s*[\w. -]+\s*\}\}|\{\d+\}|\{[A-Za-z_][\w.]*\}|%[sd]"
)


def run_rule_based_qa(
    source_text: str,
    target_text: str,
    review_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Run deterministic source/target checks and return user-readable warnings."""
    warnings: list[dict[str, Any]] = []
    for segment in _segments(source_text, target_text, review_rows):
        warnings.extend(_check_segment(segment["source"], segment["target"], segment["index"]))
    return warnings


def _segments(
    source_text: str,
    target_text: str,
    review_rows: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Use bilingual review rows when available; otherwise check the full text."""
    if review_rows:
        segments = []
        for position, row in enumerate(review_rows, start=1):
            source = str(row.get("Source") or "")
            target = str(row.get("Target") or "")
            segment_index = row.get("Segment") or position
            if source.strip() or target.strip():
                segments.append({"index": segment_index, "source": source, "target": target})
        if segments:
            return segments
    return [{"index": None, "source": source_text, "target": target_text}]


def _check_segment(source: str, target: str, segment_index: Any) -> list[dict[str, Any]]:
    """Run the individual checks for one source/target pair."""
    warnings: list[dict[str, Any]] = []
    source_clean = source.strip()
    target_clean = target.strip()

    if source_clean and not target_clean:
        warnings.append(
            _warning(
                "critical",
                "Empty target",
                "Target text is empty for a non-empty source segment.",
                source,
                target,
                segment_index,
            )
        )
        return warnings

    warnings.extend(_compare_tokens("warning", "Number mismatch", NUMBER_RE, source, target, segment_index))
    warnings.extend(_compare_tokens("critical", "URL mismatch", URL_RE, source, target, segment_index))
    warnings.extend(_compare_tokens("critical", "Email mismatch", EMAIL_RE, source, target, segment_index))
    warnings.extend(
        _compare_tokens("critical", "Placeholder mismatch", PLACEHOLDER_RE, source, target, segment_index)
    )
    return warnings


def _compare_tokens(
    severity: str,
    category: str,
    pattern: re.Pattern[str],
    source: str,
    target: str,
    segment_index: Any,
) -> list[dict[str, Any]]:
    """Compare repeated tokens as multisets so duplicated values are not missed."""
    source_tokens = _normalized_tokens(pattern, source)
    target_tokens = _normalized_tokens(pattern, target)
    if source_tokens == target_tokens:
        return []

    missing = list((Counter(source_tokens) - Counter(target_tokens)).elements())
    extra = list((Counter(target_tokens) - Counter(source_tokens)).elements())
    parts = []
    if missing:
        parts.append(f"missing in target: {', '.join(missing)}")
    if extra:
        parts.append(f"extra in target: {', '.join(extra)}")
    detail = "; ".join(parts) or "source and target values differ"
    return [
        _warning(
            severity,
            category,
            f"{category}: {detail}.",
            source,
            target,
            segment_index,
        )
    ]


def _normalized_tokens(pattern: re.Pattern[str], text: str) -> list[str]:
    """Extract comparable tokens, trimming punctuation that often follows URLs."""
    tokens = []
    for match in pattern.findall(text):
        token = str(match).strip().rstrip(".,;:!?)]")
        if token.startswith("{{"):
            token = re.sub(r"\s+", " ", token)
        tokens.append(token)
    return tokens


def _warning(
    severity: str,
    category: str,
    message: str,
    source: str,
    target: str,
    segment_index: Any,
) -> dict[str, Any]:
    """Create one QA warning row for Streamlit and tests."""
    return {
        "severity": severity,
        "category": category,
        "message": message,
        "source excerpt": _excerpt(source),
        "target excerpt": _excerpt(target),
        "segment index": segment_index,
    }


def _excerpt(text: str, limit: int = 180) -> str:
    """Keep warning rows readable in the app."""
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
