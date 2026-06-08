import json
from pathlib import Path
import tempfile
import unittest

from promptset_audit import audit_file, split_file


class PromptsetAuditTests(unittest.TestCase):
    def dataset(self, rows: list[object]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "prompts.jsonl"
        path.write_text(
            "\n".join(json.dumps(row) if not isinstance(row, str) else row for row in rows) + "\n",
            encoding="utf-8",
        )
        return path

    def test_reports_invalid_and_duplicate_rows(self) -> None:
        path = self.dataset(
            [
                {"prompt": "A glass molecule", "width": 1024, "height": 1024},
                {"prompt": "  a GLASS molecule  ", "width": 1025},
                {"negative_prompt": "blur"},
                "{invalid",
            ]
        )
        report = audit_file(path)
        codes = {finding.code for finding in report.findings}
        self.assertIn("duplicate-prompt", codes)
        self.assertIn("missing-prompt", codes)
        self.assertIn("invalid-json", codes)
        self.assertIn("unaligned-width", codes)

    def test_split_is_deterministic_and_deduplicates(self) -> None:
        path = self.dataset(
            [
                {"prompt": "alpha"},
                {"prompt": "beta"},
                {"prompt": "gamma"},
                {"prompt": "ALPHA"},
            ]
        )
        first = Path(tempfile.mkdtemp())
        second = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(first))
        self.addCleanup(lambda: __import__("shutil").rmtree(second))
        _, _, first_counts = split_file(path, first, validation_ratio=0.5, salt="test")
        _, _, second_counts = split_file(path, second, validation_ratio=0.5, salt="test")
        self.assertEqual(first_counts, second_counts)
        self.assertEqual(first_counts["duplicates_skipped"], 1)
        self.assertEqual((first / "train.jsonl").read_text(), (second / "train.jsonl").read_text())
        self.assertEqual((first / "validation.jsonl").read_text(), (second / "validation.jsonl").read_text())

    def test_rejects_invalid_ratio(self) -> None:
        path = self.dataset([{"prompt": "alpha"}])
        with self.assertRaises(ValueError):
            split_file(path, tempfile.mkdtemp(), validation_ratio=1)


if __name__ == "__main__":
    unittest.main()

