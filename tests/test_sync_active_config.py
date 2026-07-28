import os
import unittest
import tempfile
from pathlib import Path
from sync_active_config import sanitize_branch_name, get_machine_name, sync_active_configs

class TestSyncActiveConfig(unittest.TestCase):
    def test_sanitize_branch_name(self):
        self.assertEqual(sanitize_branch_name("My-MacBook.local"), "My-MacBook.local")
        self.assertEqual(sanitize_branch_name("test@machine!name#1"), "test-machine-name-1")
        self.assertEqual(sanitize_branch_name("invalid--branch--name"), "invalid-branch-name")
        self.assertEqual(sanitize_branch_name("-leading-trailing-"), "leading-trailing")

    def test_get_machine_name(self):
        old_hostname = os.environ.get("HOSTNAME")
        try:
            os.environ["HOSTNAME"] = "test-host"
            name = get_machine_name()
            self.assertIsInstance(name, str)
            self.assertTrue(len(name) > 0)
        finally:
            if old_hostname is not None:
                os.environ["HOSTNAME"] = old_hostname
            else:
                os.environ.pop("HOSTNAME", None)

    def test_sync_active_configs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source = tmp_path / "source"
            repo = tmp_path / "repo"
            
            source.mkdir()
            repo.mkdir()
            
            # Create matching files in source and repo
            (source / ".bashrc").write_text("export MODIFIED=1\n")
            (repo / ".bashrc").write_text("export MODIFIED=0\n")
            
            (source / ".vimrc").write_text("set number\n")
            (repo / ".vimrc").write_text("set number\n")
            
            ignores = {".git"}
            checked, updated = sync_active_configs(source, repo, ignores)
            
            self.assertIn(".bashrc", checked)
            self.assertIn(".vimrc", checked)
            self.assertIn(".bashrc", updated)
            self.assertNotIn(".vimrc", updated)
            
            # Verify file was updated in repo
            self.assertEqual((repo / ".bashrc").read_text(), "export MODIFIED=1\n")

if __name__ == "__main__":
    unittest.main()
