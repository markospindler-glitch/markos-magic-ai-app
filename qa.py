"""QA checks comparing source and translated text using GPT-5.5."""

from __future__ import annotations

from openai_client import DEFAULT_MODEL, ask_openai


def run_qa_check(
    source_text: str,
    translated_text: str,
    source_language: str,
    target_language: str,
    domain: str,
    tm_context: str = "",
    reference_context: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    """Ask GPT-5.5 to compare source and target and produce an editable QA report."""
    if not source_text.strip():
        raise ValueError("Source text is missing.")
    if not translated_text.strip():
        raise ValueError("Translated text is missing.")

    system_prompt = (
        "You are a translation QA reviewer. Compare source and target carefully. "
        "Be practical and do not invent issues."
    )
    user_prompt = f"""Run a translation QA check.

Source language: {source_language}
Target language: {target_language}
Text type/domain: {domain}

Check:
- meaning transfer
- omissions
- additions
- terminology
- target-side consistency
- repeated source text translated differently in different places
- repeated or similar source phrases whose target translations should be consistent
- numbers, names, dates, units, and acronyms
- grammar and fluency in the target language
- register and style
- punctuation and formatting
- high-risk mistranslations
- compliance with client reference guidance

Return a concise editable report with:
Overall result
Issues found
Consistency findings
Recommended fixes
Final notes

Translation Memory / expected terminology context:
{tm_context or "No Translation Memory context supplied."}

Client reference guidance:
{reference_context or "No client reference guidance supplied."}

Source text:
{source_text}

Translated text:
{translated_text}
"""
    return ask_openai(system_prompt, user_prompt, model=model)
