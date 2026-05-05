from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import prompt_archive


class PromptArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_archive_path = prompt_archive.ARCHIVE_PATH
        prompt_archive.ARCHIVE_PATH = Path(self.temp_dir.name) / "prompt_archive.json"

    def tearDown(self):
        prompt_archive.ARCHIVE_PATH = self.old_archive_path
        self.temp_dir.cleanup()

    def test_update_saved_prompt(self):
        saved = prompt_archive.save_prompt_to_archive(
            "Original prompt",
            "English",
            "Slovenian",
            "Legal",
            "Legal template",
        )

        updated = prompt_archive.update_prompt_in_archive(
            saved["id"],
            "Updated prompt",
            "English",
            "German",
            "Business",
            "Updated template",
        )
        entries = prompt_archive.load_prompt_archive()

        self.assertEqual(saved["id"], updated["id"])
        self.assertEqual("Updated prompt", entries[0]["prompt"])
        self.assertEqual("German", entries[0]["target_language"])
        self.assertEqual("Updated template", entries[0]["title"])
        self.assertIn("updated_at", entries[0])

    def test_update_missing_prompt_id_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "Load or select"):
            prompt_archive.update_prompt_in_archive("", "Prompt", "English", "Slovenian", "General")

    def test_update_unknown_prompt_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "could not be found"):
            prompt_archive.update_prompt_in_archive("missing", "Prompt", "English", "Slovenian", "General")


if __name__ == "__main__":
    unittest.main()
