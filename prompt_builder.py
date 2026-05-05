"""Build an editable translation prompt using GPT-5.5."""

from __future__ import annotations

from openai_client import DEFAULT_MODEL, ask_openai


def build_translation_prompt(
    source_language: str,
    target_language: str,
    domain: str,
    analysis_report: str,
    source_text: str,
    tm_context: str = "",
    reference_context: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    """Ask GPT-5.5 to create a custom prompt from the analysis."""
    if not analysis_report.strip():
        raise ValueError("Run the analysis first, or type analysis notes manually.")
    if not source_text.strip():
        raise ValueError("Please paste source text before generating the prompt.")

    system_prompt = (
        "You are a prompt engineer for professional translation workflows. "
        "Write prompts that are precise, practical, and easy for a human to edit."
    )
    user_prompt = f"""Create a custom translation prompt.

Source language: {source_language}
Target language: {target_language}
Text type/domain: {domain}

The prompt must tell the translation model how to handle grammar, style,
terminology, syntax, spelling, punctuation, topic, register, and risks.

It must also instruct the model to:
- Preserve meaning completely.
- Keep terminology consistent.
- Preserve names, numbers, dates, units, and formatting where appropriate.
- Preserve paragraph breaks: one source paragraph should become one target paragraph.
- If the source came from a DOCX/PDF layout, keep headings, lists, and line structure as stable as possible.
- Avoid adding information.
- Return only the translated text.
- End the prompt with this exact heading followed by the full source text: The text for translation:

Source-text analysis:
{analysis_report}

Translation Memory matches:
{tm_context or "No Translation Memory matches supplied."}

Client reference guidance:
{reference_context or "No client reference guidance supplied."}

Source text:
{source_text}

Return only the finished translation prompt.
"""
    prompt = ask_openai(system_prompt, user_prompt, model=model)
    return ensure_text_for_translation_section(prompt, source_text)


def ensure_text_for_translation_section(prompt: str, source_text: str) -> str:
    """Make sure the prompt ends with the exact source text to translate."""
    if not prompt.strip():
        raise ValueError("Translation prompt is empty.")
    if not source_text.strip():
        raise ValueError("Source text is missing.")

    marker = "The text for translation:"
    prompt_without_old_section = prompt.split(marker, 1)[0].rstrip()
    return f"{prompt_without_old_section}\n\n{marker}\n{source_text.strip()}"
