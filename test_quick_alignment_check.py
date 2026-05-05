from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from xliff_aligner import quick_alignment_check


class QuickAlignmentCheckTests(unittest.TestCase):
    def test_quick_alignment_updates_only_low_confidence_rows(self):
        rows = [
            {"id": "1", "source": "Source 1.", "target": "Target 1.", "confidence": 96, "note": ""},
            {"id": "2", "source": "Source 2.", "target": "Wrong target.", "confidence": 62, "note": "Review."},
            {"id": "3", "source": "Source 3.", "target": "Target 3.", "confidence": 94, "note": ""},
        ]

        with patch("xliff_aligner.ask_openai", return_value=json.dumps([
            {"id": "2", "target": "Target 2.", "confidence": 95, "note": "Fixed nearby one-row issue."}
        ])) as mocked:
            improved = quick_alignment_check(rows, "English", "Slovenian")

        self.assertEqual("Target 1.", improved[0]["target"])
        self.assertEqual("Target 2.", improved[1]["target"])
        self.assertEqual(95, improved[1]["confidence"])
        self.assertEqual("Target 3.", improved[2]["target"])
        prompt = mocked.call_args.args[1]
        self.assertIn("Only update rows with these ids: 2", prompt)
        self.assertIn('"needs_review": true', prompt)

    def test_quick_alignment_noops_when_all_rows_are_high_confidence(self):
        rows = [
            {"id": "1", "source": "Source 1.", "target": "Target 1.", "confidence": 96, "note": ""},
            {"id": "2", "source": "Source 2.", "target": "Target 2.", "confidence": 91, "note": ""},
        ]

        with patch("xliff_aligner.ask_openai", side_effect=AssertionError("GPT should not be called")):
            improved = quick_alignment_check(rows, "English", "Slovenian")

        self.assertEqual(rows, improved)


if __name__ == "__main__":
    unittest.main()
