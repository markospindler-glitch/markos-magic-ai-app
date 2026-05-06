"""Import source text from supported uploaded files."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import re

import fitz
import pandas as pd

from idml_utils import extract_idml_text
from sdlxliff_pipeline import extract_editable_segments


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NAMESPACES = {"w": WORD_NAMESPACE}
PROTECTED_TOKEN_RE = re.compile(r"\[\[(?:SEG_\d+_)?TAG_\d+(?:_OPEN|_CLOSE)?\]\]")


def import_source_file(file_name: str, file_bytes: bytes) -> str: 
    """Extract editable source text from an uploaded file."""
    suffix = Path(file_name).suffix.lower()
    if suffix == ".txt":
        return _decode_text(file_bytes)
    if suffix == ".csv":
        return extract_csv_text(file_bytes)
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return extract_excel_text(file_bytes, suffix)
    if suffix == ".docx":
        return extract_docx_text(file_bytes)
    if suffix == ".pdf":
        return extract_pdf_text(file_bytes)
    if suffix == ".idml":
        return extract_idml_text(file_bytes)
    if suffix == ".sdlxliff":
        return extract_sdlxliff_source_text(file_bytes)
    if suffix in {".xliff", ".xlf"}:
        return extract_xliff_source_text(file_bytes)
    raise ValueError("Unsupported file type. Upload a TXT, CSV, Excel, DOCX, PDF, IDML, SDLXLIFF, XLIFF, or XLF file.")

def strip_protected_tokens(text: str) -> str:
    """Remove SDLXLIFF protected inline-tag placeholders from display text."""
    return " ".join(PROTECTED_TOKEN_RE.sub("", str(text or "")).split())

def extract_csv_text(file_bytes: bytes) -> str:
    """Extract rows from a CSV file as readable text."""
    return _decode_text(file_bytes)


def extract_excel_text(file_bytes: bytes, suffix: str) -> str:
    """Extract visible workbook cell values as plain text, one row per line."""
    engine = "openpyxl" if suffix in {".xlsx", ".xlsm"} else "xlrd"
    sheets = pd.read_excel(BytesIO(file_bytes), sheet_name=None, header=None, dtype=str, engine=engine)
    blocks = []

    for sheet_name, frame in sheets.items():
        frame = frame.fillna("")
        rows = []
        for row in frame.itertuples(index=False, name=None):
            values = [str(value).strip() for value in row if str(value).strip()]
            if values:
                rows.append(" | ".join(values))
        if rows:
            blocks.append(f"Sheet: {sheet_name}\n" + "\n".join(rows))

    text = "\n\n".join(blocks)
    if not text.strip():
        raise ValueError("No readable text was found in the Excel file.")
    return text


def extract_docx_text(file_bytes: bytes) -> str:
    """Extract visible paragraph and table text from a DOCX in XML order."""
    with ZipFile(BytesIO(file_bytes), "r") as docx_zip:
        document_xml = docx_zip.read("word/document.xml")

    root = ET.fromstring(document_xml)
    paragraphs = []
    for paragraph in root.findall(".//w:p", NAMESPACES):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NAMESPACES))
        if text.strip():
            paragraphs.append(text.strip())

    text = "\n".join(paragraphs)
    if not text:
        raise ValueError("No editable text was found in the DOCX file.")
    return text


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract selectable text from a PDF file. This does not use OCR."""
    document = fitz.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text("text").strip() for page in document]
    text = "\n\n".join(page for page in pages if page)
    if not text:
        raise ValueError(
            "No selectable text was found in the PDF. Scanned PDFs need OCR, "
            "which this app still does not use."
        )
    return text


def extract_xliff_source_text(file_bytes: bytes) -> str:
    """Extract source segments from SDLXLIFF/XLIFF without editing the XML."""
    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError(
            f"The bilingual file could not be parsed as XML at line {exc.position[0]}, "
            f"column {exc.position[1]}."
        ) from exc

    units = root.findall(".//{*}trans-unit") + root.findall(".//{*}unit")
    segments = []
    for unit in units:
        source = _first_descendant(unit, "source")
        source = _preferred_segment_element(source)
        if source is None:
            continue
        text = _plain_text(source)
        if text:
            segments.append(text)

    if not segments:
        raise ValueError("No source segments were found in the SDLXLIFF/XLIFF file.")
    return "\n".join(segments)


def extract_sdlxliff_source_text(file_bytes: bytes) -> str:
    """Extract editable source segments from SDLXLIFF XML only."""
    segments = extract_editable_segments(file_bytes)
    return "\n".join(segment.protected_source_text for segment in segments)


def _decode_text(file_bytes: bytes) -> str:
    """Decode a plain text upload with common encodings."""
    for encoding in ("utf-8-sig", "utf-8", "cp1250", "cp1252"):
        try:
            text = file_bytes.decode(encoding)
            if text.strip():
                return text
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not read the TXT file. Save it as UTF-8 and try again.")


def _first_descendant(element, local_name: str):
    for child in element.iter():
        if _local_name(child.tag) == local_name:
            return child
    return None


def _preferred_segment_element(container):
    """Prefer the real segment marker in SDLXLIFF when it exists."""
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
    return " ".join("".join(element.itertext()).split())


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag
