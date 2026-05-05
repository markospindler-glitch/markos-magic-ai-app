from __future__ import annotations

import unittest
from io import BytesIO
from zipfile import ZipFile

from file_validation import (
    export_preflight_warnings,
    validate_sdlxliff_template,
    validate_source_upload,
)


class FileValidationTests(unittest.TestCase):
    def test_rejects_empty_file(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            validate_source_upload("source.txt", b"")

    def test_rejects_unsupported_extension(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_source_upload("source.exe", b"abc")

    def test_rejects_invalid_pdf_signature(self):
        with self.assertRaisesRegex(ValueError, "valid PDF"):
            validate_source_upload("source.pdf", b"not a pdf")

    def test_accepts_minimal_docx_zip_with_document_xml(self):
        warnings = validate_source_upload("source.docx", _zip_bytes({"word/document.xml": "<w:document />"}))

        self.assertEqual([], warnings)

    def test_rejects_docx_without_document_xml(self):
        with self.assertRaisesRegex(ValueError, "missing its main document"):
            validate_source_upload("source.docx", _zip_bytes({"word/styles.xml": "<w:styles />"}))

    def test_rejects_invalid_xliff_xml(self):
        with self.assertRaisesRegex(ValueError, "not valid XML"):
            validate_source_upload("source.xliff", b"<xliff>")

    def test_accepts_valid_sdlxliff_template(self):
        warnings = validate_sdlxliff_template("template.sdlxliff", b"<xliff version='1.2' />")

        self.assertEqual([], warnings)

    def test_export_preflight_warns_about_missing_target_and_template_bytes(self):
        warnings = export_preflight_warnings("Source", "", "docx", b"")

        self.assertIn("Final target text is missing. Export buttons will become useful after translation or proofreading.", warnings)
        self.assertIn("Same-format export needs the original uploaded source file bytes. Re-upload the source file if needed.", warnings)

    def test_export_preflight_warns_about_sdlxliff_template_for_non_sdlxliff_input(self):
        warnings = export_preflight_warnings("Source", "Target", "docx", b"template bytes")

        self.assertIn("Bilingual SDLXLIFF export needs a real Trados-created SDLXLIFF template.", warnings)


def _zip_bytes(files: dict[str, str]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
