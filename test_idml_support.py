from __future__ import annotations

import unittest
from io import BytesIO
from zipfile import ZipFile

from export_same_format import create_same_format_file
from file_validation import validate_source_upload
from import_files import import_source_file


class IDMLSupportTests(unittest.TestCase):
    def test_import_idml_story_text(self):
        text = import_source_file("sample.idml", _sample_idml())

        self.assertIn("First story text.", text)
        self.assertIn("Second story text.", text)

    def test_validate_idml_requires_designmap(self):
        bad_idml = _zip_bytes({"Stories/Story_1.xml": "<Story><Content>Text</Content></Story>"})

        with self.assertRaisesRegex(ValueError, "designmap"):
            validate_source_upload("sample.idml", bad_idml)

    def test_same_format_idml_replaces_story_content(self):
        data, mime_type, note = create_same_format_file("idml", _sample_idml(), "Translated first.\nTranslated second.")

        self.assertEqual("application/vnd.adobe.indesign-idml-package", mime_type)
        self.assertIn("IDML export preserves", note)
        with ZipFile(BytesIO(data), "r") as archive:
            story_xml = archive.read("Stories/Story_1.xml").decode("utf-8")
            self.assertIn("Translated first.", story_xml)
            self.assertIn("Translated second.", story_xml)
            self.assertIn("designmap.xml", archive.namelist())


def _sample_idml() -> bytes:
    return _zip_bytes(
        {
            "designmap.xml": "<Document />",
            "Stories/Story_1.xml": (
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<Story><ParagraphStyleRange><CharacterStyleRange>"
                "<Content>First story text.</Content>"
                "<Content>Second story text.</Content>"
                "</CharacterStyleRange></ParagraphStyleRange></Story>"
            ),
            "Resources/Styles.xml": "<Styles />",
        }
    )


def _zip_bytes(files: dict[str, str]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
