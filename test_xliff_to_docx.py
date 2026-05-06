from __future__ import annotations

import unittest

from xliff_to_docx import build_target_text_from_segments, create_docx_from_xliff_and_template, extract_xliff_target_segments


class XliffToDocxTests(unittest.TestCase):
    def test_extract_xliff_target_segments_simple(self):
        xliff_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
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
        segments = extract_xliff_target_segments(xliff_bytes)
        self.assertEqual(segments, ["Odprite datoteko.", "Shranite spremembe."])

    def test_extract_xliff_target_segments_no_namespace(self):
        xliff_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source>Open the file.</source>
        <target>Odprite datoteko.</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
        segments = extract_xliff_target_segments(xliff_bytes)
        self.assertEqual(segments, ["Odprite datoteko."])

    def test_extract_xliff_target_segments_empty_target(self):
        xliff_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source>Open the file.</source>
        <target></target>
      </trans-unit>
      <trans-unit id="2">
        <source>Save changes.</source>
        <target>Shranite spremembe.</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
        segments = extract_xliff_target_segments(xliff_bytes)
        self.assertEqual(segments, ["Shranite spremembe."])

    def test_extract_xliff_target_segments_no_targets(self):
        xliff_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source>Open the file.</source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
        segments = extract_xliff_target_segments(xliff_bytes)
        self.assertEqual(segments, [])

    def test_build_target_text_from_segments(self):
        segments = ["Hello world.", "How are you?"]
        text = build_target_text_from_segments(segments)
        self.assertEqual(text, "Hello world.\nHow are you?")

    def test_create_docx_from_xliff_and_template_success(self):
        # This test would require a real DOCX file, skipping for now
        pass

    def test_create_docx_from_xliff_and_template_no_targets(self):
        xliff_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.docx" source-language="en-US" target-language="sl-SI">
    <body>
      <trans-unit id="1">
        <source>Open the file.</source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
        template_docx_bytes = b"mock"
        with self.assertRaises(ValueError) as cm:
            create_docx_from_xliff_and_template(xliff_bytes, template_docx_bytes)
        self.assertIn("No usable target segments", str(cm.exception))