import os
import unittest
import tempfile
from pathlib import Path
from check_secrets import (
    is_ssh_private_key_file,
    scan_file_for_secrets,
    scan_path,
    is_placeholder
)

class TestCheckSecrets(unittest.TestCase):

    def test_is_placeholder(self):
        self.assertTrue(is_placeholder("YOUR_API_KEY"))
        self.assertTrue(is_placeholder("EXAMPLE"))
        self.assertTrue(is_placeholder("xxxxxxxxxxxx"))
        self.assertTrue(is_placeholder("${MY_VAR}"))
        self.assertFalse(is_placeholder("AKIAIOSFODNN7EXAMPLE"))
        self.assertFalse(is_placeholder("ghp_1234567890abcdefghijklmnopqrstuvwxyz"))

    def test_is_ssh_private_key_file(self):
        # Positive SSH private key filenames
        self.assertTrue(is_ssh_private_key_file("id_rsa"))
        self.assertTrue(is_ssh_private_key_file("id_ed25519"))
        self.assertTrue(is_ssh_private_key_file("id_ecdsa"))
        self.assertTrue(is_ssh_private_key_file("id_dsa"))
        self.assertTrue(is_ssh_private_key_file("server_key.pem"))
        self.assertTrue(is_ssh_private_key_file("cert.pkcs12"))
        
        # Negative / safe filenames
        self.assertFalse(is_ssh_private_key_file("id_rsa.pub"))
        self.assertFalse(is_ssh_private_key_file("id_ed25519.pub"))
        self.assertFalse(is_ssh_private_key_file("config.template"))
        self.assertFalse(is_ssh_private_key_file(".bashrc"))

    def test_scan_file_for_ssh_headers(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            key_file = Path(tmp_dir) / "my_key"
            key_content = "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAA\n-----END OPENSSH PRIVATE KEY-----\n"
            key_file.write_text(key_content)

            findings = scan_file_for_secrets(key_file)
            self.assertTrue(len(findings) > 0)
            self.assertTrue(any("SSH Private Key" in f["type"] for f in findings))

    def test_scan_file_for_rsa_private_key_header(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            key_file = Path(tmp_dir) / "id_rsa_test"
            key_content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----\n"
            key_file.write_text(key_content)

            findings = scan_file_for_secrets(key_file)
            self.assertTrue(len(findings) > 0)
            self.assertTrue(any("SSH Private Key" in f["type"] for f in findings))

    def test_scan_file_for_aws_keys(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            aws_file = Path(tmp_dir) / ".aws_credentials"
            aws_file.write_text("aws_access_key_id = AKIAIOSFODNN7EXAMPLE\naws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n")

            findings = scan_file_for_secrets(aws_file)
            types = [f["type"] for f in findings]
            self.assertIn("AWS Access Key ID", types)

    def test_scan_file_for_github_pat(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pat_file = Path(tmp_dir) / ".gitconfig"
            pat_file.write_text("token = ghp_1234567890abcdefghijklmnopqrstuvwxyz\n")

            findings = scan_file_for_secrets(pat_file)
            types = [f["type"] for f in findings]
            self.assertIn("GitHub Personal Access Token", types)

    def test_scan_file_for_slack_token(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            slack_file = Path(tmp_dir) / "slack.env"
            slack_file.write_text("SLACK_TOKEN=xoxb-123456789012-1234567890123-abcdefghijklmnopqrstuv\n")

            findings = scan_file_for_secrets(slack_file)
            types = [f["type"] for f in findings]
            self.assertIn("Slack Token", types)

    def test_scan_file_for_openai_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ai_file = Path(tmp_dir) / ".env"
            ai_file.write_text("OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz123456\n")

            findings = scan_file_for_secrets(ai_file)
            types = [f["type"] for f in findings]
            self.assertIn("OpenAI / Anthropic API Key", types)

    def test_clean_file_no_secrets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            clean_file = Path(tmp_dir) / ".bashrc"
            clean_file.write_text("export PATH=$PATH:/usr/local/bin\nalias ll='ls -la'\nexport API_KEY=YOUR_API_KEY\n")

            findings = scan_file_for_secrets(clean_file)
            self.assertEqual(len(findings), 0)

    def test_scan_path_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / ".bashrc").write_text("export TEST=1\n")
            (tmp_path / "id_rsa").write_text("-----BEGIN RSA PRIVATE KEY-----\nkey\n")

            ignores = {".git"}
            results = scan_path(tmp_path, ignores)

            self.assertIn("id_rsa", results)
            self.assertNotIn(".bashrc", results)

if __name__ == "__main__":
    unittest.main()
