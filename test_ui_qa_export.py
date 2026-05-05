from __future__ import annotations

import unittest

import ui_qa_export


class UIQAExportTests(unittest.TestCase):
    def test_render_function_is_available(self):
        self.assertTrue(callable(ui_qa_export.render_qa_export_tab))


if __name__ == "__main__":
    unittest.main()
