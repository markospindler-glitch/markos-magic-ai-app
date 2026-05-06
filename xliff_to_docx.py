"""Helpers for creating DOCX from XLIFF and template DOCX."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from export_docx import create_formatted_docx_from_template
from import_files import strip_protected_tokens


XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"


def extract_xliff_target_segments(xliff_bytes: bytes) -> list[str]:
    """Extract target text segments from ordinary XLIFF/XLF files in document order."""
    try:
        root = ET.fromstring(xliff_bytes)
    except ET.ParseError as exc:
        raise ValueError(
            f"The XLIFF file could not be parsed as XML at line {exc.position[0]}, "
            f"column {exc.position[1]}."
        ) from exc

    namespace = {"x": XLIFF_NS}
    target_nodes = root.findall(".//x:trans-unit/x:target", namespace)
    if not target_nodes:
        target_nodes = root.findall(".//target")

    segments = []
    for node in target_nodes:
        text = _plain_text(node)
        if text.strip():
            segments.append(strip_protected_tokens(text))
    return segments


def _plain_text(element) -> str:
    """Extract plain text from an XML element, normalizing whitespace."""
    return " ".join("".join(element.itertext()).split())


def build_target_text_from_segments(segments: list[str]) -> str:
    """Join target segments into text suitable for DOCX replacement."""
    return "\n".join(segments)


def create_docx_from_xliff_and_template(xliff_bytes: bytes, template_docx_bytes: bytes) -> bytes:
    """Create a translated DOCX from XLIFF target segments and original DOCX template."""
    segments = extract_xliff_target_segments(xliff_bytes)
    if not segments:
        raise ValueError("No usable target segments found in the XLIFF file.")
    translated_text = build_target_text_from_segments(segments)
    return create_formatted_docx_from_template(template_docx_bytes, translated_text)