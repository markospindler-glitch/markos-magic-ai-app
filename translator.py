"""Translation service wrapper using GPT-5.5."""

from __future__ import annotations

from openai_client import DEFAULT_MODEL, ask_openai
from translation_quality import TRANSLATION_QUALITY_REQUIREMENTS


def translate_text(
    source_text: str,
    translation_prompt: str,
    tm_context: str = "",
    reference_context: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    """Translate source text with the reviewed custom prompt."""
    if not source_text.strip():
        raise ValueError("Please paste source text before translating.")
    if not translation_prompt.strip():
        raise ValueError("Please generate or enter a translation prompt first.")

    context_parts = []
    if tm_context.strip():
        context_parts.append(
            "Translation Memory matches:\n"
            "Use exact matches unless clearly wrong; use fuzzy matches for terminology and phrasing.\n"
            f"{tm_context}"
        )
    if reference_context.strip():
        context_parts.append(
            "Client reference guidance:\n"
            "Follow this guidance for terminology, style, tone, and client preferences.\n"
            f"{reference_context}"
        )

    user_prompt = f"{TRANSLATION_QUALITY_REQUIREMENTS}\n\nSource text:\n{source_text}"
    if context_parts:
        user_prompt = "\n\n".join(context_parts) + f"\n\n{user_prompt}"

    return ask_openai(
        system_prompt=translation_prompt,
        user_prompt=user_prompt,
        model=model,
    )
