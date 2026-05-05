"""Reference file handling for client glossaries and past translations."""

from __future__ import annotations

from import_files import import_source_file
from openai_client import DEFAULT_MODEL, ask_openai


MAX_REFERENCE_CHARS = 60000


def extract_reference_texts(files) -> list[dict[str, str]]:
    """Extract text from uploaded reference files."""
    references = []
    for file in files:
        text = import_source_file(file.name, file.getvalue())
        references.append({"name": file.name, "text": text})
    if not references:
        raise ValueError("Upload at least one reference file.")
    return references


def analyse_reference_files(
    references: list[dict[str, str]],
    source_language: str,
    target_language: str,
    domain: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Ask GPT-5.5 to extract reusable terminology and style guidance."""
    if not references:
        raise ValueError("No reference files were loaded.")

    reference_text = _combined_reference_text(references)
    system_prompt = (
        "You are a translation project reference analyst. Extract practical, "
        "reusable guidance from client reference materials."
    )
    user_prompt = f"""Analyse these reference files for a translation project.

Source language: {source_language}
Target language: {target_language}
Text type/domain: {domain}

Extract:
- mandatory terminology and preferred translations
- terms to avoid
- client style and tone preferences
- formatting or wording conventions
- recurring names, product names, acronyms, units, and phrases
- any useful examples from past translations
- risks or ambiguities to watch for

Return a concise but useful reference guidance report that can be inserted into
analysis, prompt building, translation, proofreading, and QA.

Reference files:
{reference_text}
"""
    return ask_openai(system_prompt, user_prompt, model=model)


def _combined_reference_text(references: list[dict[str, str]]) -> str:
    blocks = []
    remaining = MAX_REFERENCE_CHARS
    for reference in references:
        if remaining <= 0:
            break
        text = reference["text"].strip()
        chunk = text[:remaining]
        remaining -= len(chunk)
        blocks.append(f"File: {reference['name']}\n{chunk}")
    return "\n\n---\n\n".join(blocks)
