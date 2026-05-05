from __future__ import annotations

import unittest

from import_files import import_source_file


class ImportFilesTests(unittest.TestCase):
    def test_import_sdlxliff_source_segments(self):
        file_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source><mrk mtype="seg" mid="1">Open <x id="1"/> file.</mrk></source>
        <target><mrk mtype="seg" mid="1">Odprite <x id="1"/> datoteko.</mrk></target>
      </trans-unit>
      <trans-unit id="2">
        <source>Save changes.</source>
        <target>Shranite spremembe.</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

        text = import_source_file("sample.sdlxliff", file_bytes)

        self.assertIn("Open [[SEG_1_TAG_1]] file.", text)
        self.assertIn("Save changes.", text)
        self.assertNotIn("Odprite", text)


if __name__ == "__main__":
    unittest.main()
