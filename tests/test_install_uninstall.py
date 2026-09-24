import os
import unittest
import tempfile
import subprocess
from pathlib import Path

class TestInstallUninstallScripts(unittest.TestCase):
    
    def test_install_and_uninstall_workflow(self):
        repo_dir = Path(__file__).resolve().parent.parent
        install_script = repo_dir / "install.sh"
        uninstall_script = repo_dir / "uninstall.sh"
        
        self.assertTrue(install_script.exists())
        self.assertTrue(uninstall_script.exists())
        
        with tempfile.TemporaryDirectory() as tmp_home:
            dest = Path(tmp_home)
            
            # Pre-create an existing file to test .bak backup creation
            existing_bashrc = dest / ".bashrc"
            existing_bashrc.write_text("# Original user bashrc\nexport MY_VAR=1\n")
            
            # 1. Run install.sh pointing to temporary destination
            test_env = {**os.environ, "SKIP_CRON": "1"}
            res_inst = subprocess.run(
                [str(install_script), str(dest)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=test_env,
            )
            self.assertEqual(res_inst.returncode, 0, f"install.sh failed:\n{res_inst.stderr}")
            
            # Verify symlinks were created
            self.assertTrue(existing_bashrc.is_symlink())
            self.assertEqual(existing_bashrc.resolve(), (repo_dir / ".bashrc").resolve())
            
            # Verify backup file was created
            bak_bashrc = dest / ".bashrc.bak"
            self.assertTrue(bak_bashrc.exists())
            self.assertEqual(bak_bashrc.read_text(), "# Original user bashrc\nexport MY_VAR=1\n")
            
            # Verify .gitconfig was created from .gitconfig.safe if missing
            gitconfig = dest / ".gitconfig"
            self.assertTrue(gitconfig.exists())
            
            # 2. Run uninstall.sh pointing to temporary destination
            res_uninst = subprocess.run(
                [str(uninstall_script), str(dest)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=test_env,
            )
            self.assertEqual(res_uninst.returncode, 0, f"uninstall.sh failed:\n{res_uninst.stderr}")
            
            # Verify symlink was removed and original backup restored
            self.assertFalse(existing_bashrc.is_symlink())
            self.assertTrue(existing_bashrc.exists())
            self.assertEqual(existing_bashrc.read_text(), "# Original user bashrc\nexport MY_VAR=1\n")
            self.assertFalse(bak_bashrc.exists())

    def test_crontab_install_and_uninstall(self):
        repo_dir = Path(__file__).resolve().parent.parent
        install_script = repo_dir / "install.sh"
        uninstall_script = repo_dir / "uninstall.sh"

        with tempfile.TemporaryDirectory() as tmp_env_dir:
            tmp_path = Path(tmp_env_dir)
            mock_bin_dir = tmp_path / "bin"
            mock_bin_dir.mkdir()
            mock_cron_file = tmp_path / "crontab.txt"
            mock_dest = tmp_path / "home"
            mock_dest.mkdir()

            # Create mock crontab binary
            mock_crontab_script = mock_bin_dir / "crontab"
            mock_crontab_script.write_text(
                "#!/usr/bin/env bash\n"
                "CRON_FILE=\"$MOCK_CRON_STORE\"\n"
                "if [ \"$1\" = \"-l\" ]; then\n"
                "    if [ -f \"$CRON_FILE\" ]; then\n"
                "        cat \"$CRON_FILE\"\n"
                "    else\n"
                "        echo \"no crontab for user\" >&2\n"
                "        exit 1\n"
                "    fi\n"
                "elif [ \"$1\" = \"-\" ]; then\n"
                "    cat > \"$CRON_FILE\"\n"
                "elif [ \"$1\" = \"-r\" ]; then\n"
                "    rm -f \"$CRON_FILE\"\n"
                "fi\n"
            )
            mock_crontab_script.chmod(0o755)

            test_env = {
                **os.environ,
                "PATH": f"{mock_bin_dir}:{os.environ.get('PATH', '')}",
                "MOCK_CRON_STORE": str(mock_cron_file),
                "SKIP_CRON": "0",
            }

            # Seed existing crontab with unrelated user job
            existing_user_cron = "30 2 * * * /usr/local/bin/my_backup.sh\n"
            mock_cron_file.write_text(existing_user_cron)

            # 1. Test install.sh adds managed block and preserves existing job
            res_inst = subprocess.run(
                [str(install_script), str(mock_dest)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=test_env,
            )
            self.assertEqual(res_inst.returncode, 0, f"install.sh failed:\n{res_inst.stderr}")
            installed_cron = mock_cron_file.read_text()
            self.assertIn("30 2 * * * /usr/local/bin/my_backup.sh", installed_cron)
            self.assertIn("# BEGIN DOTFILES MANAGED BLOCK", installed_cron)
            self.assertIn("sync_active_config.sh", installed_cron)
            self.assertIn("backup_vscode.sh", installed_cron)
            self.assertIn("# END DOTFILES MANAGED BLOCK", installed_cron)

            # 2. Test idempotency: running install.sh again replaces without duplicating
            res_inst2 = subprocess.run(
                [str(install_script), str(mock_dest)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=test_env,
            )
            self.assertEqual(res_inst2.returncode, 0)
            installed_cron2 = mock_cron_file.read_text()
            self.assertEqual(installed_cron2.count("# BEGIN DOTFILES MANAGED BLOCK"), 1)
            self.assertEqual(installed_cron2.count("# END DOTFILES MANAGED BLOCK"), 1)

            # 3. Test uninstall.sh removes managed block but preserves user job
            res_uninst = subprocess.run(
                [str(uninstall_script), str(mock_dest)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=test_env,
            )
            self.assertEqual(res_uninst.returncode, 0, f"uninstall.sh failed:\n{res_uninst.stderr}")
            uninstalled_cron = mock_cron_file.read_text()
            self.assertNotIn("BEGIN DOTFILES MANAGED BLOCK", uninstalled_cron)
            self.assertNotIn("sync_active_config.sh", uninstalled_cron)
            self.assertIn("30 2 * * * /usr/local/bin/my_backup.sh", uninstalled_cron)

            # 4. Test --no-cron flag prevents crontab changes
            res_no_cron = subprocess.run(
                [str(install_script), str(mock_dest), "--no-cron"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=test_env,
            )
            self.assertEqual(res_no_cron.returncode, 0)
            cron_after_no_cron = mock_cron_file.read_text()
            self.assertNotIn("BEGIN DOTFILES MANAGED BLOCK", cron_after_no_cron)


if __name__ == "__main__":
    unittest.main()
