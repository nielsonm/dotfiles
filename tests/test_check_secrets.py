import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from check_secrets import (
    is_ssh_private_key_file,
    scan_file_for_secrets,
    scan_path,
    is_placeholder,
    main,
)


class TestCheckSecrets(unittest.TestCase):

    def test_is_placeholder(self):
        self.assertTrue(is_placeholder("YOUR_API_KEY"))
        self.assertTrue(is_placeholder("EXAMPLE"))
        self.assertTrue(is_placeholder("xxxxxxxxxxxx"))
        self.assertTrue(is_placeholder("${MY_VAR}"))
        self.assertTrue(is_placeholder("<API_KEY>"))
        self.assertFalse(is_placeholder("AKIAIOSFODNN7EXAMPLE"))
        self.assertFalse(is_placeholder("ghp_1234567890abcdefghijklmnopqrstuvwxyz"))

    def test_is_ssh_private_key_file(self):
        self.assertTrue(is_ssh_private_key_file("id_rsa"))
        self.assertTrue(is_ssh_private_key_file("id_ed25519"))
        self.assertTrue(is_ssh_private_key_file("id_ecdsa"))
        self.assertTrue(is_ssh_private_key_file("id_dsa"))
        self.assertTrue(is_ssh_private_key_file("server_key.pem"))
        self.assertTrue(is_ssh_private_key_file("cert.pkcs12"))
        self.assertTrue(is_ssh_private_key_file("secret.key"))

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
            self.assertIn("AWS Secret Access Key", types)

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

    def test_scan_file_for_stripe_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stripe_file = Path(tmp_dir) / "stripe.env"
            stripe_file.write_text("STRIPE_KEY = sk_live_51Abcdefghijklmnopqrstuvwxyz1234\n")

            findings = scan_file_for_secrets(stripe_file)
            types = [f["type"] for f in findings]
            self.assertIn("Stripe Secret Key", types)

    def test_scan_file_for_openai_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ai_file = Path(tmp_dir) / ".env"
            ai_file.write_text("OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz123456\n")

            findings = scan_file_for_secrets(ai_file)
            types = [f["type"] for f in findings]
            self.assertIn("OpenAI / Anthropic API Key", types)

    def test_scan_file_for_generic_secret(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sec_file = Path(tmp_dir) / "app.env"
            sec_file.write_text("client_secret = 'super_secret_database_key_value'\n")

            findings = scan_file_for_secrets(sec_file)
            types = [f["type"] for f in findings]
            self.assertIn("Generic Secret / Key Assignment", types)

    def test_scan_binary_file_skipped(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_file = Path(tmp_dir) / "sample.bin"
            bin_file.write_bytes(b"\x00\x01\x02\x03AKIAIOSFODNN7EXAMPLE\x00\x00")

            findings = scan_file_for_secrets(bin_file)
            self.assertEqual(len(findings), 0)

    def test_clean_file_no_secrets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            clean_file = Path(tmp_dir) / ".bashrc"
            clean_file.write_text("export PATH=$PATH:/usr/local/bin\nalias ll='ls -la'\nexport API_KEY=YOUR_API_KEY\n")

            findings = scan_file_for_secrets(clean_file)
            self.assertEqual(len(findings), 0)

    def test_template_file_handling(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            template_file = Path(tmp_dir) / "config.template"
            template_file.write_text("api_key = 'sample_template_value_here'\n")

            findings = scan_file_for_secrets(template_file)
            self.assertEqual(len(findings), 0)

    def test_scan_path_single_file_and_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / ".bashrc").write_text("export TEST=1\n")
            (tmp_path / "id_rsa").write_text("-----BEGIN RSA PRIVATE KEY-----\nkey\n")

            ignores = {".git"}
            results_dir = scan_path(tmp_path, ignores)
            self.assertIn("id_rsa", results_dir)
            self.assertNotIn(".bashrc", results_dir)

            results_file = scan_path(tmp_path / "id_rsa")
            self.assertIn("id_rsa", results_file)

            results_none = scan_path(tmp_path / "nonexistent")
            self.assertEqual(len(results_none), 0)

    def test_main_cli_clean_and_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / ".bashrc").write_text("export TEST=1\n")

            test_args = ["check_secrets.py", "-t", str(tmp_path), "--json"]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                data = json.loads(captured.getvalue())
                self.assertTrue(data["clean"])
                self.assertEqual(data["total_secrets_found"], 0)

    def test_main_cli_quiet_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / ".bashrc").write_text("export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n")

            # With secrets and --exit-code -> should exit with code 1
            test_args = ["check_secrets.py", "-t", str(tmp_path), "--exit-code"]
            with patch("sys.argv", test_args):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 1)

    def test_main_cli_invalid_target(self):
        with patch("sys.argv", ["check_secrets.py", "-t", "/nonexistent_path"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    def test_main_cli_clean_without_quiet(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "clean.txt").write_text("Hello world\n")

            test_args = ["check_secrets.py", "-t", str(tmp_path)]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                self.assertIn("[OK] Secret Scanner: No SSH private keys or secrets found", captured.getvalue())

    def test_main_cli_clean_with_quiet(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "clean.txt").write_text("Hello world\n")

            test_args = ["check_secrets.py", "-t", str(tmp_path), "-q"]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                self.assertEqual(captured.getvalue(), "")

    def test_main_cli_with_secrets_and_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "secret.env").write_text("OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz123456\n")

            test_args = ["check_secrets.py", "-t", str(tmp_path), "--json"]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                data = json.loads(captured.getvalue())
                self.assertFalse(data["clean"])
                self.assertEqual(data["total_secrets_found"], 1)
                self.assertIn("secret.env", data["results"])

    def test_main_cli_with_secrets_plain_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "secret.env").write_text("OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz123456\n")

            test_args = ["check_secrets.py", "-t", str(tmp_path)]
            with patch("sys.argv", test_args):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    main()
                output = captured.getvalue()
                self.assertIn("[WARNING] Secret Scanner detected 1 potential secret(s)", output)
                self.assertIn("File: secret.env", output)
                self.assertIn("OpenAI / Anthropic API Key", output)

    def test_ssh_key_file_read_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            key_file = Path(tmp_dir) / "id_rsa"
            key_file.write_text("dummy")

            # Mock read_text to raise an exception
            with patch.object(Path, "read_text", side_effect=PermissionError("Permission denied")):
                findings = scan_file_for_secrets(key_file)
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["type"], "SSH Private Key File")
                self.assertIn("unread: Permission denied", findings[0]["detail"])

    def test_ssh_key_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            key_file = Path(tmp_dir) / "id_ecdsa"
            key_file.write_text("")
            findings = scan_file_for_secrets(key_file)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["snippet"], "")

    def test_file_read_errors_handled_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_file = Path(tmp_dir) / "test.txt"
            sample_file.write_text("some content")

            # Mock open to fail
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                findings = scan_file_for_secrets(sample_file)
                self.assertEqual(findings, [])

    def test_scan_path_with_ignored_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            git_dir = root / ".git"
            git_dir.mkdir()
            (git_dir / "secret_in_git.txt").write_text("OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz123456\n")

            cache_dir = root / "Cache"
            cache_dir.mkdir()
            (cache_dir / "secret_in_cache.txt").write_text("OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz123456\n")

            normal_file = root / "script.sh"
            normal_file.write_text("echo 'hello'\n")

            results = scan_path(root)
            self.assertEqual(len(results), 0)

    def test_scan_path_single_file_in_ignores(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            readme = Path(tmp_dir) / "README.md"
            readme.write_text("OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz123456\n")

            results = scan_path(readme)
            self.assertEqual(len(results), 0)

    def test_additional_placeholder_cases(self):
        self.assertTrue(is_placeholder("your_password_here"))
        self.assertTrue(is_placeholder("YOUR_AWS_KEY"))
        self.assertTrue(is_placeholder("changeme"))
        self.assertTrue(is_placeholder("undefined"))
        self.assertTrue(is_placeholder("null"))
        self.assertTrue(is_placeholder("none"))
        self.assertTrue(is_placeholder("foo"))
        self.assertTrue(is_placeholder("bar"))
        self.assertTrue(is_placeholder("123456"))
        self.assertTrue(is_placeholder("000000000"))

    def test_line_comment_and_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "test.conf"
            f.write_text("\n\n# AKIAIOSFODNN7EXAMPLE this is a comment\n   \n")
            findings = scan_file_for_secrets(f)
            self.assertEqual(len(findings), 0)


if __name__ == "__main__":
    unittest.main()
