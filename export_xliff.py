"""XLIFF export helpers for bilingual source/target translation files."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from xml.dom import minidom
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring


XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("", XLIFF_NS)

LANGUAGE_CODES = {
    "English": "en-US",
    "Slovenian": "sl-SI",
    "German": "de-DE",
    "French": "fr-FR",
    "Italian": "it-IT",
    "Spanish": "es-ES",
    "Croatian": "hr-HR",
    "Serbian": "sr-RS",
    "Bosnian": "bs-BA",
    "Portuguese": "pt-PT",
    "Dutch": "nl-NL",
    "Polish": "pl-PL",
}

ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "no.",
    "art.",
    "sec.",
    "npr.",
    "tj.",
    "oz.",
    "st.",
    "cl.",
    "g.",
    "ga.",
}


def create_xliff(
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
) -> bytes:
    """Create a fallback XLIFF from independently segmented source and target."""
    if not source_text.strip():
        raise ValueError("Source text is missing.")
    if not target_text.strip():
        raise ValueError("Target text is missing.")

    source_segments = sentence_segments(source_text)
    target_segments = sentence_segments(target_text)
    pairs, aligned_cleanly = _pair_segments(source_segments, target_segments)
    rows = [
        {"id": str(index), "source": source, "target": target}
        for index, (source, target) in enumerate(pairs, start=1)
    ]
    return create_xliff_from_aligned_rows(
        rows,
        source_language,
        target_language,
        aligned_cleanly=aligned_cleanly,
    )


def create_xliff_from_aligned_rows(
    rows: list[dict[str, str]],
    source_language: str,
    target_language: str,
    aligned_cleanly: bool = True,
) -> bytes:
    """Create standards-friendly XLIFF 1.2 from aligned source/target rows."""
    if not rows:
        raise ValueError("No aligned rows were supplied.")

    xliff = Element(_tag("xliff"), {"version": "1.2"})
    file_node = SubElement(
        xliff,
        _tag("file"),
        {
            "original": "source-document",
            "source-language": _language_code(source_language),
            "target-language": _language_code(target_language),
            "datatype": "plaintext",
        },
    )
    header = SubElement(file_node, _tag("header"))
    SubElement(
        header,
        _tag("tool"),
        {
            "tool-id": "markos-magic-ai-app",
            "tool-name": "Marko's Magic AI App",
            "tool-version": "1.0",
        },
    )
    SubElement(header, _tag("note"), {"from": "created"}).text = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    if not aligned_cleanly:
        SubElement(header, _tag("note"), {"from": "alignment"}).text = (
            "This file used fallback sentence alignment. Prepare aligned XLIFF for better bilingual alignment."
        )

    body = SubElement(file_node, _tag("body"))
    for index, row in enumerate(rows, start=1):
        source = str(row.get("source") or "").strip()
        target = str(row.get("target") or "").strip()
        confidence = _confidence(row.get("confidence", 100 if target else 0))
        note_text = str(row.get("note") or "").strip()
        approved = bool(target and confidence >= 90)
        unit = SubElement(
            body,
            _tag("trans-unit"),
            {
                "id": str(index),
                "resname": f"sentence-{index}",
                "approved": "yes" if approved else "no",
            },
        )
        source_node = SubElement(unit, _tag("source"), {_xml_lang(): _language_code(source_language)})
        source_node.text = source
        target_node = SubElement(
            unit,
            _tag("target"),
            {
                _xml_lang(): _language_code(target_language),
                "state": "translated" if approved else "needs-review-translation",
            },
        )
        target_node.text = target
        SubElement(unit, _tag("note"), {"from": "alignment-confidence"}).text = str(confidence)
        if note_text or confidence < 90:
            SubElement(unit, _tag("note"), {"from": "alignment-review"}).text = (
                note_text or "Review this segment before storing in Translation Memory."
            )

    rough_xml = tostring(xliff, encoding="utf-8", xml_declaration=True)
    return minidom.parseString(rough_xml).toprettyxml(indent="  ", encoding="utf-8")


def sentence_segments(text: str) -> list[str]:
    """Split text into sentence-like segments while preserving paragraph order."""
    segments = []
    for paragraph in [line.strip() for line in text.splitlines() if line.strip()]:
        protected = _protect_abbreviations(paragraph)
        pieces = re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+", protected)
        segments.extend(_restore_abbreviations(piece).strip() for piece in pieces if piece.strip())
    return segments or [text.strip()]


def _pair_segments(
    source_segments: list[str],
    target_segments: list[str],
) -> tuple[list[tuple[str, str]], bool]:
    """Pair sentence segments only when counts match."""
    aligned_cleanly = len(source_segments) == len(target_segments)
    pairs = []
    for index, source in enumerate(source_segments):
        target = target_segments[index] if index < len(target_segments) else ""
        pairs.append((source, target))

    if len(target_segments) > len(source_segments) and pairs:
        extra_target = " ".join(target_segments[len(source_segments) :])
        pairs[-1] = (pairs[-1][0], f"{pairs[-1][1]} {extra_target}".strip())

    return pairs, aligned_cleanly


def _protect_abbreviations(text: str) -> str:
    protected = text
    for abbreviation in ABBREVIATIONS:
        pattern = re.compile(re.escape(abbreviation), re.IGNORECASE)
        protected = pattern.sub(lambda match: match.group(0).replace(".", "<DOT>"), protected)
    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", protected)
    return protected


def _restore_abbreviations(text: str) -> str:
    return text.replace("<DOT>", ".")


def _language_code(language_name: str) -> str:
    """Return a CAT-tool-friendly language code."""
    return LANGUAGE_CODES.get(language_name, language_name)


def _tag(name: str) -> str:
    return f"{{{XLIFF_NS}}}{name}"


def _xml_lang() -> str:
    return f"{{{XML_NS}}}lang"


def _confidence(value) -> int:
    try:
        confidence = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, confidence))
