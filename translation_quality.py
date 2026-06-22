"""Shared quality instructions for AI translation workflow steps."""

from __future__ import annotations


TRANSLATION_QUALITY_REQUIREMENTS = """Translation quality requirements:
- Transfer the full meaning accurately; do not summarize, simplify, embellish, or add information.
- Translate every heading, paragraph, list item, table cell, caption, footnote-like line, and repeated phrase.
- Use fluent, idiomatic target-language wording while staying faithful to the source.
- Keep terminology consistent with the Translation Memory and client reference guidance.
- Preserve names, numbers, dates, units, URLs, emails, placeholders, file markers, and protected tags exactly.
- Preserve paragraph order and line structure as much as possible.
- Resolve ambiguity conservatively; if unsure, choose the safest literal translation rather than omitting text.
- Before returning the final answer, silently check for omissions, untranslated source-language text, terminology drift, and formatting loss."""


PROOFREADING_QUALITY_REQUIREMENTS = """Proofreading quality requirements:
- Improve target-language fluency, grammar, syntax, spelling, punctuation, register, and naturalness.
- Keep the translated meaning unchanged; do not add, remove, summarize, or reinterpret content.
- Preserve terminology required by the Translation Memory and client reference guidance.
- Preserve names, numbers, dates, units, URLs, emails, placeholders, file markers, protected tags, and paragraph structure.
- Make precise corrections only; avoid unnecessary rewriting of already good translations.
- Before returning the final answer, silently check that no paragraph or segment has been lost."""


QA_QUALITY_CHECKLIST = """Quality checks to perform especially carefully:
- Omitted or untranslated paragraphs, headings, list items, table cells, captions, or repeated phrases.
- Meaning shifts, over-translation, under-translation, additions, or unjustified simplification.
- Terminology inconsistency against the Translation Memory or client reference guidance.
- Awkward, non-native, or domain-inappropriate target-language phrasing.
- Source-language text left unchanged in the target.
- Inconsistent translation of repeated source segments.
- Formatting-sensitive items: numbers, names, dates, units, URLs, emails, placeholders, file markers, and protected tags."""
