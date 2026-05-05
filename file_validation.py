"""Lightweight validation and preflight checks for imported/exported files."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile
from xml.etree import ElementTree as ET

from idml_utils import validate_idml_package


SUPPORTED_SOURCE_EXTENSIONS = {
    "txt",
    "csv",
    "docx",
    "pdf",
    "xlsx",
    "xls",
    "xlsm",
    "idml",
    "sdlxliff",
    "xliff",
    "xlf",
}

BILINGUAL_EXTENSIONS = {"sdlxliff", "xliff", "xlf"}
TEMPLATE_REQUIRED_EXTENSIONS = {"docx", "xlsx", "xlsm", "idml"}
MAX_UPLOAD_BYTES = 80 * 1024 * 1024


def validate_source_upload(file_name: str, file_bytes: bytes) -> list[str]:
    """Return non-blocking warnings for a supported upload.

    Obvious broken inputs raise ValueError before the deeper import code runs.
    """
    extension = _extension(file_name)
    if extension not in SUPPORTED_SOURCE_EXTENSIONS:
        raise ValueError("Unsupported file type.")
    if not file_bytes:
        raise ValueError("The uploaded file is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        return [
            "This file is large. Import may be slow, and GPT steps may need chunking for reliable results."
        ]

    if extension == "pdf" and not file_bytes.startswith(b"%PDF"):
        raise ValueError("This does not look like a valid PDF file.")
    if extension in {"docx", "xlsx", "xlsm", "idml"}:
        _validate_zip_based_file(extension, file_bytes)
    if extension in BILINGUAL_EXTENSIONS:
        _validate_xml_file(file_bytes, "The bilingual file is not valid XML.")
    if extension == "xls" and file_bytes.startswith(b"PK"):
        return ["This file looks like a modern Excel workbook. If import fails, save it as XLSX and try again."]
    return []


def export_preflight_warnings(
    source_text: str,
    target_text: str,
    source_file_type: str,
    source_file_bytes: bytes,
    sdlxliff_template_bytes: bytes = b"",
) -> list[str]:
    """Return advisory warnings before export buttons are used."""
    warnings: list[str] = []
    file_type = (source_file_type or "").lower()
    if not source_text.strip():
        warnings.append("Source text is missing. Some bilingual exports and reports may not be available.")
    if not target_text.strip():
        warnings.append("Final target text is missing. Export buttons will become useful after translation or proofreading.")
    if file_type in TEMPLATE_REQUIRED_EXTENSIONS and not source_file_bytes:
        warnings.append("Same-format export needs the original uploaded source file bytes. Re-upload the source file if needed.")
    if file_type in BILINGUAL_EXTENSIONS and not source_file_bytes:
        warnings.append("Same-format bilingual export needs the original uploaded bilingual file.")
    if file_type == "sdlxliff" and source_file_bytes:
        _append_xml_warning(source_file_bytes, warnings, "The original SDLXLIFF no longer looks like valid XML.")
    if file_type in {"xliff", "xlf"} and source_file_bytes:
        _append_xml_warning(source_file_bytes, warnings, "The original XLIFF/XLF no longer looks like valid XML.")
    if file_type != "sdlxliff" and not sdlxliff_template_bytes:
        warnings.append("Bilingual SDLXLIFF export needs a real Trados-created SDLXLIFF template.")
    return warnings


def validate_sdlxliff_template(file_name: str, file_bytes: bytes) -> list[str]:
    """Validate a Trados SDLXLIFF template upload before storing it."""
    if _extension(file_name) != "sdlxliff":
        raise ValueError("Upload a .sdlxliff template file.")
    if not file_bytes:
        raise ValueError("The SDLXLIFF template is empty.")
    _validate_xml_file(file_bytes, "The SDLXLIFF template is not valid XML.")
    return []


def _validate_zip_based_file(extension: str, file_bytes: bytes) -> None:
    if not is_zipfile_bytes(file_bytes):
        raise ValueError(f"This does not look like a valid {extension.upper()} file.")
    try:
        with ZipFileBytes(file_bytes) as archive:
            names = set(archive.namelist())
    except BadZipFile as exc:
        raise ValueError(f"This does not look like a valid {extension.upper()} file.") from exc

    if extension == "docx" and "word/document.xml" not in names:
        raise ValueError("This DOCX file is missing its main document content.")
    if extension in {"xlsx", "xlsm"} and "xl/workbook.xml" not in names:
        raise ValueError(f"This {extension.upper()} file is missing workbook content.")
    if extension == "idml":
        validate_idml_package(file_bytes)


def _validate_xml_file(file_bytes: bytes, message: str) -> None:
    try:
        ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError(message) from exc


def _append_xml_warning(file_bytes: bytes, warnings: list[str], message: str) -> None:
    try:
        _validate_xml_file(file_bytes, message)
    except ValueError:
        warnings.append(message)


def _extension(file_name: str) -> str:
    return Path(file_name or "").suffix.lower().lstrip(".")


def is_zipfile_bytes(file_bytes: bytes) -> bool:
    """Tiny wrapper to make zip signature checks testable."""
    from io import BytesIO

    return is_zipfile(BytesIO(file_bytes))


class ZipFileBytes(ZipFile):
    """Open zip bytes without repeating BytesIO boilerplate."""

    def __init__(self, file_bytes: bytes):
        from io import BytesIO

        super().__init__(BytesIO(file_bytes), "r")
