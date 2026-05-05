from __future__ import annotations

import unittest

from xliff_aligner import extract_text_from_xliff


class XliffExtractTests(unittest.TestCase):
    def test_extract_text_from_sdlxliff(self):
        file_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source>Open the file.</source>
        <target>Odprite datoteko.</target>
      </trans-unit>
      <trans-unit id="2">
        <source>Save changes.</source>
        <target>Shranite spremembe.</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

        source_text, target_text = extract_text_from_xliff(file_bytes)

        self.assertIn("Open the file.", source_text)
        self.assertIn("Save changes.", source_text)
        self.assertIn("Odprite datoteko.", target_text)
        self.assertIn("Shranite spremembe.", target_text)


if __name__ == "__main__":
    unittest.main()
