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
            res_inst = subprocess.run(
                [str(install_script), str(dest)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
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
                stderr=subprocess.PIPE
            )
            self.assertEqual(res_uninst.returncode, 0, f"uninstall.sh failed:\n{res_uninst.stderr}")
            
            # Verify symlink was removed and original backup restored
            self.assertFalse(existing_bashrc.is_symlink())
            self.assertTrue(existing_bashrc.exists())
            self.assertEqual(existing_bashrc.read_text(), "# Original user bashrc\nexport MY_VAR=1\n")
            self.assertFalse(bak_bashrc.exists())

if __name__ == "__main__":
    unittest.main()
