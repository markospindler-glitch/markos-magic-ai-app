"""Small IDML import/export helpers.

IDML files are ZIP packages containing XML files. This helper reads and updates
story text in Stories/*.xml while preserving the rest of the package.
"""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET

from export_docx import fit_text_to_paragraph_count


def extract_idml_text(file_bytes: bytes) -> str:
    """Extract readable story text from an IDML package."""
    story_texts = []
    with ZipFile(BytesIO(file_bytes), "r") as archive:
        story_names = _story_names(archive)
        for story_name in story_names:
            root = ET.fromstring(archive.read(story_name))
            parts = _content_text_nodes(root)
            if parts:
                story_texts.append("\n".join(parts))

    text = "\n\n".join(story_texts)
    if not text.strip():
        raise ValueError("No editable story text was found in the IDML file.")
    return text


def create_translated_idml(template_bytes: bytes, target_text: str) -> bytes:
    """Replace IDML story text while keeping the original package structure."""
    if not template_bytes:
        raise ValueError("No original IDML template is available.")
    if not target_text.strip():
        raise ValueError("There is no translated text to export.")

    output = BytesIO()
    with ZipFile(BytesIO(template_bytes), "r") as source_zip:
        story_names = set(_story_names(source_zip))
        content_count = _count_content_nodes(source_zip, story_names)
        replacements = fit_text_to_paragraph_count(target_text, content_count)
        replacement_index = 0

        with ZipFile(output, "w", ZIP_DEFLATED) as target_zip:
            for item in source_zip.infolist():
                data = source_zip.read(item.filename)
                if item.filename in story_names:
                    data, replacement_index = _translated_story_xml(data, replacements, replacement_index)
                target_zip.writestr(item, data)

    output.seek(0)
    return output.getvalue()


def validate_idml_package(file_bytes: bytes) -> None:
    """Raise a clear error if bytes do not look like a usable IDML package."""
    with ZipFile(BytesIO(file_bytes), "r") as archive:
        names = set(archive.namelist())
        if "designmap.xml" not in names:
            raise ValueError("This IDML file is missing designmap.xml.")
        if not _story_names(archive):
            raise ValueError("This IDML file has no Stories/*.xml files.")


def _story_names(archive: ZipFile) -> list[str]:
    return sorted(
        name
        for name in archive.namelist()
        if name.lower().startswith("stories/") and name.lower().endswith(".xml")
    )


def _content_text_nodes(root) -> list[str]:
    texts = []
    for element in root.iter():
        if _local_name(element.tag) == "Content" and (element.text or "").strip():
            texts.append(element.text.strip())
    return texts


def _count_content_nodes(archive: ZipFile, story_names: set[str]) -> int:
    count = 0
    for story_name in sorted(story_names):
        root = ET.fromstring(archive.read(story_name))
        count += len(_content_text_nodes(root))
    if count <= 0:
        raise ValueError("No editable story text was found in the IDML file.")
    return count


def _translated_story_xml(story_xml: bytes, replacements: list[str], start_index: int) -> tuple[bytes, int]:
    root = ET.fromstring(story_xml)
    replacement_index = start_index
    for element in root.iter():
        if _local_name(element.tag) != "Content" or not (element.text or "").strip():
            continue
        element.text = replacements[replacement_index] if replacement_index < len(replacements) else ""
        replacement_index += 1
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), replacement_index


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag
