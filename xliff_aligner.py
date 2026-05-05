"""GPT-assisted source/target sentence alignment for XLIFF export."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from export_xliff import XLIFF_NS, sentence_segments
from openai_client import DEFAULT_MODEL, ask_openai

MAX_ALIGNMENT_SEGMENTS_PER_REQUEST = 40
TARGET_WINDOW_OVERLAP = 10
MIN_SPLITTABLE_CHUNK_SIZE = 12
QUICK_CHECK_BATCH_SIZE = 20
QUICK_CHECK_CONTEXT_RADIUS = 2


def align_for_xliff(
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
    model: str = DEFAULT_MODEL,
) -> list[dict[str, str]]:
    """Align target translation to source sentence segments."""
    source_segments = sentence_segments(source_text)
    if not source_segments:
        raise ValueError("No source segments found for XLIFF alignment.")
    if not target_text.strip():
        raise ValueError("No target text found for XLIFF alignment.")

    target_segments = sentence_segments(target_text)
    if not target_segments:
        raise ValueError("No target segments found for XLIFF alignment.")

    if len(source_segments) == len(target_segments) and len(source_segments) > MAX_ALIGNMENT_SEGMENTS_PER_REQUEST:
        return _order_based_rows(
            source_segments,
            target_segments,
            90,
            "Source and target segment counts match; aligned by segment order.",
        )

    if max(len(source_segments), len(target_segments)) > MAX_ALIGNMENT_SEGMENTS_PER_REQUEST:
        return _align_large_document(
            source_segments,
            target_segments,
            source_language,
            target_language,
            model,
        )

    return _align_segment_lists(
        source_segments,
        target_segments,
        source_language,
        target_language,
        model,
    )


def align_fixed_source_segments(
    source_segments: list[str],
    target_text: str,
    source_language: str,
    target_language: str,
    model: str = DEFAULT_MODEL,
) -> list[dict[str, str]]:
    """Align target text to a fixed source segment list from SDLXLIFF/XLIFF."""
    fixed_source_segments = [segment.strip() for segment in source_segments if segment.strip()]
    if not fixed_source_segments:
        raise ValueError("No fixed source segments found for bilingual alignment.")
    if not target_text.strip():
        raise ValueError("No target text found for bilingual alignment.")

    target_segments = sentence_segments(target_text)
    if not target_segments:
        raise ValueError("No target segments found for bilingual alignment.")

    if len(fixed_source_segments) == len(target_segments) and len(fixed_source_segments) > MAX_ALIGNMENT_SEGMENTS_PER_REQUEST:
        return _order_based_rows(
            fixed_source_segments,
            target_segments,
            90,
            "Original bilingual source and target segment counts match; aligned by segment order.",
        )

    if max(len(fixed_source_segments), len(target_segments)) > MAX_ALIGNMENT_SEGMENTS_PER_REQUEST:
        return _align_large_document(
            fixed_source_segments,
            target_segments,
            source_language,
            target_language,
            model,
        )

    return _align_segment_lists(
        fixed_source_segments,
        target_segments,
        source_language,
        target_language,
        model,
    )


def _align_segment_lists(
    source_segments: list[str],
    target_segments: list[str],
    source_language: str,
    target_language: str,
    model: str,
) -> list[dict[str, str]]:
    """Ask GPT to align one manageable source/target segment batch."""
    system_prompt = (
        "You are a senior bilingual alignment specialist preparing translation "
        "memory-ready bilingual segments. Use semantic meaning, terminology, "
        "numbers, names, punctuation, and document order to align existing target "
        "translation to fixed source segments. Return strict JSON only."
    )
    numbered_source = _numbered_segments(source_segments)
    numbered_target = _numbered_segments(target_segments)
    user_prompt = f"""Align the target translation to these fixed source sentence segments.

Source language: {source_language}
Target language: {target_language}

Goal:
Create one bilingual row per source segment so the result can be stored safely in a translation memory.

Rules:
- Return a JSON array only.
- The array must contain exactly {len(source_segments)} objects.
- Each object must have keys: id, source, target, target_segment_ids, confidence, note.
- Use the exact source text from the numbered source segment.
- The target must be the closest matching translation for that source segment.
- Prefer whole target candidate segments, but combine adjacent target segments when one source segment was translated into multiple target sentences.
- If one target candidate contains translations of multiple source segments, split that existing target candidate carefully by meaning and assign only the matching part.
- Keep all target wording from the provided target text. Do not translate again and do not invent missing wording.
- Preserve source order and target order. Do not move unrelated target material to force a match.
- Each target candidate should normally be used once. Reuse a target candidate only when it clearly contains multiple source translations and explain this in note.
- Set confidence as an integer from 0 to 100.
- Use confidence 90-100 only for a clear one-to-one alignment.
- Use confidence 70-89 for likely but imperfect alignment.
- Use confidence below 70 if alignment is uncertain.
- Leave target empty if no reliable matching target exists.
- In note, briefly explain uncertainty, merges, splits, omissions, or additions.
- Do not create extra rows.
- Do not translate again; only align the existing target text.

Source segments:
{numbered_source}

Target candidate segments:
{numbered_target}
"""
    answer = ask_openai(system_prompt, user_prompt, model=model)
    rows = _parse_alignment_json(answer)
    return _validate_rows(rows, source_segments)


def _align_large_document(
    source_segments: list[str],
    target_segments: list[str],
    source_language: str,
    target_language: str,
    model: str,
) -> list[dict[str, str]]:
    """Align large files in smaller batches so GPT does not return empty JSON."""
    aligned_rows = []
    total_source = len(source_segments)
    total_target = len(target_segments)
    target_cursor = 0
    for start in range(0, total_source, MAX_ALIGNMENT_SEGMENTS_PER_REQUEST):
        end = min(start + MAX_ALIGNMENT_SEGMENTS_PER_REQUEST, total_source)
        source_chunk = source_segments[start:end]
        target_start, target_end = _target_window(
            start,
            end,
            total_source,
            total_target,
            target_cursor,
        )
        target_chunk = target_segments[target_start:target_end]
        if not target_chunk:
            target_chunk = target_segments[start:end]

        chunk_rows = _align_chunk_with_recovery(
            source_chunk,
            target_chunk,
            source_language,
            target_language,
            model,
        )

        for offset, row in enumerate(chunk_rows, start=start + 1):
            row["id"] = str(offset)
            aligned_rows.append(row)
        target_cursor = _next_target_cursor(target_start, target_end, target_cursor, chunk_rows)

    return _validate_rows(aligned_rows, source_segments)


def _align_chunk_with_recovery(
    source_segments: list[str],
    target_segments: list[str],
    source_language: str,
    target_language: str,
    model: str,
) -> list[dict[str, str]]:
    """Align one chunk; split it before falling back when GPT returns bad JSON."""
    try:
        return _align_segment_lists(
            source_segments,
            target_segments,
            source_language,
            target_language,
            model,
        )
    except Exception as exc:
        if len(source_segments) <= MIN_SPLITTABLE_CHUNK_SIZE:
            return _fallback_rows(source_segments, target_segments, str(exc))

        midpoint = len(source_segments) // 2
        target_midpoint = _target_midpoint(len(source_segments), len(target_segments), midpoint)
        left_rows = _align_chunk_with_recovery(
            source_segments[:midpoint],
            target_segments[:target_midpoint],
            source_language,
            target_language,
            model,
        )
        right_rows = _align_chunk_with_recovery(
            source_segments[midpoint:],
            target_segments[target_midpoint:],
            source_language,
            target_language,
            model,
        )
        return left_rows + right_rows


def extract_text_from_xliff(file_bytes: bytes) -> tuple[str, str]:
    """Extract source and target text from an uploaded XLIFF/XLF file."""
    root = ET.fromstring(file_bytes)
    namespace = {"x": XLIFF_NS}
    source_nodes = root.findall(".//x:trans-unit/x:source", namespace)
    target_nodes = root.findall(".//x:trans-unit/x:target", namespace)

    if not source_nodes:
        source_nodes = root.findall(".//source")
        target_nodes = root.findall(".//target")

    source_text = "\n".join(_node_text(node) for node in source_nodes if _node_text(node).strip())
    target_text = "\n".join(_node_text(node) for node in target_nodes if _node_text(node).strip())
    if not source_text.strip():
        raise ValueError("No source segments were found in the XLIFF file.")
    if not target_text.strip():
        raise ValueError("No target segments were found in the XLIFF file.")
    return source_text, target_text


def quick_alignment_check(
    rows: list[dict[str, str]],
    source_language: str,
    target_language: str,
    model: str = DEFAULT_MODEL,
    confidence_threshold: int = 90,
) -> list[dict[str, str]]:
    """Improve only low-confidence alignment rows using nearby context."""
    if not rows:
        raise ValueError("No aligned rows are available for quick alignment check.")

    improved_rows = [dict(row) for row in rows]
    weak_indices = [
        index
        for index, row in enumerate(improved_rows)
        if _confidence(row.get("confidence")) < confidence_threshold or not str(row.get("target") or "").strip()
    ]
    if not weak_indices:
        return improved_rows

    for batch_start in range(0, len(weak_indices), QUICK_CHECK_BATCH_SIZE):
        batch_indices = weak_indices[batch_start : batch_start + QUICK_CHECK_BATCH_SIZE]
        fixes = _quick_check_batch(
            improved_rows,
            batch_indices,
            source_language,
            target_language,
            model,
        )
        fixes_by_id = {str(fix.get("id") or ""): fix for fix in fixes if isinstance(fix, dict)}
        for index in batch_indices:
            row = improved_rows[index]
            fix = fixes_by_id.get(str(row.get("id") or index + 1))
            if not fix:
                continue
            row["target"] = str(fix.get("target") or row.get("target") or "").strip()
            row["confidence"] = _confidence(fix.get("confidence"))
            note = str(fix.get("note") or "").strip()
            if note:
                row["note"] = note
    return improved_rows


def _quick_check_batch(
    rows: list[dict[str, str]],
    weak_indices: list[int],
    source_language: str,
    target_language: str,
    model: str,
) -> list[dict[str, str]]:
    """Ask GPT to fix a small set of weak rows using local context only."""
    context_rows = _quick_check_context(rows, weak_indices)
    weak_ids = [str(rows[index].get("id") or index + 1) for index in weak_indices]
    system_prompt = (
        "You are a bilingual alignment QA specialist. Fix only weak alignment "
        "rows using nearby context. Return strict JSON only."
    )
    user_prompt = f"""Review these low-confidence alignment rows.

