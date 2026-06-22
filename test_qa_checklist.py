from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import patch

from openpyxl import load_workbook

from qa_checklist import (
    apply_approved_qa_corrections,
    approved_checklist_rows,
    build_qa_checklist_rows,
    create_qa_checklist_xlsx,
    read_qa_checklist_xlsx,
)


class QaChecklistTests(unittest.TestCase):
    def test_build_qa_checklist_rows_from_rule_and_gpt_qa(self):
        rows = build_qa_checklist_rows(
            [
                {
                    "severity": "critical",
                    "category": "Empty target",
                    "message": "Target is empty.",
                    "source excerpt": "Hello.",
                    "target excerpt": "",
                }
            ],
            "Overall result\n- Terminology should be improved.",
        )

        self.assertEqual("R1", rows[0]["ID"])
        self.assertEqual("Empty target", rows[0]["Category"])
        self.assertTrue(any(row["ID"].startswith("G") for row in rows))

    def test_qa_checklist_excel_round_trip_reads_approved_rows(self):
        xlsx_bytes = create_qa_checklist_xlsx(
            [
                {
                    "severity": "warning",
                    "category": "Number mismatch",
                    "message": "Review number.",
                    "source excerpt": "Pay 10.",
                    "target excerpt": "Placajte 11.",
                }
            ],
            "",
        )
        workbook = load_workbook(BytesIO(xlsx_bytes))
        sheet = workbook.active
        sheet["B9"] = "Yes"
        sheet["H9"] = "Change the target number to 10."
        edited = BytesIO()
        workbook.save(edited)

        rows = read_qa_checklist_xlsx(edited.getvalue())
        approved = approved_checklist_rows(rows)

        self.assertEqual(1, len(approved))
        self.assertEqual("Yes", approved[0]["Approved"])
        self.assertEqual("Change the target number to 10.", approved[0]["PM correction / instruction"])

    def test_qa_checklist_excel_is_formatted_for_pm_use(self):
        xlsx_bytes = create_qa_checklist_xlsx(
            [
                {
                    "severity": "critical",
                    "category": "Empty target",
                    "message": "Target is empty.",
                    "source excerpt": "Hello.",
                    "target excerpt": "",
                }
            ],
            "",
        )
        workbook = load_workbook(BytesIO(xlsx_bytes))
        sheet = workbook.active

        self.assertEqual("TranslatAI QA Correction Checklist", sheet["A1"].value)
        self.assertIn("How to use this checklist", sheet["A2"].value)
        self.assertEqual("Approved", sheet["B8"].value)
        self.assertEqual("A9", sheet.freeze_panes)
        self.assertEqual("A8:H9", sheet.auto_filter.ref)
        self.assertGreaterEqual(len(sheet.data_validations.dataValidation), 1)
        self.assertEqual("critical", sheet["C9"].value)
        self.assertIsNotNone(sheet["C9"].fill.fgColor.rgb)

    def test_apply_approved_qa_corrections_sends_only_approved_rows(self):
        approved_rows = [
            {
                "ID": "R1",
                "Approved": "Yes",
                "Severity": "critical",
                "Category": "Terminology",
                "Issue": "Wrong term.",
                "Source excerpt": "Source",
                "Target excerpt": "Old target",
                "PM correction / instruction": "Use the approved client term.",
            }
        ]
        with patch("qa_checklist.ask_openai", return_value="Corrected target.") as mocked:
            result = apply_approved_qa_corrections(
                "Source text.",
                "Current target.",
                approved_rows,
                "Slovenian",
                "Legal",
            )

        self.assertEqual("Corrected target.", result)
        prompt = mocked.call_args.args[1]
        self.assertIn("Apply only approved checklist items", prompt)
        self.assertIn("Use the approved client term.", prompt)
        self.assertIn("Current target.", prompt)


if __name__ == "__main__":
    unittest.main()
