from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile
import unittest

from batch_files import (
    build_combined_source_text,
    create_batch_output_zip,
    file_end_marker,
    file_start_marker,
    make_source_file_record,
    split_text_by_file_markers,
)


class BatchFileTests(unittest.TestCase):
    def test_combined_source_text_adds_stable_markers(self):
        records = [
            make_source_file_record("first.txt", b"First", "First source"),
            make_source_file_record("second.txt", b"Second", "Second source"),
        ]

        combined = build_combined_source_text(records)

        self.assertIn(file_start_marker(1), combined)
        self.assertIn(file_end_marker(2), combined)
        self.assertIn("First source", combined)
        self.assertIn("Second source", combined)

    def test_split_text_by_file_markers_returns_each_file(self):
        final_text = (
            f"{file_start_marker(1)}\nPrvi prevod\n{file_end_marker(1)}\n\n"
            f"{file_start_marker(2)}\nDrugi prevod\n{file_end_marker(2)}"
        )

        parts = split_text_by_file_markers(final_text, 2)

        self.assertEqual("Prvi prevod", parts[1])
        self.assertEqual("Drugi prevod", parts[2])

    def test_batch_zip_exports_one_text_file_per_source(self):
        records = [
            make_source_file_record("first.txt", b"First", "First source"),
            make_source_file_record("second.txt", b"Second", "Second source"),
        ]
        final_text = (
            f"{file_start_marker(1)}\nPrvi prevod\n{file_end_marker(1)}\n\n"
            f"{file_start_marker(2)}\nDrugi prevod\n{file_end_marker(2)}"
        )

        zip_bytes, summary = create_batch_output_zip(records, final_text)

        self.assertEqual(2, summary["exported"])
        with ZipFile(BytesIO(zip_bytes), "r") as archive:
            self.assertEqual({"first_target.txt", "second_target.txt"}, set(archive.namelist()))
            self.assertIn("Prvi prevod", archive.read("first_target.txt").decode("utf-8-sig"))
            self.assertIn("Drugi prevod", archive.read("second_target.txt").decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
