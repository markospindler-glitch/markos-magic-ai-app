"""HTML diff view for proofreading changes."""

from __future__ import annotations

import html
from difflib import SequenceMatcher


def proofreading_diff_html(original: str, proofread: str) -> str:
    """Return a tracked-changes-style HTML diff with surrounding text."""
    original_words = _tokens(original)
    proofread_words = _tokens(proofread)
    matcher = SequenceMatcher(None, original_words, proofread_words)
    parts = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            context = _join_tokens(proofread_words[j1:j2])
            if context:
                parts.append(f'<span class="diff-context">{html.escape(context)}</span>')
        elif tag == "delete":
            deleted = _join_tokens(original_words[i1:i2])
            parts.append(f'<del class="diff-delete">{html.escape(deleted)}</del>')
        elif tag == "insert":
            inserted = _join_tokens(proofread_words[j1:j2])
            parts.append(f'<ins class="diff-insert">{html.escape(inserted)}</ins>')
        elif tag == "replace":
            deleted = _join_tokens(original_words[i1:i2])
            inserted = _join_tokens(proofread_words[j1:j2])
            parts.append(f'<del class="diff-delete">{html.escape(deleted)}</del> ')
            parts.append(f'<ins class="diff-insert">{html.escape(inserted)}</ins>')

    return " ".join(part for part in parts if part)


def proofreading_changes(original: str, proofread: str) -> list[dict[str, str | int]]:
    """Return selectable proofreading changes."""
    original_words = _tokens(original)
    proofread_words = _tokens(proofread)
    matcher = SequenceMatcher(None, original_words, proofread_words)
    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes.append(
            {
                "id": len(changes) + 1,
                "type": tag,
                "original": _join_tokens(original_words[i1:i2]),
                "proofread": _join_tokens(proofread_words[j1:j2]),
                "original_start": i1,
                "original_end": i2,
                "proofread_start": j1,
                "proofread_end": j2,
            }
        )
    return changes


def accept_proofreading_change(original: str, proofread: str, change_id: int) -> str:
    """Update the comparison baseline so one change is considered accepted."""
    changes = proofreading_changes(original, proofread)
    change = _find_change(changes, change_id)
    original_words = _tokens(original)
    proofread_words = _tokens(proofread)
    replacement = proofread_words[int(change["proofread_start"]) : int(change["proofread_end"])]
    updated = (
        original_words[: int(change["original_start"])]
        + replacement
        + original_words[int(change["original_end"]) :]
    )
    return _join_tokens(updated)


def reject_proofreading_change(original: str, proofread: str, change_id: int) -> str:
    """Update proofread text by reverting one change back to original wording."""
    changes = proofreading_changes(original, proofread)
    change = _find_change(changes, change_id)
    original_words = _tokens(original)
    proofread_words = _tokens(proofread)
    replacement = original_words[int(change["original_start"]) : int(change["original_end"])]
    updated = (
        proofread_words[: int(change["proofread_start"])]
        + replacement
        + proofread_words[int(change["proofread_end"]) :]
    )
    return _join_tokens(updated)


def _find_change(changes: list[dict[str, str | int]], change_id: int) -> dict[str, str | int]:
    for change in changes:
        if int(change["id"]) == int(change_id):
            return change
    raise ValueError("Selected proofreading change was not found.")


def _tokens(text: str) -> list[str]:
    return (text or "").split()


def _join_tokens(tokens: list[str]) -> str:
    return " ".join(tokens)
