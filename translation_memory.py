"""Small local Translation Memory helpers.

This is intentionally simple: it can read TMX or CSV memories, find fuzzy
matches for the current source text, and export the finished work as TMX.
"""

from __future__ import annotations

import csv
import sqlite3
import tempfile
from datetime import datetime, timezone
from difflib import SequenceMatcher
from io import BytesIO, StringIO
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring

from export_xliff import LANGUAGE_CODES


def import_tm(file_name: str, file_bytes: bytes) -> list[dict[str, str]]:
    """Import TM entries from TMX, CSV, or read-only SDLTM."""
    suffix = Path(file_name).suffix.lower()
    if suffix == ".tmx":
        return _import_tmx(file_bytes)
    if suffix == ".csv":
        return _import_csv(file_bytes)
    if suffix == ".sdltm":
        return _import_sdltm(file_bytes)
    raise ValueError("Unsupported TM file. Upload a TMX, CSV, or SDLTM file.")


def find_tm_matches(
    source_text: str,
    tm_entries: list[dict[str, str]],
    minimum_score: int = 70,
    limit: int = 10,
) -> list[dict[str, str]]:
    """Find useful fuzzy TM matches for the current source text."""
    source_segments = _segments(source_text)
    matches = []

    for segment in source_segments:
        for entry in tm_entries:
            score = _score(segment, entry["source"])
            if score >= minimum_score:
                matches.append(
                    {
                        "score": str(score),
                        "current_source": segment,
                        "tm_source": entry["source"],
                        "tm_target": entry["target"],
                    }
                )

    matches.sort(key=lambda item: int(item["score"]), reverse=True)
    return matches[:limit]


def format_tm_matches(matches: list[dict[str, str]]) -> str:
    """Convert TM matches into editable prompt context."""
    if not matches:
        return ""

    blocks = []
    for index, match in enumerate(matches, start=1):
        blocks.append(
            f"Match {index} ({match['score']}%)\n"
            f"Current source: {match['current_source']}\n"
            f"TM source: {match['tm_source']}\n"
            f"TM target: {match['tm_target']}"
        )
    return "\n\n".join(blocks)


