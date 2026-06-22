from __future__ import annotations

import unittest

from ui_qa_export import build_qa_export_body


class QaExportDownloadTests(unittest.TestCase):
    def test_build_qa_export_body_includes_rule_based_and_gpt_report(self):
        body = build_qa_export_body(
            [
                {
                    "severity": "critical",
                    "category": "Empty target",
                    "message": "Target text is empty.",
                    "segment index": 3,
                    "source excerpt": "Source sentence.",
                    "target excerpt": "",
                }
            ],
            "Overall result: needs review.",
            "English",
            "Slovenian",
            "Legal",
        )

        self.assertIn("Language pair: English -> Slovenian", body)
        self.assertIn("CRITICAL | Empty target", body)
        self.assertIn("Target text is empty.", body)
        self.assertIn("GPT QA report", body)
        self.assertIn("Overall result: needs review.", body)

    def test_build_qa_export_body_empty_when_no_qa_exists(self):
        body = build_qa_export_body([], "", "English", "Slovenian", "General")

        self.assertEqual("", body)


if __name__ == "__main__":
    unittest.main()
