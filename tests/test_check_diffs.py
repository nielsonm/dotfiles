import os
import unittest
import tempfile
from pathlib import Path
from check_diffs import scan_repo_files, compare_file, generate_report

class TestCheckDiffs(unittest.TestCase):
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

    def test_generate_report(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            results = [
                {"status": "MATCH", "rel_path": ".bashrc", "repo_file": "a", "target_file": "b", "diff": []},
                {"status": "DIFFERENT", "rel_path": ".vimrc", "repo_file": "c", "target_file": "d", "diff": ["---", "+++", "-old", "+new"], "diff_count": 4},
                {"status": "MISSING_IN_TARGET", "rel_path": ".gitconfig", "repo_file": "e", "target_file": "f", "diff": []}
            ]
            report = generate_report(results, str(Path(tmp_dir) / "repo"), str(Path(tmp_dir) / "target"), summary_only=False, use_color=False)
            self.assertIn("Dotfiles Active Config Diff Report", report)
            self.assertIn("Total tracked configs checked : 3", report)
            self.assertIn("[MATCH]", report)
            self.assertIn("[DIFFERENT]", report)
            self.assertIn("[MISSING IN TARGET]", report)

if __name__ == "__main__":
    unittest.main()
