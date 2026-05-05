from __future__ import annotations

import unittest

from deterministic_qa import run_rule_based_qa


class DeterministicQATests(unittest.TestCase):
    def test_empty_target_segment_is_critical(self):
        warnings = run_rule_based_qa(
            "First segment.\nSecond segment.",
            "First target.",
            [{"Segment": 1, "Source": "First segment.", "Target": "First target."}, {"Segment": 2, "Source": "Second segment.", "Target": ""}],
        )

        self.assertEqual(1, len(warnings))
        self.assertEqual("critical", warnings[0]["severity"])
        self.assertEqual("Empty target", warnings[0]["category"])
        self.assertEqual(2, warnings[0]["segment index"])

    def test_number_mismatch_is_reported(self):
        warnings = run_rule_based_qa("Pay 1,250 EUR by 03.05.2026.", "Pay 1,250 EUR by 04.05.2026.")

        self.assertEqual(1, len(warnings))
        self.assertEqual("warning", warnings[0]["severity"])
        self.assertEqual("Number mismatch", warnings[0]["category"])
        self.assertIn("03.05.2026", warnings[0]["message"])
        self.assertIn("04.05.2026", warnings[0]["message"])

    def test_url_and_email_mismatches_are_reported(self):
        warnings = run_rule_based_qa(
            "Contact support@example.com or visit https://example.com/help.",
            "Contact help@example.com or visit https://example.com.",
        )
        categories = {warning["category"] for warning in warnings}

        self.assertEqual({"Email mismatch", "URL mismatch"}, categories)
        self.assertTrue(all(warning["severity"] == "critical" for warning in warnings))

    def test_placeholder_mismatch_is_reported(self):
        warnings = run_rule_based_qa(
            "Hello {name}, your code is {{ code }} and value is %s.",
            "Hello {name}, your code is {{ value }} and value is %d.",
        )

        self.assertEqual(1, len(warnings))
        self.assertEqual("Placeholder mismatch", warnings[0]["category"])
        self.assertIn("{{ code }}", warnings[0]["message"])
        self.assertIn("%d", warnings[0]["message"])

    def test_matching_tokens_do_not_warn(self):
        warnings = run_rule_based_qa(
            "Email a@b.com, open www.example.com, enter {0}, then pay 100.",
            "Posljite na a@b.com, odprite www.example.com, vnesite {0}, nato placajte 100.",
        )

        self.assertEqual([], warnings)


if __name__ == "__main__":
    unittest.main()
