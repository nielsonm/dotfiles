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
    stash_if_dirty,
    stash_pop_if_stashed,
    _print_sync_summary,
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

    def test_sync_active_configs_dry_run(self):
        """Verify dry_run=True reports changes without copying files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source   = tmp_path / "source"
            repo     = tmp_path / "repo"

            source.mkdir()
            repo.mkdir()

            (source / ".bashrc").write_text("export MODIFIED=1\n")
            (repo / ".bashrc").write_text("export MODIFIED=0\n")

            ignores = {".git"}
            checked, updated, blocked = sync_active_configs(
                source, repo, ignores, skip_secrets=False, dry_run=True,
            )

            self.assertIn(".bashrc", updated)
            # File should NOT have been copied
            self.assertEqual((repo / ".bashrc").read_text(), "export MODIFIED=0\n")

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
            source   = tmp_path / "source"
            repo     = tmp_path / "repo"
            source.mkdir()
            repo.mkdir()

            # Files must differ so the pre-flight check detects changes
            (source / ".bashrc").write_text("export TEST=1\n")
            (repo / ".bashrc").write_text("export TEST=0\n")

            call_log = []

            # Mock responses for git calls
            def fake_run_cmd(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                call_log.append(cmd_str)
                mock_res = MagicMock()
                mock_res.returncode = 0
                if "branch --list" in cmd_str:
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

            # Verify branch checkout happens before commit
            checkout_idx = next(i for i, c in enumerate(call_log) if "checkout" in c)
            commit_idx   = next(i for i, c in enumerate(call_log) if "commit" in c)
            self.assertLess(checkout_idx, commit_idx)

    def test_main_cli_invalid_directories(self):
        with patch("sys.argv", ["sync_active_config.py", "-r", "/nonexistent_repo", "-s", "/nonexistent_source"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("sync_active_config.run_cmd")
    def test_stash_if_dirty(self, mock_run_cmd):
        """Verify stash is created when working tree has changes."""
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout=" M .bashrc\n")
        result = stash_if_dirty("/fake/repo")
        self.assertTrue(result)
        # Should have called status then stash push
        self.assertEqual(mock_run_cmd.call_count, 2)

    @patch("sync_active_config.run_cmd")
    def test_stash_if_clean(self, mock_run_cmd):
        """Verify no stash when working tree is clean."""
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="\n")
        result = stash_if_dirty("/fake/repo")
        self.assertFalse(result)
        # Should have only called status
        self.assertEqual(mock_run_cmd.call_count, 1)

    @patch("sync_active_config.run_cmd")
    def test_stash_pop_if_stashed(self, mock_run_cmd):
        """Verify stash pop is called only when was_stashed is True."""
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="")
        stash_pop_if_stashed("/fake/repo", True)
        self.assertEqual(mock_run_cmd.call_count, 1)

        mock_run_cmd.reset_mock()
        stash_pop_if_stashed("/fake/repo", False)
        self.assertEqual(mock_run_cmd.call_count, 0)

    def test_print_sync_summary_with_updates(self):
        """Verify summary output when files were updated."""
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _print_sync_summary(
                checked=[".bashrc", ".vimrc"],
                updated=[".bashrc"],
                blocked=[],
            )
        output = captured.getvalue()
        self.assertIn("Checked 2 config files", output)
        self.assertIn("Found 1 updated config file(s)", output)
        self.assertIn(".bashrc", output)

    def test_print_sync_summary_no_changes(self):
        """Verify summary output when no files differ."""
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _print_sync_summary(checked=[".bashrc"], updated=[], blocked=[])
        output = captured.getvalue()
        self.assertIn("No differences found", output)

    def test_main_skips_branch_when_no_changes(self):
        """Verify no branch is created when active configs match the repo."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source   = tmp_path / "source"
            repo     = tmp_path / "repo"
            source.mkdir()
            repo.mkdir()

            # Identical files — no changes to sync
            (source / ".bashrc").write_text("export TEST=1\n")
            (repo / ".bashrc").write_text("export TEST=1\n")

            test_args = ["sync_active_config.py", "-s", str(source), "-r", str(repo)]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                output = captured.getvalue()
                self.assertIn("Nothing to sync", output)
                self.assertNotIn("Sync complete!", output)


if __name__ == "__main__":
    unittest.main()
