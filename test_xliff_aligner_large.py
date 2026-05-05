from __future__ import annotations

import json
import re
import unittest
from unittest.mock import patch

from xliff_aligner import align_fixed_source_segments, align_for_xliff


class LargeXliffAlignerTests(unittest.TestCase):
    def test_large_alignment_uses_order_when_segment_counts_match(self):
        source = "\n".join(f"Source sentence {index}." for index in range(1, 66))
        target = "\n".join(f"Target sentence {index}." for index in range(1, 66))

        with patch("xliff_aligner.ask_openai", side_effect=AssertionError("GPT should not be called")) as mocked:
            rows = align_for_xliff(source, target, "English", "Slovenian")

        self.assertEqual(65, len(rows))
        self.assertEqual("Source sentence 1.", rows[0]["source"])
        self.assertEqual("Target sentence 1.", rows[0]["target"])
        self.assertEqual(90, rows[0]["confidence"])
        self.assertEqual("65", rows[-1]["id"])
        mocked.assert_not_called()

    def test_fixed_source_segments_preserve_original_bilingual_segments(self):
        source_segments = [
            "This is one original SDLXLIFF segment. It has two sentences.",
            "This is another original segment.",
        ]
        target = "To je en izvirni segment SDLXLIFF. Ima dva stavka.\nTo je drug izvirni segment."

        with patch("xliff_aligner.ask_openai", return_value=json.dumps([
            {
                "id": "1",
                "source": source_segments[0],
                "target": "To je en izvirni segment SDLXLIFF. Ima dva stavka.",
                "target_segment_ids": [1, 2],
                "confidence": 95,
                "note": "",
            },
            {
                "id": "2",
                "source": source_segments[1],
                "target": "To je drug izvirni segment.",
                "target_segment_ids": [3],
                "confidence": 95,
                "note": "",
            },
        ])):
            rows = align_fixed_source_segments(source_segments, target, "English", "Slovenian")

        self.assertEqual(2, len(rows))
        self.assertEqual(source_segments[0], rows[0]["source"])
        self.assertEqual(source_segments[1], rows[1]["source"])

    def test_large_alignment_runs_in_chunks_when_counts_differ(self):
        source = "\n".join(f"Source sentence {index}." for index in range(1, 82))
        target = "\n".join(f"Target sentence {index}." for index in range(1, 89))

        with patch("xliff_aligner.ask_openai", side_effect=_fake_alignment_answer) as mocked:
            rows = align_for_xliff(source, target, "English", "Slovenian")

        self.assertEqual(81, len(rows))
        self.assertEqual("Source sentence 1.", rows[0]["source"])
        self.assertTrue(rows[0]["target"].startswith("Target sentence"))
        self.assertEqual("81", rows[-1]["id"])
        self.assertGreater(mocked.call_count, 1)

    def test_large_alignment_falls_back_to_low_confidence_rows_when_gpt_fails(self):
        source = "\n".join(f"Source sentence {index}." for index in range(1, 63))
        target = "\n".join(f"Target sentence {index}." for index in range(1, 68))

        with patch("xliff_aligner.ask_openai", side_effect=RuntimeError("empty response")):
            rows = align_for_xliff(source, target, "English", "Slovenian")

        self.assertEqual(62, len(rows))
        self.assertEqual(40, rows[0]["confidence"])
        self.assertIn("fallback", rows[0]["note"])
        self.assertEqual("62", rows[-1]["id"])


def _fake_alignment_answer(system_prompt: str, user_prompt: str, model: str) -> str:
    del system_prompt, model
    source_block = user_prompt.split("Source segments:", 1)[1].split("Target candidate segments:", 1)[0]
    target_block = user_prompt.split("Target candidate segments:", 1)[1]
    sources = _numbered_lines(source_block)
    targets = _numbered_lines(target_block)
    rows = []
    for index, source in enumerate(sources, start=1):
        rows.append(
            {
                "id": str(index),
                "source": source,
                "target": targets[index - 1] if index <= len(targets) else "",
                "target_segment_ids": [index],
                "confidence": 95,
                "note": "",
            }
        )
    return json.dumps(rows)


def _numbered_lines(text: str) -> list[str]:
    values = []
    for line in text.splitlines():
        match = re.match(r"\s*\d+\.\s+(.*)", line)
        if match:
            values.append(match.group(1).strip())
    return values


if __name__ == "__main__":
    unittest.main()
