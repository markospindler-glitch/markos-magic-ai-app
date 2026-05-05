"""Reflow translated text to match source DOCX paragraph count."""

from __future__ import annotations

from import_files import extract_docx_text
from openai_client import DEFAULT_MODEL, ask_openai


def source_docx_paragraph_count(docx_bytes: bytes) -> int:
    """Count non-empty paragraphs extracted from a DOCX."""
    text = extract_docx_text(docx_bytes)
    return len([line for line in text.splitlines() if line.strip()])


def reflow_to_paragraph_count(
    target_text: str,
    paragraph_count: int,
    target_language: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Ask GPT-5.5 to reflow target text into exactly N paragraphs."""
    if not target_text.strip():
        raise ValueError("Target text is missing.")
    if paragraph_count < 1:
        raise ValueError("Source paragraph count must be at least 1.")

    system_prompt = (
        "You are a document layout-preservation editor. Reflow translated text "
        "without changing meaning, so it matches the required paragraph count."
    )
    user_prompt = f"""Reflow this {target_language} translation into exactly {paragraph_count} non-empty paragraphs.

Rules:
- Preserve the full meaning.
- Do not add information.
- Do not remove information.
- Do not translate into another language.
- Keep the wording as close as possible.
- Return only the reflowed text.
- Separate paragraphs with one blank line.

Target text:
{target_text}
"""
    return ask_openai(system_prompt, user_prompt, model=model)
