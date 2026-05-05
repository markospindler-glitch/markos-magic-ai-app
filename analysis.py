"""Source-text analysis using GPT-5.5."""

from __future__ import annotations

from openai_client import DEFAULT_MODEL, ask_openai


def analyse_source_text(
    text: str,
    source_language: str,
    target_language: str,
    domain: str,
    reference_context: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    """Ask GPT-5.5 to produce a detailed, editable translation analysis."""
    if not text.strip():
        raise ValueError("Please paste source text before running the analysis.")

    system_prompt = (
        "You are a senior translation analyst. Produce practical analysis for "
        "a professional translator. Be specific, concise, and useful."
    )
    user_prompt = f"""Analyse this source text before translation.

Source language: {source_language}
Target language: {target_language}
Text type/domain: {domain}

Client reference guidance:
{reference_context or "No client reference guidance supplied."}

Return the analysis with exactly these headings:
Grammar
Style
Terminology
Syntax
Spelling
Punctuation
Topic
Register
Translation risks

For each heading, write clear notes that help produce a better translation.
Mention concrete source-text details where useful. Do not translate the text.
Take the client reference guidance into account when analysing terminology,
register, style, risks, and domain expectations.

Source text:
{text}
"""
    return ask_openai(system_prompt, user_prompt, model=model)


def format_analysis_report(analysis: str) -> str:
    """Keep compatibility with the app: the OpenAI answer is already a report."""
    return analysis.strip()
