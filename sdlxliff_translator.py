"""Segment-safe SDLXLIFF translation workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from openai_client import DEFAULT_MODEL, ask_openai
from prompt_builder import ensure_text_for_translation_section
from sdlxliff_pipeline import (
    extract_editable_segments,
    validate_and_repair_protected_translation,
)


@dataclass(frozen=True)
class SdlxliffTranslationResult:
    """Approved SDLXLIFF translation rows ready for export."""

    target_text: str
    review_rows: list[dict[str, str]]


def translate_sdlxliff_segments(
    file_bytes: bytes,
    translation_prompt: str,
    tm_context: str = "",
    reference_context: str = "",
    model: str = DEFAULT_MODEL,
    progress_callback: Callable[[int, int], None] | None = None,
    ask_fn: Callable[[str, str, str], str] = ask_openai,
) -> SdlxliffTranslationResult:
    """Translate SDLXLIFF one protected segment at a time."""
    segments = extract_editable_segments(file_bytes)
    approved_targets = []
    review_rows = []

    for position, segment in enumerate(segments, start=1):
        if progress_callback:
            progress_callback(position, len(segments))
        protected_prompt = _segment_prompt(translation_prompt, segment.protected_source_text)
        answer = ask_fn(
            protected_prompt,
            _segment_user_prompt(segment.protected_source_text, tm_context, reference_context),
            model,
        )
        cleaned_answer = _clean_segment_answer(answer)
        try:
            validation = validate_and_repair_protected_translation(
                segment.protected_source_text,
                cleaned_answer,
                segment_index=segment.index,
                auto_repair_missing_tokens=True,
            )
            target_text = validation.text
            note = validation.note
            needs_review = False
        except Exception as exc:
            target_text = cleaned_answer
            note = f"Manual review required: {exc}"
            needs_review = True
        approved_targets.append(target_text)
        review_rows.append(
            {
                "Open": needs_review,
                "Segment": segment.index,
                "Source": segment.protected_source_text,
                "Target": target_text,
                "Review note": note,
            }
        )

    return SdlxliffTranslationResult(
        target_text="\n".join(approved_targets),
        review_rows=review_rows,
    )


def _segment_prompt(translation_prompt: str, protected_source_text: str) -> str:
    prompt = ensure_text_for_translation_section(translation_prompt, protected_source_text)
    return (
        f"{prompt}\n\n"
        "SDLXLIFF safety rules:\n"
        "- Protected tokens such as [[SEG_1_TAG_1]] or [[SEG_1_TAG_1_OPEN]] must be copied exactly.\n"
        "- Do not translate, remove, rename, split, or invent protected tokens.\n"
        "- Return only the translated segment."
    )


def _segment_user_prompt(protected_source_text: str, tm_context: str, reference_context: str) -> str:
    context_parts = []
    if tm_context.strip():
        context_parts.append(f"Translation Memory matches:\n{tm_context.strip()}")
    if reference_context.strip():
        context_parts.append(f"Client reference guidance:\n{reference_context.strip()}")
    context_parts.append(f"Source segment:\n{protected_source_text}")
    return "\n\n".join(context_parts)


def _clean_segment_answer(answer: str) -> str:
    cleaned = str(answer or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith(("text", "plain", "markdown")):
            cleaned = cleaned.splitlines()[1:]
            cleaned = "\n".join(cleaned).strip()
    return cleaned
