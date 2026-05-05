from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import active_project
from state_manager import apply_project_snapshot, get_current_project_snapshot


class ActiveProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_path = active_project.ACTIVE_PROJECT_PATH
        active_project.ACTIVE_PROJECT_PATH = Path(self.temp_dir.name) / "data" / "current_project.json"

    def tearDown(self):
        active_project.ACTIVE_PROJECT_PATH = self.old_path
        self.temp_dir.cleanup()

    def test_save_and_load_active_project(self):
        state = {
            "project_name": "Active job",
            "source_text": "Hello",
            "translated_text": "Pozdravljeni",
            "source_file_bytes_b64": "YWJj",
        }

        path = active_project.save_active_project(state)
        loaded = active_project.load_active_project()

        self.assertTrue(path.exists())
        self.assertEqual("Active job", loaded["project_name"])
        self.assertEqual("Hello", loaded["source_text"])
        self.assertEqual("YWJj", loaded["source_file_bytes_b64"])
        self.assertIn("qa_report", loaded)

    def test_load_missing_active_project_returns_empty_dict(self):
        self.assertEqual({}, active_project.load_active_project())

    def test_apply_project_snapshot_restores_encoded_file_bytes(self):
        snapshot = {
            "source_text": "Hello",
            "source_file_bytes_b64": "YWJj",
            "sdlxliff_template_bytes_b64": "eHl6",
        }
        state = {}

        apply_project_snapshot(snapshot, state)

        self.assertEqual("Hello", state["source_text"])
        self.assertEqual(b"abc", state["source_file_bytes"])
        self.assertEqual(b"xyz", state["sdlxliff_template_bytes"])

    def test_current_project_snapshot_round_trips_with_active_project(self):
        state = {"project_name": "Roundtrip", "source_file_bytes": b"abc"}
        snapshot = get_current_project_snapshot(state)

        active_project.save_active_project(snapshot)
        restored_state = {}
        apply_project_snapshot(active_project.load_active_project(), restored_state)

        self.assertEqual("Roundtrip", restored_state["project_name"])
        self.assertEqual(b"abc", restored_state["source_file_bytes"])


if __name__ == "__main__":
    unittest.main()
