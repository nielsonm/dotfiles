import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from check_diffs import (
    scan_repo_files,
    compare_file,
    generate_report,
    format_diff_line,
    supports_color,
    colorize,
    Colors,
    main,
)


class TestCheckDiffs(unittest.TestCase):
    def test_supports_color_and_colorize(self):
        self.assertFalse(supports_color(no_color=True))
        self.assertTrue(supports_color(force_color=True))

        plain = colorize("test", Colors.OKGREEN, use_color=False)
        self.assertEqual(plain, "test")

        colored = colorize("test", Colors.OKGREEN, use_color=True)
        self.assertIn("\033[92m", colored)
        self.assertIn("\033[0m", colored)

    def test_scan_repo_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir) / "repo"
            repo.mkdir()
            (repo / ".bashrc").write_text("export TEST=1\n")
            (repo / ".vimrc").write_text("set number\n")
            (repo / "README.md").write_text("# Readme\n")

            ignores = {".git", ".gitignore", "README.md"}
            files = scan_repo_files(repo, ignores)

            rel_files = [str(f) for f in files]
            self.assertIn(".bashrc", rel_files)
            self.assertIn(".vimrc", rel_files)
            self.assertNotIn("README.md", rel_files)

    def test_compare_file_matching(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_file = tmp_path / "repo_file"
            target_file = tmp_path / "target_file"

            content = "line1\nline2\n"
            repo_file.write_text(content)
            target_file.write_text(content)

            result = compare_file(repo_file, target_file, ".bashrc")
            self.assertEqual(result["status"], "MATCH")
            self.assertEqual(result["diff"], [])

    def test_compare_file_different(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_file = tmp_path / "repo_file"
            target_file = tmp_path / "target_file"

            repo_file.write_text("line1\nline2_repo\n")
            target_file.write_text("line1\nline2_target\n")

            result = compare_file(repo_file, target_file, ".bashrc")
            self.assertEqual(result["status"], "DIFFERENT")
            self.assertTrue(len(result["diff"]) > 0)

    def test_compare_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_file = tmp_path / "repo_file"
            target_file = tmp_path / "non_existent_target"

            repo_file.write_text("line1\n")

            result = compare_file(repo_file, target_file, ".bashrc")
            self.assertEqual(result["status"], "MISSING_IN_TARGET")

    def test_compare_file_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_file = tmp_path / "repo_file"
            target_file = tmp_path / "target_dir_instead_of_file"
            repo_file.write_text("line1\n")
            target_file.mkdir()  # Causes read error

            result = compare_file(repo_file, target_file, ".bashrc")
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("error", result)

    def test_generate_report(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            results = [
                {"status": "MATCH", "rel_path": ".bashrc", "repo_file": "a", "target_file": "b", "diff": []},
                {"status": "DIFFERENT", "rel_path": ".vimrc", "repo_file": "c", "target_file": "d", "diff": ["---", "+++", "@@", "-old", "+new"], "diff_count": 5},
                {"status": "MISSING_IN_TARGET", "rel_path": ".gitconfig", "repo_file": "e", "target_file": "f", "diff": []},
                {"status": "ERROR", "rel_path": ".tmux.conf", "repo_file": "g", "target_file": "h", "error": "Permission denied", "diff": []},
            ]
            report = generate_report(results, str(Path(tmp_dir) / "repo"), str(Path(tmp_dir) / "target"), summary_only=False, use_color=False)
            self.assertIn("Dotfiles Active Config Diff Report", report)
            self.assertIn("Total tracked configs checked : 4", report)
            self.assertIn("[MATCH]", report)
            self.assertIn("[DIFFERENT]", report)
            self.assertIn("[MISSING IN TARGET]", report)
            self.assertIn("[ERROR]", report)

    def test_generate_report_summary_only(self):
        results = [
            {"status": "DIFFERENT", "rel_path": ".vimrc", "repo_file": "c", "target_file": "d", "diff": ["-old", "+new"], "diff_count": 2}
        ]
        report = generate_report(results, "/repo", "/target", summary_only=True, use_color=False)
        self.assertIn("FILE STATUSES:", report)
        self.assertNotIn("DETAILED UNIFIED DIFFS:", report)

    def test_format_diff_line(self):
        self.assertEqual(format_diff_line("+added", use_color=False), "+added")
        self.assertIn("\033[92m", format_diff_line("+added", use_color=True))
        self.assertIn("\033[91m", format_diff_line("-deleted", use_color=True))
        self.assertIn("\033[96m", format_diff_line("@@ -1,2 +1,2 @@", use_color=True))
        self.assertIn("\033[1m", format_diff_line("--- old", use_color=True))
        self.assertIn("\033[1m", format_diff_line("+++ new", use_color=True))
        self.assertEqual(format_diff_line(" normal line", use_color=True), " normal line")

    def test_main_cli_default_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo = tmp_path / "repo"
            target = tmp_path / "target"
            repo.mkdir()
            target.mkdir()

            (repo / ".bashrc").write_text("export A=1\n")
            (target / ".bashrc").write_text("export A=2\n")

            test_args = ["check_diffs.py", "-r", str(repo), "-t", str(target), "--summary-only", "--no-color"]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                output = captured.getvalue()
                self.assertIn("Dotfiles Active Config Diff Report", output)
                self.assertIn(".bashrc", output)

    def test_main_cli_json_and_output_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo = tmp_path / "repo"
            target = tmp_path / "target"
            repo.mkdir()
            target.mkdir()

            (repo / ".bashrc").write_text("export A=1\n")
            (target / ".bashrc").write_text("export A=1\n")
            output_file = tmp_path / "report.json"

            test_args = ["check_diffs.py", "-r", str(repo), "-t", str(target), "--json", "-o", str(output_file)]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                self.assertTrue(output_file.exists())
                data = json.loads(output_file.read_text())
                self.assertEqual(data["summary"]["matched"], 1)

    def test_main_cli_filter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo = tmp_path / "repo"
            target = tmp_path / "target"
            repo.mkdir()
            target.mkdir()

            (repo / ".bashrc").write_text("export A=1\n")
            (repo / ".vimrc").write_text("set number\n")
            (target / ".bashrc").write_text("export A=1\n")
            (target / ".vimrc").write_text("set number\n")

            test_args = ["check_diffs.py", "-r", str(repo), "-t", str(target), "-f", ".vimrc", "--no-color"]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                output = captured.getvalue()
                self.assertIn(".vimrc", output)
                self.assertNotIn(".bashrc", output)

    def test_main_cli_invalid_directories(self):
        with patch("sys.argv", ["check_diffs.py", "-r", "/nonexistent_repo"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
