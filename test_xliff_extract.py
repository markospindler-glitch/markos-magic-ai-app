from __future__ import annotations

import unittest

from xliff_aligner import extract_segment_pairs_from_xliff, extract_text_from_xliff


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

    def test_extract_segment_pairs_from_namespaced_xliff(self):
        file_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file>
    <body>
      <trans-unit id="a">
        <source>First source.</source>
        <target>Prvi cilj.</target>
      </trans-unit>
      <trans-unit id="b">
        <source>Second source.</source>
        <target>Drugi cilj.</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

        pairs = extract_segment_pairs_from_xliff(file_bytes)

        self.assertEqual(
            [
                {"id": "a", "source": "First source.", "target": "Prvi cilj."},
                {"id": "b", "source": "Second source.", "target": "Drugi cilj."},
            ],
            pairs,
        )

    def test_extract_segment_pairs_from_sdlxliff_mrk_segments(self):
        file_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0"
       version="1.2" sdl:version="1.0">
  <file>
    <body>
      <trans-unit id="1">
        <source><mrk mtype="seg" mid="1">Open <x id="fmt1" /> file.</mrk></source>
        <target><mrk mtype="seg" mid="1">Odprite <x id="fmt1" /> datoteko.</mrk></target>
      </trans-unit>
      <trans-unit id="2">
        <source><mrk mtype="seg" mid="2">Save changes.</mrk></source>
        <target><mrk mtype="seg" mid="2">Shranite spremembe.</mrk></target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

        pairs = extract_segment_pairs_from_xliff(file_bytes)

        self.assertEqual("Open file.", pairs[0]["source"])
        self.assertEqual("Odprite datoteko.", pairs[0]["target"])
        self.assertEqual("Save changes.", pairs[1]["source"])
        self.assertEqual("Shranite spremembe.", pairs[1]["target"])


if __name__ == "__main__":
    unittest.main()
