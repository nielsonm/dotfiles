import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sync_active_config import (
    sanitize_branch_name,
    get_machine_name,
    sync_active_configs,
    run_cmd,
    setup_cron_job,
    main,
)


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

    def test_run_cmd(self):
        res = run_cmd(["echo", "hello"])
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "hello")

        with self.assertRaises(RuntimeError):
            run_cmd(["false"], check=True)

    def test_sync_active_configs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source = tmp_path / "source"
            repo = tmp_path / "repo"

            source.mkdir()
            repo.mkdir()

            (source / ".bashrc").write_text("export MODIFIED=1\n")
            (repo / ".bashrc").write_text("export MODIFIED=0\n")

            (source / ".vimrc").write_text("set number\n")
            (repo / ".vimrc").write_text("set number\n")

            ignores = {".git"}
            checked, updated, blocked = sync_active_configs(source, repo, ignores, skip_secrets=False)

            self.assertIn(".bashrc", checked)
            self.assertIn(".vimrc", checked)
            self.assertIn(".bashrc", updated)
            self.assertNotIn(".vimrc", updated)
            self.assertEqual(len(blocked), 0)

            self.assertEqual((repo / ".bashrc").read_text(), "export MODIFIED=1\n")

    def test_sync_active_configs_blocks_secrets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source = tmp_path / "source"
            repo = tmp_path / "repo"

            source.mkdir()
            repo.mkdir()

            (source / ".bashrc").write_text("export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n")
            (repo / ".bashrc").write_text("export AWS_ACCESS_KEY_ID=old\n")

            (source / ".vimrc").write_text("set number\n")
            (repo / ".vimrc").write_text("set number\n")

            ignores = {".git"}
            checked, updated, blocked = sync_active_configs(source, repo, ignores, skip_secrets=True)

            self.assertIn(".bashrc", checked)
            self.assertIn(".bashrc", blocked)
            self.assertNotIn(".bashrc", updated)
            self.assertEqual((repo / ".bashrc").read_text(), "export AWS_ACCESS_KEY_ID=old\n")

    @patch("sync_active_config.run_cmd")
    @patch("subprocess.run")
    def test_setup_cron_job(self, mock_subproc, mock_run_cmd):
        # 1. When cron already contains script
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="0 9 * * * /path/to/script\n")
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            setup_cron_job("/path/to/script")
        self.assertIn("already installed", captured.getvalue())

        # 2. When cron does not contain script
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="0 8 * * * other_job\n")
        mock_subproc.return_value = MagicMock(returncode=0, stderr="")
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            setup_cron_job("/path/to/new_script")
        self.assertIn("Successfully added daily cron job", captured.getvalue())

    def test_main_cli_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source = tmp_path / "source"
            repo = tmp_path / "repo"
            source.mkdir()
            repo.mkdir()

            (source / ".bashrc").write_text("export TEST=1\n")
            (repo / ".bashrc").write_text("export TEST=0\n")

            test_args = ["sync_active_config.py", "-s", str(source), "-r", str(repo), "--dry-run"]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                output = captured.getvalue()
                self.assertIn("Dotfiles Active Config Sync", output)
                self.assertIn("[Dry Run]", output)

    @patch("sync_active_config.run_cmd")
    def test_main_cli_git_operations_mocked(self, mock_run_cmd):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source = tmp_path / "source"
            repo = tmp_path / "repo"
            source.mkdir()
            repo.mkdir()

            (source / ".bashrc").write_text("export TEST=1\n")
            (repo / ".bashrc").write_text("export TEST=1\n")

            # Mock responses for git calls
            def fake_run_cmd(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                mock_res = MagicMock()
                mock_res.returncode = 0
                if "rev-parse" in cmd_str:
                    mock_res.stdout = "main\n"
                elif "branch --list" in cmd_str:
                    mock_res.stdout = ""
                elif "status --porcelain" in cmd_str:
                    mock_res.stdout = " M .bashrc\n"
                else:
                    mock_res.stdout = ""
                    mock_res.stderr = ""
                return mock_res

            mock_run_cmd.side_effect = fake_run_cmd

            test_args = ["sync_active_config.py", "-s", str(source), "-r", str(repo), "-b", "my-test-branch", "--no-push"]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                output = captured.getvalue()
                self.assertIn("Target Branch  : my-test-branch", output)
                self.assertIn("Sync complete!", output)

    def test_main_cli_invalid_directories(self):
        with patch("sys.argv", ["sync_active_config.py", "-r", "/nonexistent_repo", "-s", "/nonexistent_source"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