Source language: {source_language}
Target language: {target_language}

Only update rows with these ids: {", ".join(weak_ids)}

Rules:
- Return a JSON array only.
- Return exactly one object for each listed weak id.
- Each object must have keys: id, target, confidence, note.
- Use only target wording already present in the provided context rows.
- Do not translate again.
- Do not change high-confidence context rows.
- Fix obvious splits, merges, empty targets, and nearby one-row shifts.
- If the current target is already the best available match, keep it and set confidence accordingly.
- Set confidence as an integer from 0 to 100.
- Use confidence 90-100 only when the row is now clearly aligned.
- Leave target empty if no reliable matching target exists.

Context rows:
{json.dumps(context_rows, ensure_ascii=False, indent=2)}
"""
    answer = ask_openai(system_prompt, user_prompt, model=model)
    fixes = _parse_alignment_json(answer)
    if len(fixes) != len(weak_indices):
        raise ValueError(
            f"Quick alignment check returned {len(fixes)} row(s), expected {len(weak_indices)}."
        )
    return fixes


def _quick_check_context(rows: list[dict[str, str]], weak_indices: list[int]) -> list[dict[str, str]]:
    """Return weak rows plus a small neighbor window for context."""
    context_indices = set()
    for index in weak_indices:
        start = max(0, index - QUICK_CHECK_CONTEXT_RADIUS)
        end = min(len(rows), index + QUICK_CHECK_CONTEXT_RADIUS + 1)
        context_indices.update(range(start, end))

    context = []
    weak_set = set(weak_indices)
    for index in sorted(context_indices):
        row = rows[index]
        context.append(
            {
                "id": str(row.get("id") or index + 1),
                "source": str(row.get("source") or ""),
                "target": str(row.get("target") or ""),
                "confidence": _confidence(row.get("confidence")),
                "note": str(row.get("note") or ""),
                "needs_review": index in weak_set,
            }
        )
    return context


def _node_text(node) -> str:
    return "".join(node.itertext()).strip()


def _parse_alignment_json(answer: str) -> list[dict[str, str]]:
    cleaned = answer.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    if not cleaned.startswith("["):
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("Alignment response was not a JSON list.")
    return data


def _validate_rows(rows: list[dict[str, str]], source_segments: list[str]) -> list[dict[str, str]]:
    if len(rows) != len(source_segments):
        raise ValueError(
            f"Alignment returned {len(rows)} rows, but source has {len(source_segments)} segments."
        )

    validated = []
    for index, (row, expected_source) in enumerate(zip(rows, source_segments), start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Alignment row {index} is not an object.")
        validated.append(
            {
                "id": str(row.get("id") or index),
                "source": expected_source,
                "target": str(row.get("target") or "").strip(),
                "target_segment_ids": _target_segment_ids(row.get("target_segment_ids")),
                "confidence": _confidence(row.get("confidence")),
                "note": str(row.get("note") or "").strip(),
            }
        )
    return validated


def _target_window(
    source_start: int,
    source_end: int,
    total_source: int,
    total_target: int,
    target_cursor: int,
) -> tuple[int, int]:
    """Estimate the matching target range for one source chunk."""
    if total_source <= 0 or total_target <= 0:
        return 0, 0
    start = max(0, target_cursor - (TARGET_WINDOW_OVERLAP // 2))
    expected_count = max(1, round(((source_end - source_start) / total_source) * total_target))
    end = start + expected_count + TARGET_WINDOW_OVERLAP
    start = max(0, min(start, total_target))
    end = max(start + 1, min(end, total_target))
    return start, end


def _next_target_cursor(
    target_start: int,
    target_end: int,
    previous_cursor: int,
    rows: list[dict[str, str]],
) -> int:
    """Advance target cursor using returned target ids when possible."""
    used_ids = []
    for row in rows:
        used_ids.extend(_target_segment_ids(row.get("target_segment_ids")))
    if used_ids:
        return max(previous_cursor, target_start + max(used_ids))
    consumed_targets = sum(1 for row in rows if str(row.get("target") or "").strip())
    if consumed_targets:
        return max(previous_cursor, target_start + consumed_targets)
    return max(previous_cursor, target_end - TARGET_WINDOW_OVERLAP)


def _target_midpoint(source_count: int, target_count: int, source_midpoint: int) -> int:
    """Split target segments in roughly the same proportion as source segments."""
    if source_count <= 0 or target_count <= 0:
        return 0
    midpoint = round((source_midpoint / source_count) * target_count)
    return max(0, min(midpoint, target_count))


def _target_segment_ids(value) -> list[int]:
    """Normalize target segment ids from GPT into a simple integer list."""
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    ids = []
    for item in values:
        try:
            segment_id = int(item)
        except (TypeError, ValueError):
            continue
        if segment_id > 0:
            ids.append(segment_id)
    return ids


def _order_based_rows(
    source_segments: list[str],
    target_segments: list[str],
    confidence: int,
    note: str,
) -> list[dict[str, str]]:
    """Create reliable one-to-one rows when segmentation already matches."""
    rows = []
    for index, source in enumerate(source_segments, start=1):
        rows.append(
            {
                "id": str(index),
                "source": source,
                "target": target_segments[index - 1] if index <= len(target_segments) else "",
                "target_segment_ids": [index],
                "confidence": confidence,
                "note": note,
            }
        )
    return _validate_rows(rows, source_segments)


def _fallback_rows(source_segments: list[str], target_segments: list[str], reason: str) -> list[dict[str, str]]:
    """Return low-confidence order-based rows if GPT alignment fails for a chunk."""
    rows = []
    for index, source in enumerate(source_segments, start=1):
        target = target_segments[index - 1] if index <= len(target_segments) else ""
        note = "Low-confidence order-based fallback because GPT alignment failed for this chunk."
        if reason:
            note += f" Technical reason: {reason}"
        rows.append(
            {
                "id": str(index),
                "source": source,
                "target": target,
                "target_segment_ids": [index] if target else [],
                "confidence": 40 if target else 0,
                "note": note,
            }
        )
    if len(target_segments) > len(source_segments) and rows:
        extra = " ".join(target_segments[len(source_segments) :]).strip()
        if extra:
            rows[-1]["target"] = f"{rows[-1]['target']} {extra}".strip()
            rows[-1]["note"] += " Extra target text was attached to the last source segment in this chunk."
    return rows


def _confidence(value) -> int:
    try:
        confidence = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, confidence))


def _numbered_segments(segments: list[str]) -> str:
    return "\n".join(f"{index}. {segment}" for index, segment in enumerate(segments, start=1))