def create_tmx(
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
) -> bytes:
    """Export aligned source/target text as a simple TMX memory."""
    if not source_text.strip():
        raise ValueError("Source text is missing.")
    if not target_text.strip():
        raise ValueError("Target text is missing.")

    source_segments = _segments(source_text)
    target_segments = _segments(target_text)
    if len(source_segments) != len(target_segments):
        source_segments = [source_text.strip()]
        target_segments = [target_text.strip()]

    tmx = Element("tmx", {"version": "1.4"})
    header = SubElement(
        tmx,
        "header",
        {
            "creationtool": "Local Translation Workflow",
            "creationtoolversion": "1.0",
            "segtype": "paragraph",
            "adminlang": "en-US",
            "srclang": _language_code(source_language),
            "datatype": "PlainText",
        },
    )
    header.set("creationdate", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    body = SubElement(tmx, "body")

    for source, target in zip(source_segments, target_segments):
        tu = SubElement(body, "tu")
        _add_tuv(tu, _language_code(source_language), source)
        _add_tuv(tu, _language_code(target_language), target)

    rough_xml = tostring(tmx, encoding="utf-8")
    return minidom.parseString(rough_xml).toprettyxml(indent="  ", encoding="utf-8")


def create_tmx_from_entries(
    entries: list[dict[str, str]],
    source_language: str,
    target_language: str,
) -> bytes:
    """Export TM entries as TMX."""
    if not entries:
        raise ValueError("No TM entries are available.")

    return _build_tmx(entries, source_language, target_language)


def updated_tmx_from_aligned_rows(
    existing_entries: list[dict[str, str]],
    aligned_rows: list[dict[str, str]],
    source_language: str,
    target_language: str,
    minimum_confidence: int = 90,
) -> bytes:
    """Merge existing TM entries with high-confidence aligned rows."""
    merged = list(existing_entries or [])
    seen = {_entry_key(entry) for entry in merged}

    for row in aligned_rows:
        confidence = int(row.get("confidence", 0) or 0)
        source = str(row.get("source") or "").strip()
        target = str(row.get("target") or "").strip()
        if confidence < minimum_confidence or not source or not target:
            continue
        entry = {"source": source, "target": target}
        key = _entry_key(entry)
        if key not in seen:
            merged.append(entry)
            seen.add(key)

    return create_tmx_from_entries(merged, source_language, target_language)


def _import_tmx(file_bytes: bytes) -> list[dict[str, str]]:
    root = ET.parse(BytesIO(file_bytes)).getroot()
    entries = []

    for tu in root.findall(".//tu"):
        segments = []
        for tuv in tu.findall("tuv"):
            seg = tuv.find("seg")
            if seg is not None and seg.text and seg.text.strip():
                segments.append(seg.text.strip())
        if len(segments) >= 2:
            entries.append({"source": segments[0], "target": segments[1]})

    if not entries:
        raise ValueError("No translation units were found in the TMX file.")
    return entries


def _import_csv(file_bytes: bytes) -> list[dict[str, str]]:
    text = _decode_text(file_bytes)
    reader = csv.DictReader(StringIO(text))
    fields = {field.lower(): field for field in (reader.fieldnames or [])}
    source_field = fields.get("source")
    target_field = fields.get("target")
    if not source_field or not target_field:
        raise ValueError("CSV TM must have columns named source and target.")

    entries = []
    for row in reader:
        source = (row.get(source_field) or "").strip()
        target = (row.get(target_field) or "").strip()
        if source and target:
            entries.append({"source": source, "target": target})

    if not entries:
        raise ValueError("No usable source/target rows were found in the CSV file.")
    return entries


def _import_sdltm(file_bytes: bytes) -> list[dict[str, str]]:
    """Read source/target pairs from a Trados SDLTM SQLite file.

    This is deliberately read-only. SDLTM is proprietary and can vary by
    Trados version, so the importer tries safe, inspectable text-column
    patterns and refuses to guess when no usable pairs are found.
    """
    with tempfile.NamedTemporaryFile(suffix=".sdltm", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(file_bytes)

    try:
        connection = sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)
        try:
            entries = _extract_sdltm_entries(connection)
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(
            "The SDLTM file could not be read as a SQLite database. "
            "If Trados has it open or the file is damaged, close Trados or export the memory as TMX."
        ) from exc
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    if not entries:
        raise ValueError(
            "No usable source/target pairs were found in this SDLTM. "
            "SDLTM is proprietary and schemas can vary; export the memory from Trados Studio as TMX and upload that."
        )
    return entries


def _extract_sdltm_entries(connection) -> list[dict[str, str]]:
    entries = []
    for table_name in _sqlite_table_names(connection):
        columns = _sqlite_columns(connection, table_name)
        column_lookup = {column.lower(): column for column in columns}
        source_column = _first_matching_column(
            column_lookup,
            ["source", "sourcetext", "source_text", "source_segment", "src", "src_text"],
        )
        target_column = _first_matching_column(
            column_lookup,
            ["target", "targettext", "target_text", "target_segment", "trg", "tgt", "targettranslation"],
        )
        if source_column and target_column:
            entries.extend(_read_sdltm_column_pairs(connection, table_name, source_column, target_column))

    if entries:
        return _dedupe_entries(entries)

    return _dedupe_entries(_scan_sdltm_text_columns(connection))


def _sqlite_table_names(connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _sqlite_columns(connection, table_name: str) -> list[str]:
    rows = connection.execute(f'PRAGMA table_info("{_escape_identifier(table_name)}")').fetchall()
    return [str(row[1]) for row in rows]


def _first_matching_column(column_lookup: dict[str, str], candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in column_lookup:
            return column_lookup[candidate]
    for lowered, original in column_lookup.items():
        if any(candidate in lowered for candidate in candidates):
            return original
    return ""


def _read_sdltm_column_pairs(connection, table_name: str, source_column: str, target_column: str) -> list[dict[str, str]]:
    query = (
        f'SELECT "{_escape_identifier(source_column)}", "{_escape_identifier(target_column)}" '
        f'FROM "{_escape_identifier(table_name)}"'
    )
    entries = []
    for source, target in connection.execute(query).fetchmany(50000):
        source_text = _clean_sdltm_text(source)
        target_text = _clean_sdltm_text(target)
        if source_text and target_text and source_text != target_text:
            entries.append({"source": source_text, "target": target_text})
    return entries


def _scan_sdltm_text_columns(connection) -> list[dict[str, str]]:
    entries = []
    for table_name in _sqlite_table_names(connection):
        columns = _sqlite_columns(connection, table_name)
        text_columns = [column for column in columns if _looks_like_text_column(connection, table_name, column)]
        for left_index, source_column in enumerate(text_columns):
            for target_column in text_columns[left_index + 1 :]:
                sample = _read_sdltm_column_pairs(connection, table_name, source_column, target_column)
                if len(sample) >= 3:
                    entries.extend(sample)
                    return entries
    return entries


def _looks_like_text_column(connection, table_name: str, column: str) -> bool:
    query = f'SELECT "{_escape_identifier(column)}" FROM "{_escape_identifier(table_name)}" LIMIT 25'
    values = [_clean_sdltm_text(row[0]) for row in connection.execute(query).fetchall()]
    useful = [value for value in values if len(value.split()) >= 2]
    return len(useful) >= 2


def _clean_sdltm_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "utf-16", "cp1250", "cp1252"):
            try:
                value = value.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return ""
    text = str(value)
    if "<" in text and ">" in text:
        try:
            text = "".join(ET.fromstring(f"<wrapper>{text}</wrapper>").itertext())
        except ET.ParseError:
            pass
    text = " ".join(text.split())
    if len(text) > 2000:
        return ""
    return text


def _dedupe_entries(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped = []
    seen = set()
    for entry in entries:
        key = _entry_key(entry)
        if key in seen:
            continue
        deduped.append(entry)
        seen.add(key)
    return deduped


def _escape_identifier(identifier: str) -> str:
    return str(identifier).replace('"', '""')


def _add_tuv(parent, language: str, text: str) -> None:
    tuv = SubElement(parent, "tuv", {"xml:lang": language})
    seg = SubElement(tuv, "seg")
    seg.text = text


def _build_tmx(entries: list[dict[str, str]], source_language: str, target_language: str) -> bytes:
    tmx = Element("tmx", {"version": "1.4"})
    header = SubElement(
        tmx,
        "header",
        {
            "creationtool": "Marko's Magic AI App",
            "creationtoolversion": "1.0",
            "segtype": "sentence",
            "adminlang": "en-US",
            "srclang": _language_code(source_language),
            "datatype": "PlainText",
        },
    )
    header.set("creationdate", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    body = SubElement(tmx, "body")

    for entry in entries:
        source = str(entry.get("source") or "").strip()
        target = str(entry.get("target") or "").strip()
        if not source or not target:
            continue
        tu = SubElement(body, "tu")
        _add_tuv(tu, _language_code(source_language), source)
        _add_tuv(tu, _language_code(target_language), target)

    rough_xml = tostring(tmx, encoding="utf-8")
    return minidom.parseString(rough_xml).toprettyxml(indent="  ", encoding="utf-8")


def _entry_key(entry: dict[str, str]) -> tuple[str, str]:
    return (
        str(entry.get("source") or "").strip().lower(),
        str(entry.get("target") or "").strip().lower(),
    )


def _segments(text: str) -> list[str]:
    segments = [line.strip() for line in text.splitlines() if line.strip()]
    return segments or [text.strip()]


def _score(left: str, right: str) -> int:
    return round(SequenceMatcher(None, left.lower(), right.lower()).ratio() * 100)


def _decode_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1250", "cp1252"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not read the CSV file. Save it as UTF-8 and try again.")


def _language_code(language_name: str) -> str:
    return LANGUAGE_CODES.get(language_name, language_name)
