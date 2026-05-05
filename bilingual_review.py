"""Helpers for an editable bilingual review table."""

from __future__ import annotations

from export_xliff import sentence_segments


def build_review_rows(source_text: str, target_text: str) -> list[dict[str, str]]:
    """Build source/target rows for manual bilingual review."""
    if not source_text.strip():
        raise ValueError("Source text is missing.")
    if not target_text.strip():
        raise ValueError("Target text is missing.")

    source_segments = sentence_segments(source_text)
    target_segments = sentence_segments(target_text)
    rows = []
    max_rows = max(len(source_segments), len(target_segments))
    for index in range(max_rows):
        rows.append(
            {
                "Segment": index + 1,
                "Source": source_segments[index] if index < len(source_segments) else "",
                "Target": target_segments[index] if index < len(target_segments) else "",
                "Review note": "",
            }
        )
    return rows


def target_text_from_rows(rows: list[dict[str, str]]) -> str:
    """Rebuild target text from edited bilingual review rows."""
    targets = []
    for row in rows:
        target = str(row.get("Target") or "").strip()
        if target:
            targets.append(target)
    if not targets:
        raise ValueError("No reviewed target text found in the bilingual review table.")
    return "\n".join(targets)
