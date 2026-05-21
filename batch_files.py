"""Helpers for multi-file translation projects.

The app still runs one translation workflow, so batch projects use visible
file markers. Those markers let the final target text be split back into one
output file for each uploaded source file.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import re

from export_bilingual_template import (
    BILINGUAL_EXTENSIONS,
    bilingual_source_segment_count,
    create_translated_bilingual_file,
    fit_target_segments_to_count,
    target_segments_from_text,
)
from export_same_format import create_same_format_file
from file_validation import validate_source_upload
from import_files import import_source_file, strip_protected_tokens


FILE_MARKER_PREFIX = "TRANSLATAI_FILE"
_MARKER_RE = re.compile(r"\[\[TRANSLATAI_FILE_(\d+)_(START|END)\]\]")


def file_start_marker(index: int) -> str:
    """Return the exact marker that starts one file in a batch project."""
    return f"[[{FILE_MARKER_PREFIX}_{index}_START]]"


def file_end_marker(index: int) -> str:
    """Return the exact marker that ends one file in a batch project."""
    return f"[[{FILE_MARKER_PREFIX}_{index}_END]]"


def has_file_markers(text: str) -> bool:
    """Tell whether text contains TranslatAI batch markers."""
    return bool(_MARKER_RE.search(text or ""))


def batch_prompt_instruction() -> str:
    """Instruction added to prompts whenever source text contains file markers."""
    return (
        "Batch file rules:\n"
        "- Preserve every marker like [[TRANSLATAI_FILE_1_START]] and [[TRANSLATAI_FILE_1_END]] exactly.\n"
        "- Do not translate, delete, rename, or move those markers.\n"
        "- Keep each file's translation between its matching START and END markers.\n"
        "- Return all files in the same order as the source text."
    )


def import_uploaded_source_files(uploaded_files) -> list[dict]:
    """Import multiple Streamlit uploaded files into source-file records."""
    records = []
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        records.append(import_source_file_record(uploaded_file.name, file_bytes))
    if not records:
        raise ValueError("Upload at least one source file.")
    return records


def import_source_file_record(file_name: str, file_bytes: bytes) -> dict:
    """Validate and import one uploaded source file into a session-safe record."""
    warnings = validate_source_upload(file_name, file_bytes)
    extension = Path(file_name).suffix.lower().lstrip(".")
    text = import_source_file(file_name, file_bytes)
    if extension in BILINGUAL_EXTENSIONS:
        text = strip_protected_tokens(text)
    return make_source_file_record(file_name, file_bytes, text, warnings)


def make_source_file_record(
    file_name: str,
    file_bytes: bytes,
    text: str,
    warnings: list[str] | None = None,
) -> dict:
    """Create the small file record stored in Streamlit session state."""
    extension = Path(file_name).suffix.lower().lstrip(".")
    return {
        "name": file_name,
        "extension": extension,
        "size_bytes": len(file_bytes or b""),
        "bytes": file_bytes or b"",
        "text": text or "",
        "warnings": list(warnings or []),
    }


def build_combined_source_text(source_files: list[dict]) -> str:
    """Combine imported file texts with protected markers between files."""
    sections = []
    for index, record in enumerate(source_files, start=1):
        text = str(record.get("text") or "").strip()
        sections.append(f"{file_start_marker(index)}\n{text}\n{file_end_marker(index)}")
    return "\n\n".join(sections).strip()


def split_text_by_file_markers(text: str, file_count: int) -> dict[int, str]:
    """Split translated batch text back into per-file target text."""
    if file_count <= 0:
        raise ValueError("No source files are available for batch export.")
    if file_count == 1 and not has_file_markers(text):
        return {1: text.strip()}

    parts: dict[int, str] = {}
    for index in range(1, file_count + 1):
        start = re.escape(file_start_marker(index))
        end = re.escape(file_end_marker(index))
        match = re.search(start + r"\s*(.*?)\s*" + end, text or "", flags=re.DOTALL)
        if not match:
            raise ValueError(
                f"File marker {file_start_marker(index)} / {file_end_marker(index)} is missing from the final "
                "translation. Keep the markers exactly as shown so the app can split the output files."
            )
        parts[index] = match.group(1).strip()
    return parts


def create_batch_output_zip(source_files: list[dict], final_translation: str) -> tuple[bytes, dict]:
    """Create one same-format output per source file and return a ZIP package."""
    if len(source_files) < 2:
        raise ValueError("Batch export needs at least two source files.")
    target_parts = split_text_by_file_markers(final_translation, len(source_files))

    output = BytesIO()
    exported = 0
    errors = []
    used_names: set[str] = set()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for index, record in enumerate(source_files, start=1):
            file_name = _target_file_name(record, used_names)
            try:
                data, _mime_type, _note = _create_one_output_file(record, target_parts[index])
                archive.writestr(file_name, data)
                exported += 1
            except Exception as exc:
                errors.append(f"{record.get('name', f'File {index}')}: {exc}")

        if errors:
            archive.writestr("EXPORT_ERRORS.txt", "\n".join(errors))

    if exported == 0:
        raise ValueError("None of the batch output files could be prepared. " + " ".join(errors))
    return output.getvalue(), {"exported": exported, "errors": errors}


def _create_one_output_file(record: dict, target_text: str) -> tuple[bytes, str, str]:
    extension = str(record.get("extension") or "").lower()
    source_bytes = record.get("bytes") or b""
    if extension in BILINGUAL_EXTENSIONS:
        required_count = bilingual_source_segment_count(source_bytes)
        target_segments = target_segments_from_text(target_text)
        if len(target_segments) != required_count:
            target_segments = fit_target_segments_to_count(target_text, required_count)
        return (
            create_translated_bilingual_file(source_bytes, target_segments),
            "application/xliff+xml",
            "Bilingual file exported from original template.",
        )
    return create_same_format_file(extension, source_bytes, target_text)


def _target_file_name(record: dict, used_names: set[str]) -> str:
    source_name = str(record.get("name") or "translation.txt")
    path = Path(source_name)
    extension = str(record.get("extension") or path.suffix.lower().lstrip(".") or "txt").lower()
    stem = _safe_stem(path.stem or "translation")
    candidate = f"{stem}_target.{extension}"
    counter = 2
    while candidate.lower() in used_names:
        candidate = f"{stem}_target_{counter}.{extension}"
        counter += 1
    used_names.add(candidate.lower())
    return candidate


def _safe_stem(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem.strip())
    return cleaned.strip("_") or "translation"
