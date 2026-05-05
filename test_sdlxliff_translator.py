from __future__ import annotations

import unittest

from sdlxliff_translator import translate_sdlxliff_segments


SAMPLE_SDLXLIFF = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0"
       version="1.2" sdl:version="1.0">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source><mrk mtype="seg" mid="1">Open <x id="fmt1" /> file.</mrk></source>
      </trans-unit>
      <trans-unit id="2">
        <source><mrk mtype="seg" mid="2">Save changes.</mrk></source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


class SdlxliffTranslatorTests(unittest.TestCase):
    def test_translates_and_validates_segments_one_by_one(self):
        calls = []

        def fake_ask(system_prompt: str, user_prompt: str, model: str) -> str:
            calls.append((system_prompt, user_prompt, model))
            if len(calls) == 1:
                return "Odprite datoteko."
            return "Shranite spremembe."

        result = translate_sdlxliff_segments(
            SAMPLE_SDLXLIFF,
            "Translate professionally.\n\nThe text for translation:\nplaceholder",
            model="test-model",
            ask_fn=fake_ask,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(result.review_rows), 2)
        self.assertIn("[[SEG_1_TAG_1]]", result.review_rows[0]["Target"])
        self.assertEqual(result.review_rows[1]["Target"], "Shranite spremembe.")
        self.assertIn("automatically repaired", result.review_rows[0]["Review note"])
        self.assertIn("Source segment:", calls[0][1])

    def test_marks_unvalidated_segment_for_manual_review(self):
        def fake_ask(system_prompt: str, user_prompt: str, model: str) -> str:
            if "Open" in user_prompt:
                return "Odprite [[SEG_99_TAG_1]] datoteko."
            return "Shranite spremembe."

        result = translate_sdlxliff_segments(
            SAMPLE_SDLXLIFF,
            "Translate professionally.\n\nThe text for translation:\nplaceholder",
            model="test-model",
            ask_fn=fake_ask,
        )

        self.assertTrue(result.review_rows[0]["Open"])
        self.assertIn("Manual review required", result.review_rows[0]["Review note"])
        self.assertFalse(result.review_rows[1]["Open"])


if __name__ == "__main__":
    unittest.main()
