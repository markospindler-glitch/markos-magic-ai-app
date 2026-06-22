"""Small rule-based QA checks that run before the GPT QA report."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from export_xliff import sentence_segments


NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*(?:%?)")
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>\"]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r"\{\{\s*[\w. -]+\s*\}\}|\{\d+\}|\{[A-Za-z_][\w.]*\}|%[sd]"
)
WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def run_rule_based_qa(
    source_text: str,
    target_text: str,
    review_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Run deterministic source/target checks and return user-readable warnings."""
    warnings: list[dict[str, Any]] = []
    segments = _segments(source_text, target_text, review_rows)
    warnings.extend(_coverage_warnings(source_text, target_text, review_rows, segments))
    for segment in segments:
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

    if _looks_like_copied_source(source_clean, target_clean):
        warnings.append(
            _warning(
                "critical",
                "Possible untranslated text",
                "Target appears to contain the source text unchanged. Review this segment carefully.",
                source,
                target,
                segment_index,
            )
        )

    warnings.extend(_compare_tokens("warning", "Number mismatch", NUMBER_RE, source, target, segment_index))
    warnings.extend(_compare_tokens("critical", "URL mismatch", URL_RE, source, target, segment_index))
    warnings.extend(_compare_tokens("critical", "Email mismatch", EMAIL_RE, source, target, segment_index))
    warnings.extend(
        _compare_tokens("critical", "Placeholder mismatch", PLACEHOLDER_RE, source, target, segment_index)
    )
    return warnings


def _coverage_warnings(
    source_text: str,
    target_text: str,
    review_rows: list[dict[str, Any]] | None,
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Warn when the target appears shorter than the source in whole segments/paragraphs."""
    warnings: list[dict[str, Any]] = []
    if review_rows:
        return warnings

    source_segments = sentence_segments(source_text)
    target_segments = sentence_segments(target_text)
    if source_segments and len(target_segments) < len(source_segments):
        missing_index = len(target_segments) + 1
        missing_source = source_segments[missing_index - 1] if missing_index <= len(source_segments) else ""
        warnings.append(
            _warning(
                "critical",
                "Possible missing translation",
                (
                    f"Target has fewer sentence-like segments than the source "
                    f"({len(target_segments)} target vs {len(source_segments)} source). "
                    f"The first possibly missing source segment is segment {missing_index}."
                ),
                missing_source,
                "",
                missing_index,
            )
        )

    source_paragraphs = _non_empty_lines(source_text)
    target_paragraphs = _non_empty_lines(target_text)
    if len(source_paragraphs) > 1 and len(target_paragraphs) < len(source_paragraphs):
        missing_index = len(target_paragraphs) + 1
        missing_source = source_paragraphs[missing_index - 1] if missing_index <= len(source_paragraphs) else ""
        warnings.append(
            _warning(
                "critical",
                "Possible missing paragraph",
                (
                    f"Target has fewer non-empty paragraphs/lines than the source "
                    f"({len(target_paragraphs)} target vs {len(source_paragraphs)} source). "
                    f"Review source paragraph/line {missing_index}."
                ),
                missing_source,
                "",
                missing_index,
            )
        )

    return warnings


def _looks_like_copied_source(source: str, target: str) -> bool:
    """Detect longer source text that appears unchanged in the target."""
    source_norm = _normalize_for_copy_check(source)
    target_norm = _normalize_for_copy_check(target)
    if len(source_norm) < 45:
        return False
    if len(WORD_RE.findall(source_norm)) < 7:
        return False
    return source_norm == target_norm or source_norm in target_norm


def _normalize_for_copy_check(text: str) -> str:
    """Normalize text enough to catch copied paragraphs without being too eager."""
    return re.sub(r"\s+", " ", str(text).casefold()).strip()


def _non_empty_lines(text: str) -> list[str]:
    """Return non-empty source/target lines in document order."""
    return [line.strip() for line in str(text).splitlines() if line.strip()]


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
