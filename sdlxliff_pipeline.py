"""Safe SDLXLIFF parsing and target update helpers.

SDLXLIFF is an XML-based Trados bilingual format. The important rule here is:
change only editable target segment text and preserve the surrounding XML.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from io import BytesIO
from xml.etree import ElementTree as ET


_INVALID_XML_TEXT_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_PROTECTED_TOKEN_RE = re.compile(r"\[\[(?:SEG_\d+_)?TAG_\d+(?:_OPEN|_CLOSE)?\]\]")
_LOCKED_VALUES = {"1", "true", "yes", "locked"}


@dataclass(frozen=True)
class SdlxliffSegment:
    """One editable SDLXLIFF source segment."""

    index: int
    segment_id: str
    source_text: str
    protected_source_text: str
    target_text: str


@dataclass(frozen=True)
class _TokenSpec:
    token: str
    kind: str
    element: object


@dataclass(frozen=True)
class TokenValidationResult:
    """Approved protected-token translation for one SDLXLIFF segment."""

    text: str
    repaired: bool
    note: str


def extract_editable_segments(file_bytes: bytes) -> list[SdlxliffSegment]:
    """Parse SDLXLIFF XML and return only editable source segments."""
    root = _parse_root(file_bytes)
    segments = []
    for unit in _trans_units(root):
        if _is_locked(unit):
            continue
        source_segment = _source_segment(unit)
        if source_segment is None or _is_locked(source_segment):
            continue
        source_text = _plain_text(source_segment)
        if not source_text:
            continue
        segment_index = len(segments) + 1
        protected_source_text, _tokens = _protect_inline_tags(source_segment, segment_index)
        target_segment = _target_segment(unit)
        segments.append(
            SdlxliffSegment(
                index=segment_index,
                segment_id=_segment_id(unit, source_segment, segment_index),
                source_text=source_text,
                protected_source_text=protected_source_text,
                target_text=_plain_text(target_segment) if target_segment is not None else "",
            )
        )
    if not segments:
        raise ValueError(
            "No editable SDLXLIFF source segments were found. The file may contain only locked "
            "segments or an unsupported SDLXLIFF structure."
        )
    return segments


def create_translated_sdlxliff(
    file_bytes: bytes,
    translations: list[str],
    auto_repair_missing_tokens: bool = True,
) -> bytes:
    """Insert translations into matching editable SDLXLIFF target segments."""
    if not file_bytes:
        raise ValueError("No SDLXLIFF file is available.")
    if not translations:
        raise ValueError("No translations are available for SDLXLIFF export.")

    _register_namespaces(file_bytes)
    root = _parse_root(file_bytes)
    editable_units = _editable_units(root)
    if len(editable_units) != len(translations):
        raise ValueError(
            "SDLXLIFF export needs exactly one target segment for each editable source segment. "
            f"The SDLXLIFF file has {len(editable_units)} editable segment(s), but "
            f"{len(translations)} translation segment(s) were provided."
        )

    for segment_index, (unit, translation) in enumerate(zip(editable_units, translations), start=1):
        source_segment = _source_segment(unit)
        if source_segment is None:
            raise ValueError("Unsupported SDLXLIFF structure: editable unit has no source segment.")
        target_segment = _target_segment(unit)
        if target_segment is None:
            target_segment = _create_target_segment(unit, source_segment)
        _replace_target_text(
            target_segment,
            translation,
            source_segment,
            segment_index,
            auto_repair_missing_tokens=auto_repair_missing_tokens,
        )
        _mark_translated(unit, target_segment)

    return _serialize_valid_xml(root)


def editable_segment_count(file_bytes: bytes) -> int:
    """Return the number of editable source segments in an SDLXLIFF file."""
    return len(extract_editable_segments(file_bytes))


def validate_and_repair_sdlxliff_translations(file_bytes: bytes, translations: list[str]) -> list[str]:
    """Validate target rows against their matching SDLXLIFF source tokens."""
    if not translations:
        raise ValueError("No SDLXLIFF target rows are available for export.")
    root = _parse_root(file_bytes)
    editable_units = _editable_units(root)
    if len(editable_units) != len(translations):
        raise ValueError(
            "SDLXLIFF export needs one validated target row for each editable source segment. "
            f"The SDLXLIFF file has {len(editable_units)} editable segment(s), but "
            f"{len(translations)} target row(s) are available."
        )

    approved = []
    for segment_index, (unit, translation) in enumerate(zip(editable_units, translations), start=1):
        source_segment = _source_segment(unit)
        if source_segment is None:
            raise ValueError(f"SDLXLIFF segment {segment_index} has no source segment.")
        protected_source_text, _tokens = _protect_inline_tags(source_segment, segment_index)
        result = validate_and_repair_protected_translation(
            protected_source_text,
            translation,
            segment_index=segment_index,
        )
        approved.append(result.text)
    return approved


def validate_and_repair_protected_translation(
    protected_source_text: str,
    translation: str,
    segment_index: int = 1,
    auto_repair_missing_tokens: bool = True,
) -> TokenValidationResult:
    """Approve one translated segment by checking protected SDLXLIFF tokens."""
    clean_translation = _xml_safe_text(translation).strip()
    required_tokens = _tokens_in_text(protected_source_text)
    _validate_unknown_token_strings(clean_translation, required_tokens, segment_index)
    repaired = False
    if auto_repair_missing_tokens:
        repaired_text = _repair_missing_token_strings(clean_translation, required_tokens, protected_source_text)
        repaired = repaired_text != clean_translation
        clean_translation = repaired_text
    missing = [token for token in required_tokens if token not in clean_translation]
    if missing:
        raise ValueError(
            f"SDLXLIFF segment {segment_index} is missing protected token(s): {', '.join(missing)}. "
            "Keep all tokens exactly as shown or review this segment manually."
        )
    _validate_balanced_token_strings(clean_translation, segment_index)
    note = "Protected tokens validated."
    if repaired:
        note = "Missing protected tokens were automatically repaired and validated."
    return TokenValidationResult(text=clean_translation, repaired=repaired, note=note)


def _editable_units(root) -> list:
    units = []
    for unit in _trans_units(root):
        source_segment = _source_segment(unit)
        if source_segment is None:
            continue
        if _is_locked(unit) or _is_locked(source_segment):
            continue
        if _plain_text(source_segment):
            units.append(unit)
    if not units:
        raise ValueError(
            "No editable SDLXLIFF source segments were found. Locked segments and metadata were left untouched."
        )
    return units


def _parse_root(file_bytes: bytes):
    try:
        return ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError(
            f"The SDLXLIFF file could not be parsed as XML at line {exc.position[0]}, "
            f"column {exc.position[1]}."
        ) from exc


def _trans_units(root) -> list:
    units = root.findall(".//{*}trans-unit")
    if not units:
        raise ValueError("Unsupported SDLXLIFF structure: no trans-unit elements were found.")
    return units


def _source_segment(unit):
    return _preferred_segment_element(_first_descendant(unit, "source"))


def _target_segment(unit):
    return _preferred_segment_element(_first_descendant(unit, "target"))


def _create_target_segment(unit, source_segment):
    source = _first_descendant(unit, "source")
    if source is None:
        raise ValueError("Unsupported SDLXLIFF structure: cannot create target without source.")
    target = ET.Element(_same_namespace_tag(source.tag, "target"))
    children = list(unit)
    source_index = children.index(source) if source in children else len(children)
    unit.insert(source_index + 1, target)

    if source_segment is not source and _local_name(source_segment.tag) == "mrk":
        marker = ET.SubElement(target, source_segment.tag, dict(source_segment.attrib))
        _copy_inline_children(source_segment, marker)
        return marker
    _copy_inline_children(source_segment, target)
    return target


def _protect_inline_tags(segment, segment_index: int | None = None) -> tuple[str, list[_TokenSpec]]:
    tokens = []
    counter = {"value": 0}

    def next_base() -> str:
        counter["value"] += 1
        prefix = f"SEG_{segment_index}_" if segment_index is not None else ""
        return f"[[{prefix}TAG_{counter['value']}"

    def protect_element(element) -> str:
        parts = [_xml_safe_text(element.text or "")]
        for child in list(element):
            if _is_empty_inline(child):
                base = next_base()
                token = f"{base}]]"
                tokens.append(_TokenSpec(token, "empty", copy.deepcopy(child)))
                parts.append(token)
            else:
                base = next_base()
                open_token = f"{base}_OPEN]]"
                close_token = f"{base}_CLOSE]]"
                tokens.append(_TokenSpec(open_token, "open", _shallow_copy(child)))
                tokens.append(_TokenSpec(close_token, "close", _shallow_copy(child)))
                parts.append(open_token)
                parts.append(protect_element(child))
                parts.append(close_token)
            parts.append(_xml_safe_text(child.tail or ""))
        return "".join(parts)

    return protect_element(segment).strip(), tokens


def _replace_target_text(
    target_segment,
    translation: str,
    source_segment,
    segment_index: int,
    auto_repair_missing_tokens: bool,
) -> None:
    protected_source_text, tokens = _protect_inline_tags(source_segment, segment_index)
    clean_translation = _xml_safe_text(translation)
    _validate_unknown_tokens(clean_translation, tokens, segment_index)
    if auto_repair_missing_tokens:
        clean_translation = _repair_missing_protected_tokens(clean_translation, tokens, protected_source_text)
    _validate_protected_tokens(clean_translation, tokens, segment_index)

    target_segment.text = None
    for child in list(target_segment):
        target_segment.remove(child)

    if not tokens:
        target_segment.text = clean_translation
        return
    _restore_protected_tokens(target_segment, clean_translation, tokens)


def _validate_protected_tokens(translation: str, tokens: list[_TokenSpec], segment_index: int) -> None:
    missing = [spec.token for spec in tokens if spec.token not in translation]
    if missing:
        raise ValueError(
            f"SDLXLIFF segment {segment_index} could not be exported because protected inline tag token(s) are missing "
            f"from the translation: {', '.join(missing)}. Keep all tokens exactly as shown and review "
            "this segment manually."
        )


def _validate_unknown_tokens(translation: str, tokens: list[_TokenSpec], segment_index: int) -> None:
    known_tokens = {spec.token for spec in tokens}
    unknown = [token for token in _PROTECTED_TOKEN_RE.findall(translation) if token not in known_tokens]
    if unknown:
        raise ValueError(
            f"SDLXLIFF segment {segment_index} could not be exported because it contains unknown protected token(s): "
            f"{', '.join(unknown)}."
        )


def _validate_unknown_token_strings(translation: str, required_tokens: list[str], segment_index: int) -> None:
    known_tokens = set(required_tokens)
    unknown = [token for token in _PROTECTED_TOKEN_RE.findall(translation) if token not in known_tokens]
    if unknown:
        raise ValueError(
            f"SDLXLIFF segment {segment_index} contains unknown protected token(s): {', '.join(unknown)}."
        )


def _repair_missing_protected_tokens(
    translation: str,
    tokens: list[_TokenSpec],
    protected_source_text: str,
) -> str:
    """Reinsert missing source tokens at approximate target positions.

    This is intentionally conservative: when any required token is missing, the
    target text is rebuilt from the clean translation and the full original
    source token sequence. That keeps tags balanced and avoids mixing old and
    new token positions.
    """
    if not tokens:
        return translation
    required_tokens = [spec.token for spec in tokens]
    if all(token in translation for token in required_tokens):
        return translation

    plain_translation = _PROTECTED_TOKEN_RE.sub("", translation)
    token_positions = _source_token_visible_positions(protected_source_text)
    if not token_positions:
        return translation

    source_visible_length = len(_PROTECTED_TOKEN_RE.sub("", protected_source_text))
    target_length = len(plain_translation)
    insertions: dict[int, list[str]] = {}
    for token, source_position in token_positions:
        if source_visible_length <= 0:
            target_position = target_length
        else:
            target_position = round((source_position / source_visible_length) * target_length)
        target_position = max(0, min(target_length, target_position))
        insertions.setdefault(target_position, []).append(token)

    repaired_parts = []
    for position in range(target_length + 1):
        repaired_parts.extend(insertions.get(position, []))
        if position < target_length:
            repaired_parts.append(plain_translation[position])
    return "".join(repaired_parts)


def _repair_missing_token_strings(
    translation: str,
    required_tokens: list[str],
    protected_source_text: str,
) -> str:
    if not required_tokens or all(token in translation for token in required_tokens):
        return translation

    plain_translation = _PROTECTED_TOKEN_RE.sub("", translation)
    token_positions = _source_token_visible_positions(protected_source_text)
    if not token_positions:
        return translation

    source_visible_length = len(_PROTECTED_TOKEN_RE.sub("", protected_source_text))
    target_length = len(plain_translation)
    insertions: dict[int, list[str]] = {}
    for token, source_position in token_positions:
        if source_visible_length <= 0:
            target_position = target_length
        else:
            target_position = round((source_position / source_visible_length) * target_length)
        target_position = max(0, min(target_length, target_position))
        insertions.setdefault(target_position, []).append(token)

    repaired_parts = []
    for position in range(target_length + 1):
        repaired_parts.extend(insertions.get(position, []))
        if position < target_length:
            repaired_parts.append(plain_translation[position])
    return "".join(repaired_parts)


def _source_token_visible_positions(protected_source_text: str) -> list[tuple[str, int]]:
    positions = []
    visible_position = 0
    cursor = 0
    for match in _PROTECTED_TOKEN_RE.finditer(protected_source_text):
        visible_position += len(protected_source_text[cursor : match.start()])
        positions.append((match.group(0), visible_position))
        cursor = match.end()
    return positions


def _tokens_in_text(text: str) -> list[str]:
    return _PROTECTED_TOKEN_RE.findall(text or "")


def _validate_balanced_token_strings(translation: str, segment_index: int) -> None:
    stack = []
    for token in _tokens_in_text(translation):
        base = _token_base(token)
        if token.endswith("_OPEN]]"):
            stack.append(base)
        elif token.endswith("_CLOSE]]"):
            if not stack or stack[-1] != base:
                raise ValueError(
                    f"SDLXLIFF segment {segment_index} has protected tag tokens in the wrong order."
                )
            stack.pop()
    if stack:
        raise ValueError(f"SDLXLIFF segment {segment_index} has unbalanced protected tag tokens.")


def _token_base(token: str) -> str:
    return token.removesuffix("_OPEN]]").removesuffix("_CLOSE]]").removesuffix("]]")


def _restore_protected_tokens(target_segment, translation: str, tokens: list[_TokenSpec]) -> None:
    specs_by_token = {spec.token: spec for spec in tokens}
    stack = [target_segment]
    position = 0
    for match in _PROTECTED_TOKEN_RE.finditer(translation):
        _append_text(stack[-1], translation[position : match.start()])
        token = match.group(0)
        spec = specs_by_token[token]
        if spec.kind == "empty":
            stack[-1].append(_empty_copy(spec.element))
        elif spec.kind == "open":
            child = _shallow_copy(spec.element)
            stack[-1].append(child)
            stack.append(child)
        elif spec.kind == "close":
            if len(stack) == 1 or stack[-1].tag != spec.element.tag:
                raise ValueError(
                    f"SDLXLIFF segment could not be exported because protected token {token} is out of order."
                )
            stack.pop()
        position = match.end()
    _append_text(stack[-1], translation[position:])
    if len(stack) != 1:
        raise ValueError("SDLXLIFF segment could not be exported because protected tag tokens are unbalanced.")


def _append_text(element, text: str) -> None:
    if not text:
        return
    children = list(element)
    if children:
        children[-1].tail = (children[-1].tail or "") + text
    else:
        element.text = (element.text or "") + text


def _copy_inline_children(source_segment, target_segment) -> None:
    for child in list(source_segment):
        copied = copy.deepcopy(child)
        _clear_visible_text(copied)
        target_segment.append(copied)


def _clear_visible_text(element) -> None:
    element.text = None
    element.tail = ""
    for child in list(element):
        _clear_visible_text(child)


def _is_empty_inline(element) -> bool:
    return not list(element) and not (element.text or "")


def _shallow_copy(element):
    return ET.Element(element.tag, dict(element.attrib))


def _empty_copy(element):
    copied = copy.deepcopy(element)
    _clear_visible_text(copied)
    return copied


def _mark_translated(unit, target_segment) -> None:
    unit.set("approved", "yes")
    target_container = _first_descendant(unit, "target")
    if target_container is not None:
        target_container.set("state", "translated")
    target_segment.set("state", "translated")


def _is_locked(element) -> bool:
    for key, value in element.attrib.items():
        name = _local_name(key).lower()
        normalized = str(value or "").strip().lower()
        if name == "translate" and normalized in {"no", "false", "0"}:
            return True
        if name in {"locked", "locktype", "lock"} and normalized in _LOCKED_VALUES:
            return True
    return False


def _segment_id(unit, source_segment, fallback: int) -> str:
    return (
        source_segment.get("mid")
        or source_segment.get("id")
        or unit.get("id")
        or str(fallback)
    )


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


def _plain_text(element) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _same_namespace_tag(source_tag: str, local_name: str) -> str:
    if source_tag.startswith("{"):
        namespace = source_tag.split("}", 1)[0][1:]
        return f"{{{namespace}}}{local_name}"
    return local_name


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _register_namespaces(file_bytes: bytes) -> None:
    try:
        for _event, namespace in ET.iterparse(BytesIO(file_bytes), events=("start-ns",)):
            prefix, uri = namespace
            ET.register_namespace(prefix or "", uri)
    except ET.ParseError:
        return


def _xml_safe_text(text: str) -> str:
    return _INVALID_XML_TEXT_RE.sub("", str(text or ""))


def _serialize_valid_xml(root) -> bytes:
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    try:
        ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("The generated SDLXLIFF XML is not well-formed, so it was not exported.") from exc
    return data
