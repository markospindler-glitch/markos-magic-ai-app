from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import project_repository
from error_utils import user_friendly_message
from state_manager import ensure_state_defaults, get_current_project_snapshot, reset_project_state


class StateManagerTests(unittest.TestCase):
    def test_ensure_state_defaults_adds_common_keys(self):
        state = {}

        ensure_state_defaults(state)

        self.assertEqual("", state["source_text"])
        self.assertEqual("", state["analysis_report"])
        self.assertEqual("English", state["source_language"])
        self.assertEqual("Slovenian", state["target_language"])
        self.assertEqual("General", state["text_type"])

    def test_reset_project_state_clears_project_fields_and_increments_editor_version(self):
        state = {
            "source_text": "Existing source",
            "translated_text": "Existing target",
            "bilingual_review_editor_version": 4,
            "show_price_list": True,
        }

        reset_project_state(state)

        self.assertEqual("", state["source_text"])
        self.assertEqual("", state["translated_text"])
        self.assertEqual(5, state["bilingual_review_editor_version"])
        self.assertTrue(state["show_price_list"])

    def test_project_snapshot_encodes_file_bytes(self):
        state = {"project_name": "Demo", "source_file_bytes": b"abc", "sdlxliff_template_bytes": b"xyz"}

        snapshot = get_current_project_snapshot(state)

        self.assertEqual("Demo", snapshot["project_name"])
        self.assertEqual("YWJj", snapshot["source_file_bytes_b64"])
        self.assertEqual("eHl6", snapshot["sdlxliff_template_bytes_b64"])


class ProjectRepositoryStabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_projects_dir = project_repository.PROJECTS_DIR
        project_repository.PROJECTS_DIR = Path(self.temp_dir.name) / "projects"

    def tearDown(self):
        project_repository.PROJECTS_DIR = self.old_projects_dir
        self.temp_dir.cleanup()

    def test_load_project_fills_missing_optional_fields(self):
        project_repository.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path = project_repository.PROJECTS_DIR / "old_project.json"
        path.write_text(
            json.dumps({"project_name": "Old", "saved_at": "2026-01-01 10:00", "state": {"source_text": "Hello"}}),
            encoding="utf-8",
        )

        state = project_repository.load_project(str(path))

        self.assertEqual("Hello", state["source_text"])
        self.assertEqual("", state["qa_report"])
        self.assertEqual("", state["source_file_bytes_b64"])

    def test_corrupted_project_json_has_clear_error(self):
        project_repository.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path = project_repository.PROJECTS_DIR / "broken.json"
        path.write_text("{bad json", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "corrupted"):
            project_repository.load_project(str(path))

    def test_update_project_creates_backup(self):
        path = project_repository.save_project("Demo", {"source_text": "Before"})

        project_repository.update_project(str(path), "Demo", {"source_text": "After"})

        backups = list(project_repository.PROJECTS_DIR.glob("*.backup-*.json"))
        self.assertEqual(1, len(backups))
        self.assertEqual("After", project_repository.load_project(str(path))["source_text"])


class ErrorUtilsTests(unittest.TestCase):
    def test_user_friendly_message_falls_back(self):
        self.assertIn("file could not be imported", user_friendly_message("file_import"))
        self.assertEqual("Something went wrong. Please try again.", user_friendly_message("unknown"))


if __name__ == "__main__":
    unittest.main()
