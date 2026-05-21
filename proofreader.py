"""Native-speaker proofreading using GPT-5.5."""

from __future__ import annotations

from openai_client import DEFAULT_MODEL, ask_openai
from batch_files import batch_prompt_instruction, has_file_markers


def proofread_translation(
    translated_text: str,
    target_language: str,
    domain: str,
    tm_context: str = "",
    reference_context: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    """Ask GPT-5.5 to proofread the translation as a native speaker."""
    if not translated_text.strip():
        raise ValueError("Translated text is missing.")

    system_prompt = (
        f"You are a native-speaker proofreader for {target_language}. "
        "You edit translations with precision, preserving meaning while improving "
        "fluency, grammar, terminology, syntax, spelling, punctuation, register, "
        "and naturalness."
    )
    user_prompt = f"""Proofread this translation in {target_language}.

Text type/domain: {domain}

Translation Memory / preferred terminology context:
{tm_context or "No Translation Memory context supplied."}

Client reference guidance:
{reference_context or "No client reference guidance supplied."}

Instructions:
- Improve the text as a native-speaker proofreader.
- Correct grammar, syntax, spelling, punctuation, terminology, register, and style.
- Keep wording consistent with supplied Translation Memory context where appropriate.
- Follow supplied client reference guidance for terminology, tone, style, and conventions.
- Keep the meaning unchanged.
- Do not add new information.
- Preserve names, numbers, dates, units, and formatting where appropriate.
- Preserve paragraph breaks and line structure so formatted export still works.
- Make precise improvements, not a loose rewrite.
- Return only the fully proofread text, with no comments.
{batch_prompt_instruction() if has_file_markers(translated_text) else ""}

Translation to proofread:
{translated_text}
"""
    return ask_openai(system_prompt, user_prompt, model=model)
