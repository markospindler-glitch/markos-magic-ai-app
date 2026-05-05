from __future__ import annotations

import unittest
from io import BytesIO

from docx import Document

from handout_translator_v1.app import build_source_language_docx_bytes, source_text_from_result


class HandoutIntegrationTests(unittest.TestCase):
    def test_source_language_docx_uses_english_text(self):
        result = {
            "page": {
                "title": {"english_text": "English Title", "slovenian_text": "Slovenski naslov"},
                "elements": [
                    {
                        "order": 1,
                        "element_type": "title",
                        "english_text": "English Title",
                        "slovenian_text": "Slovenski naslov",
                        "layout_hint": "centered bold",
                        "layout": {},
                    },
                    {
                        "order": 2,
                        "element_type": "body_block",
                        "english_text": "Original source sentence.",
                        "slovenian_text": "Preveden stavek.",
                        "layout_hint": "",
                        "layout": {},
                    },
                ],
            }
        }

        docx_bytes = build_source_language_docx_bytes(result)
        document = Document(BytesIO(docx_bytes))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)

        self.assertIn("English Title", text)
        self.assertIn("Original source sentence.", text)
        self.assertNotIn("Slovenski naslov", text)
        self.assertNotIn("Preveden stavek.", text)
        self.assertIn("Original source sentence.", source_text_from_result(result))


if __name__ == "__main__":
    unittest.main()
