from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from export_bilingual_template import create_translated_bilingual_file, fit_target_segments_to_count


class ExportBilingualTemplateTests(unittest.TestCase):
    def test_create_translated_sdlxliff_from_template(self):
        template = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source><mrk mtype="seg" mid="1">Open file.</mrk></source>
        <target><mrk mtype="seg" mid="1">Old target.</mrk></target>
      </trans-unit>
      <trans-unit id="2">
        <source>Save changes.</source>
        <target>Old second target.</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

        updated = create_translated_bilingual_file(template, ["Odprite datoteko.", "Shranite spremembe."])
        root = ET.fromstring(updated)
        targets = ["".join(node.itertext()).strip() for node in root.findall(".//{*}target")]

        self.assertEqual(targets, ["Odprite datoteko.", "Shranite spremembe."])

    def test_create_translated_sdlxliff_requires_matching_segment_count(self):
        template = b"""<xliff><file><body><trans-unit id="1"><source>One.</source></trans-unit></body></file></xliff>"""

        with self.assertRaises(ValueError):
            create_translated_bilingual_file(template, ["Ena.", "Dve."])

    def test_create_translated_sdlxliff_preserves_namespace_prefixes(self):
        template = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <sdl:seg-defs />
    <body>
      <trans-unit id="1"><source>Open.</source><target>Old.</target></trans-unit>
    </body>
  </file>
</xliff>
"""

        updated = create_translated_bilingual_file(template, ["Odpri."])

        self.assertIn(b"xmlns:sdl=", updated)
        self.assertNotIn(b"ns0:", updated)
        ET.fromstring(updated)

    def test_create_translated_sdlxliff_keeps_inline_code_elements(self):
        template = b"""<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file><body>
    <trans-unit id="1">
      <source><mrk mtype="seg" mid="1">Open <x id="1" /> file.</mrk></source>
      <target><mrk mtype="seg" mid="1">Old <x id="1" /> target.</mrk></target>
    </trans-unit>
  </body></file>
</xliff>"""

        updated = create_translated_bilingual_file(template, ["Odprite datoteko."])
        root = ET.fromstring(updated)
        target = root.find(".//{*}target")

        self.assertEqual("".join(target.itertext()).strip(), "Odprite datoteko.")
        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}x"))

    def test_fit_target_segments_merges_many_sentences_to_required_count(self):
        target_text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten."

        segments = fit_target_segments_to_count(target_text, 3)

        self.assertEqual(len(segments), 3)
        self.assertIn("One.", segments[0])
        self.assertIn("Ten.", segments[-1])


if __name__ == "__main__":
    unittest.main()
