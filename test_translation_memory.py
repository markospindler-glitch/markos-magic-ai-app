from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from translation_memory import import_tm


class TranslationMemoryTests(unittest.TestCase):
    def test_import_sdltm_like_sqlite_memory(self):
        with tempfile.NamedTemporaryFile(suffix=".sdltm", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            connection = sqlite3.connect(temp_path)
            connection.execute("CREATE TABLE translation_units (source_text TEXT, target_text TEXT)")
            connection.execute(
                "INSERT INTO translation_units VALUES (?, ?)",
                ("Open the file.", "Odprite datoteko."),
            )
            connection.execute(
                "INSERT INTO translation_units VALUES (?, ?)",
                ("Save changes.", "Shranite spremembe."),
            )
            connection.commit()
            connection.close()

            entries = import_tm("memory.sdltm", temp_path.read_bytes())

            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["source"], "Open the file.")
            self.assertEqual(entries[0]["target"], "Odprite datoteko.")
        finally:
            try:
                temp_path.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
