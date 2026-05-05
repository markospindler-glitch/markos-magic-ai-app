from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from sdlxliff_pipeline import (
    create_translated_sdlxliff,
    extract_editable_segments,
    validate_and_repair_protected_translation,
    validate_and_repair_sdlxliff_translations,
)


SAMPLE_SDLXLIFF = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0"
       version="1.2" sdl:version="1.0">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <sdl:seg-defs>
      <sdl:seg id="1" />
      <sdl:seg id="2" />
      <sdl:seg id="3" />
    </sdl:seg-defs>
    <body>
      <trans-unit id="1">
        <source><mrk mtype="seg" mid="1">Open <x id="fmt1" /> file.</mrk></source>
        <target><mrk mtype="seg" mid="1">Old <x id="fmt1" /> target.</mrk></target>
      </trans-unit>
      <trans-unit id="2">
        <source><mrk mtype="seg" mid="2">Save changes.</mrk></source>
      </trans-unit>
      <trans-unit id="3" translate="no">
        <source><mrk mtype="seg" mid="3">Locked text.</mrk></source>
        <target><mrk mtype="seg" mid="3">Zaklenjeno besedilo.</mrk></target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


class SdlxliffPipelineTests(unittest.TestCase):
    def test_extract_insert_and_save_valid_sdlxliff(self):
        segments = extract_editable_segments(SAMPLE_SDLXLIFF)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].segment_id, "1")
        self.assertEqual(segments[0].source_text, "Open file.")
        self.assertEqual(segments[0].protected_source_text, "Open [[SEG_1_TAG_1]] file.")
        self.assertEqual(segments[1].source_text, "Save changes.")

        output = create_translated_sdlxliff(
            SAMPLE_SDLXLIFF,
            ["Odprite [[SEG_1_TAG_1]] datoteko.", "Shranite spremembe."],
        )
        root = ET.fromstring(output)
        editable_targets = []
        editable_sources = []
        for unit in root.findall(".//{*}trans-unit"):
            if unit.get("translate") == "no":
                continue
            editable_sources.append(unit.find(".//{*}source"))
            editable_targets.append(unit.find(".//{*}target"))

        self.assertEqual(len(editable_sources), len(editable_targets))
        self.assertEqual(len(editable_targets), 2)
        self.assertEqual(
            [" ".join("".join(target.itertext()).split()) for target in editable_targets],
            ["Odprite datoteko.", "Shranite spremembe."],
        )
        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}x"))
        self.assertIn(b"xmlns:sdl=", output)
        self.assertIn(b"Locked text.", output)
        self.assertIn(b"Zaklenjeno besedilo.", output)

    def test_rejects_unsupported_sdlxliff_structure(self):
        with self.assertRaisesRegex(ValueError, "no trans-unit"):
            create_translated_sdlxliff(b"<xliff><file /></xliff>", ["Test"])

    def test_auto_repairs_translation_with_missing_placeholder_token(self):
        output = create_translated_sdlxliff(SAMPLE_SDLXLIFF, ["Odprite datoteko.", "Shranite spremembe."])
        root = ET.fromstring(output)
        first_target = root.find(".//{*}trans-unit[@id='1']/{*}target")

        self.assertEqual(" ".join("".join(first_target.itertext()).split()), "Odprite datoteko.")
        self.assertIsNotNone(root.find(".//{*}trans-unit[@id='1']/{*}target/{*}mrk/{*}x[@id='fmt1']"))

    def test_strict_mode_rejects_translation_with_missing_inline_token(self):
        with self.assertRaisesRegex(ValueError, "protected inline tag token"):
            create_translated_sdlxliff(
                SAMPLE_SDLXLIFF,
                ["Odprite datoteko.", "Shranite spremembe."],
                auto_repair_missing_tokens=False,
            )

    def test_protects_bold_and_italic_inline_tags(self):
        sample = _sample_with_source(
            '<mrk mtype="seg" mid="1">Use <g id="b">bold</g> and <g id="i">italic</g>.</mrk>'
        )
        segments = extract_editable_segments(sample)

        self.assertEqual(
            segments[0].protected_source_text,
            "Use [[SEG_1_TAG_1_OPEN]]bold[[SEG_1_TAG_1_CLOSE]] and [[SEG_1_TAG_2_OPEN]]italic[[SEG_1_TAG_2_CLOSE]].",
        )
        output = create_translated_sdlxliff(
            sample,
            ["Uporabite [[SEG_1_TAG_1_OPEN]]krepko[[SEG_1_TAG_1_CLOSE]] in [[SEG_1_TAG_2_OPEN]]lezece[[SEG_1_TAG_2_CLOSE]]."],
        )
        root = ET.fromstring(output)

        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}g[@id='b']"))
        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}g[@id='i']"))

    def test_auto_repairs_translation_with_missing_open_close_tokens(self):
        sample = _sample_with_source(
            '<mrk mtype="seg" mid="1">Use <g id="b">bold</g> text.</mrk>'
        )

        output = create_translated_sdlxliff(sample, ["Uporabite krepko besedilo."])
        root = ET.fromstring(output)
        target = root.find(".//{*}target")

        self.assertEqual(" ".join("".join(target.itertext()).split()), "Uporabite krepko besedilo.")
        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}g[@id='b']"))

    def test_rejects_unknown_protected_token(self):
        with self.assertRaisesRegex(ValueError, "unknown protected token"):
            create_translated_sdlxliff(SAMPLE_SDLXLIFF, ["Odprite [[SEG_1_TAG_99]] datoteko.", "Shranite spremembe."])

    def test_protects_placeholder_tags(self):
        sample = _sample_with_source('<mrk mtype="seg" mid="1">Click <x id="button" /> now.</mrk>')
        segments = extract_editable_segments(sample)

        self.assertEqual(segments[0].protected_source_text, "Click [[SEG_1_TAG_1]] now.")
        output = create_translated_sdlxliff(sample, ["Kliknite [[SEG_1_TAG_1]] zdaj."])
        root = ET.fromstring(output)

        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}x[@id='button']"))

    def test_protects_line_break_tags(self):
        sample = _sample_with_source('<mrk mtype="seg" mid="1">First<br id="1" />Second</mrk>')
        segments = extract_editable_segments(sample)

        self.assertEqual(segments[0].protected_source_text, "First[[SEG_1_TAG_1]]Second")
        output = create_translated_sdlxliff(sample, ["Prva[[SEG_1_TAG_1]]Druga"])
        root = ET.fromstring(output)

        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}br[@id='1']"))

    def test_protects_multiple_tags(self):
        sample = _sample_with_source(
            '<mrk mtype="seg" mid="1"><x id="1" />Open <x id="2" /> file <x id="3" />.</mrk>'
        )
        segments = extract_editable_segments(sample)

        self.assertEqual(segments[0].protected_source_text, "[[SEG_1_TAG_1]]Open [[SEG_1_TAG_2]] file [[SEG_1_TAG_3]].")
        output = create_translated_sdlxliff(sample, ["[[SEG_1_TAG_1]]Odprite [[SEG_1_TAG_2]] datoteko [[SEG_1_TAG_3]]."])
        root = ET.fromstring(output)

        self.assertEqual(len(root.findall(".//{*}target/{*}mrk/{*}x")), 3)

    def test_protects_nested_tags(self):
        sample = _sample_with_source(
            '<mrk mtype="seg" mid="1">Keep <g id="outer">outer <g id="inner">inner</g></g> text.</mrk>'
        )
        segments = extract_editable_segments(sample)

        self.assertEqual(
            segments[0].protected_source_text,
            "Keep [[SEG_1_TAG_1_OPEN]]outer [[SEG_1_TAG_2_OPEN]]inner[[SEG_1_TAG_2_CLOSE]][[SEG_1_TAG_1_CLOSE]] text.",
        )
        output = create_translated_sdlxliff(
            sample,
            [
                "Ohranite [[SEG_1_TAG_1_OPEN]]zunanje [[SEG_1_TAG_2_OPEN]]notranje[[SEG_1_TAG_2_CLOSE]][[SEG_1_TAG_1_CLOSE]] besedilo."
            ],
        )
        root = ET.fromstring(output)

        self.assertIsNotNone(root.find(".//{*}target/{*}mrk/{*}g[@id='outer']/{*}g[@id='inner']"))

    def test_validates_and_repairs_one_protected_translation_immediately(self):
        result = validate_and_repair_protected_translation(
            "Use [[SEG_7_TAG_1_OPEN]]bold[[SEG_7_TAG_1_CLOSE]] text.",
            "Uporabite krepko besedilo.",
            segment_index=7,
        )

        self.assertTrue(result.repaired)
        self.assertIn("[[SEG_7_TAG_1_OPEN]]", result.text)
        self.assertIn("[[SEG_7_TAG_1_CLOSE]]", result.text)

    def test_validates_all_sdlxliff_rows_before_export(self):
        approved = validate_and_repair_sdlxliff_translations(
            SAMPLE_SDLXLIFF,
            ["Odprite datoteko.", "Shranite spremembe."],
        )

        self.assertEqual(len(approved), 2)
        self.assertIn("[[SEG_1_TAG_1]]", approved[0])


def _sample_with_source(source_xml: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0"
       version="1.2" sdl:version="1.0">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source>{source_xml}</source>
        <target><mrk mtype="seg" mid="1">Old target.</mrk></target>
      </trans-unit>
    </body>
  </file>
</xliff>
""".encode("utf-8")


if __name__ == "__main__":
    unittest.main()
