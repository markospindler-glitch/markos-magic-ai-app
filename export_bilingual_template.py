"""Export translated SDLXLIFF/XLIFF files from the uploaded bilingual template."""

from __future__ import annotations

import re
from io import BytesIO
from xml.etree import ElementTree as ET

from sdlxliff_pipeline import (
    create_translated_sdlxliff,
    editable_segment_count,
)


BILINGUAL_EXTENSIONS = {"sdlxliff", "xliff", "xlf"}
_INVALID_XML_TEXT_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def create_translated_bilingual_file(template_bytes: bytes, target_segments: list[str]) -> bytes:
    """Return an SDLXLIFF/XLIFF file with target segments updated in place.

    The uploaded XML package is used as the template. This updates target text
    only; it does not rebuild the file from scratch.
    """
    if not template_bytes:
        raise ValueError("No uploaded bilingual template is available.")
    if not target_segments:
        raise ValueError("No target segments are available for same-format export.")

    if _looks_like_sdlxliff(template_bytes):
        return create_translated_sdlxliff(template_bytes, target_segments)

    _register_template_namespaces(template_bytes)
    root = ET.fromstring(template_bytes)
    units = root.findall(".//{*}trans-unit") + root.findall(".//{*}unit")
    editable_units = [unit for unit in units if _source_segment(unit) is not None]
    if not editable_units:
        raise ValueError("No source segments were found in the uploaded bilingual file.")
    if len(editable_units) != len(target_segments):
        raise ValueError(
            "Same-format bilingual export needs one target segment for each source segment. "
            f"The uploaded file has {len(editable_units)} source segment(s), but the final target has "
            f"{len(target_segments)} segment(s). Build or re-align the manual bilingual review table, "
            "then export again."
        )

    for unit, target_text in zip(editable_units, target_segments):
        target = _target_segment(unit)
        if target is None:
            target = _create_target_segment(unit)
        _replace_segment_text(target, target_text)
        _mark_translated(unit, target)

    return _serialize_valid_xml(root)


def bilingual_source_segment_count(template_bytes: bytes) -> int:
    """Count editable source segments in an uploaded SDLXLIFF/XLIFF template."""
    if _looks_like_sdlxliff(template_bytes):
        return editable_segment_count(template_bytes)
    _register_template_namespaces(template_bytes)
    root = ET.fromstring(template_bytes)
    units = root.findall(".//{*}trans-unit") + root.findall(".//{*}unit")
    return len([unit for unit in units if _source_segment(unit) is not None])


def target_segments_from_rows(rows: list[dict[str, str]]) -> list[str]:
    """Get export-ready targets from aligned/manual bilingual rows."""
    return [str(row.get("target") or row.get("Target") or "").strip() for row in rows if str(row.get("target") or row.get("Target") or "").strip()]


def target_segments_from_text(target_text: str) -> list[str]:
    """Use non-empty target lines as fallback segments."""
    return [line.strip() for line in target_text.splitlines() if line.strip()]


def fit_target_segments_to_count(target_text: str, required_count: int) -> list[str]:
    """Split or merge target text to exactly match the bilingual template count."""
    if required_count <= 0:
        raise ValueError("The uploaded bilingual file has no editable source segments.")

    pieces = _sentence_like_segments(target_text)
    if not pieces:
        raise ValueError("No target text is available for same-format export.")
    if len(pieces) == required_count:
        return pieces
    if required_count == 1:
        return [" ".join(pieces)]
    if len(pieces) < required_count:
        return pieces + [""] * (required_count - len(pieces))
    return _merge_segments_evenly(pieces, required_count)


def _sentence_like_segments(text: str) -> list[str]:
    segments = []
    for paragraph in [line.strip() for line in text.splitlines() if line.strip()]:
        pieces = re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+", paragraph)
        segments.extend(piece.strip() for piece in pieces if piece.strip())
    return segments


def _merge_segments_evenly(pieces: list[str], required_count: int) -> list[str]:
    merged = []
    total = len(pieces)
    for index in range(required_count):
        start = round(index * total / required_count)
        end = round((index + 1) * total / required_count)
        if end <= start:
            end = min(total, start + 1)
        merged.append(" ".join(pieces[start:end]).strip())
    return merged


def _source_segment(unit):
    source = _first_descendant(unit, "source")
    return _preferred_segment_element(source)


def _target_segment(unit):
    target = _first_descendant(unit, "target")
    return _preferred_segment_element(target)


def _create_target_segment(unit):
    source = _first_descendant(unit, "source")
    if source is None:
        raise ValueError("Cannot create target because the unit has no source.")
    target = ET.Element(_same_namespace_tag(source.tag, "target"))
    source_index = list(unit).index(source) if source in list(unit) else len(list(unit))
    unit.insert(source_index + 1, target)

    source_marker = _preferred_segment_element(source)
    if source_marker is not None and source_marker is not source and _local_name(source_marker.tag) == "mrk":
        marker = ET.SubElement(target, source_marker.tag, dict(source_marker.attrib))
        return marker
    return target


def _replace_segment_text(segment, target_text: str) -> None:
    clean_text = _xml_safe_text(target_text)
    children = list(segment)
    segment.text = clean_text
    if not children:
        return

    # SDLXLIFF inline elements often carry formatting/placeholders that Trados
    # needs later. Keep the elements in place, but remove old visible text so
    # the target segment does not contain both old and new translation text.
    for child in children:
        child.text = None
        child.tail = ""


def _mark_translated(unit, target) -> None:
    if _local_name(unit.tag) == "trans-unit":
        unit.set("approved", "yes")
    target.set("state", "translated")


def _first_descendant(element, local_name: str):
    if element is None:
        return None
    for child in element.iter():
        if _local_name(child.tag) == local_name:
            return child
    return None


def _preferred_segment_element(container):
    if container is None:
        return None
    segment_markers = []
    for child in container.iter():
        if _local_name(child.tag) != "mrk":
            continue
        marker_type = child.get("mtype") or child.get("type") or ""
        if marker_type in {"seg", "x-sdl-seg"}:
            segment_markers.append(child)
    if len(segment_markers) == 1:
        return segment_markers[0]
    return container


def _same_namespace_tag(source_tag: str, local_name: str) -> str:
    if source_tag.startswith("{"):
        namespace = source_tag.split("}", 1)[0][1:]
        return f"{{{namespace}}}{local_name}"
    return local_name


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _register_template_namespaces(template_bytes: bytes) -> None:
    """Keep original namespace prefixes such as sdl: instead of ns0: output."""
    try:
        for _event, namespace in ET.iterparse(BytesIO(template_bytes), events=("start-ns",)):
            prefix, uri = namespace
            ET.register_namespace(prefix or "", uri)
    except ET.ParseError:
        # Let the normal parser path raise the clear XML error for the caller.
        return


def _xml_safe_text(text: str) -> str:
    """Remove characters XML 1.0 cannot contain in text nodes."""
    return _INVALID_XML_TEXT_RE.sub("", str(text or ""))


def _serialize_valid_xml(root) -> bytes:
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    try:
        ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(
            "The generated bilingual XML is not well-formed, so it was not exported. "
            "Please try preparing the alignment again."
        ) from exc
    return data


def _looks_like_sdlxliff(template_bytes: bytes) -> bool:
    lower = template_bytes[:4000].lower()
    return b"sdlxliff" in lower or b"sdl.com/filetypes/sdlxliff" in lower
