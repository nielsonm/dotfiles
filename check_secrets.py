#!/usr/bin/env python3
"""
Secret & SSH Key Scanner for Dotfiles
Scans repository or active configuration directories for SSH private keys,
API tokens, credentials, and other sensitive patterns.
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path

# Files and directories ignored by default during scanning
DEFAULT_IGNORES = {
    ".git",
    ".github",
    ".gitignore",
    ".vscode",
    "README.md",
    "Makefile",
    "install.sh",
    "uninstall.sh",
    "check_diffs.py",
    "check_diffs.sh",
    "sync_active_config.py",
    "sync_active_config.sh",
    "check_secrets.py",
    "check_secrets.sh",
    "diff_report.txt",
    "sync_cron.log",
    "pytest.ini",
    "tests",
    "__pycache__",
    "CacheStorage",
    "Code Cache",
    "GPUCache",
    "WebStorage",
    "Local Storage",
    "blob_storage",
    "IndexedDB",
    "Crashpad",
    "Cache",
    "google-chrome",
    "Code",
    "obsidian",
    "libreoffice",
    "evolution",
    "dconf",
    "totem",
    "goa-1.0",
    "gnome-session",
    "ibus",
}

# SSH private key header patterns
SSH_PRIVATE_KEY_HEADERS = [
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN ENCRYPTED PRIVATE KEY-----",
    "-----BEGIN PGP PRIVATE KEY BLOCK-----",
]

# Filename patterns for SSH private keys
SSH_KEY_FILENAMES = {
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "id_ecdsa_sk", "id_ed25519_sk",
    "id_rsa.pem", "id_dsa.pem", "id_ecdsa.pem", "id_ed25519.pem"
}

# Regex patterns for common secret formats
SECRET_PATTERNS = [
    (
        "SSH Private Key Header",
        re.compile(r"-----BEGIN (?:OPENSSH|RSA|DSA|EC|PGP|ENCRYPTED)?\s?PRIVATE KEY(?:\sBLOCK)?-----")
    ),
    (
        "AWS Access Key ID",
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b")
    ),
    (
        "AWS Secret Access Key",
        re.compile(r"(?i)\baws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?")
    ),
    (
        "GitHub Personal Access Token",
        re.compile(r"\b(ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})\b")
    ),
    (
        "Slack Token",
        re.compile(r"\b(xox[baprs]-[0-9a-zA-Z]{10,48})\b")
    ),
    (
        "Stripe Secret Key",
        re.compile(r"\b(sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,})\b")
    ),
    (
        "OpenAI / Anthropic API Key",
        re.compile(r"\b(sk-(?:proj-|ant-)?[a-zA-Z0-9_-]{32,})\b")
    ),
    (
        "Generic Secret / Key Assignment",
        re.compile(r"(?i)\b(?:api_key|secret_key|access_token|password|auth_token|client_secret)\s*[:=]\s*['\"]([^'\"]{8,})['\"]")
    ),
]

# Known safe placeholders that should not trigger false positives
SAFE_PLACEHOLDERS = {
    "your_api_key", "your_secret_key", "your_password", "example", "placeholder",
    "change_me", "changeme", "xxx", "xxxx", "xxxxxxxx", "123456", "secret", "mysecret",
    "foo", "bar", "baz", "test", "todo", "none", "null", "undefined"
}

def is_placeholder(val):
    val_lower = val.strip().lower()
    if val_lower in SAFE_PLACEHOLDERS:
        return True
    if val_lower.startswith("your_") or val_lower.startswith("<") or val_lower.startswith("${"):
        return True
    if len(set(val_lower)) <= 2 and len(val_lower) > 4:  # e.g., "xxxxxxxxx"
        return True
    return False

def is_ssh_private_key_file(file_path):
    path = Path(file_path)
    name = path.name

    # Public keys (.pub) and explicit template files (.template) are safe unless header found inside
    if name.endswith(".pub") or name.endswith(".template"):
        return False

    if name in SSH_KEY_FILENAMES or (name.startswith("id_") and not name.endswith(".pub") and not name.endswith(".template")):
        return True

    if name.endswith(".pem") or name.endswith(".key") or name.endswith(".pkcs12") or name.endswith(".pfx"):
        return True

    return False

def scan_file_for_secrets(file_path):
    findings = []
    path = Path(file_path)

    # Check filename first
    if is_ssh_private_key_file(path):
        # Verify if content actually looks like a key or private file
        try:
            content = path.read_text(errors='replace')
            findings.append({
                "type": "SSH Private Key File",
                "line": 1,
                "detail": f"File '{path.name}' matches SSH private key naming pattern.",
                "snippet": content.splitlines()[0][:60] if content else ""
            })
        except Exception as e:
            findings.append({
                "type": "SSH Private Key File",
                "line": 1,
                "detail": f"File '{path.name}' matches SSH private key naming pattern (unread: {e})",
                "snippet": ""
            })
        return findings

    # Don't scan binary or non-text files
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        return findings

    # Skip files that are explicitly safe templates if no actual key header is present
    is_template = path.name.endswith(".template")

    for line_idx, line in enumerate(lines, start=1):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue

        for rule_name, regex in SECRET_PATTERNS:
            for match in regex.finditer(line):
                matched_val = match.group(1) if match.groups() else match.group(0)
                if is_placeholder(matched_val):
                    continue

                if is_template and "KEY" not in rule_name and "Header" not in rule_name:
                    continue

                findings.append({
                    "type": rule_name,
                    "line": line_idx,
                    "detail": f"Matched pattern '{rule_name}'",
                    "snippet": line_clean[:80]
                })

    return findings

def scan_path(target_path, ignores=None):
    if ignores is None:
        ignores = DEFAULT_IGNORES

    results = {}
    path = Path(target_path).resolve()

    if not path.exists():
        return results

    if path.is_file():
        rel_str = path.name
        if rel_str not in ignores:
            findings = scan_file_for_secrets(path)
            if findings:
                results[rel_str] = findings
        return results

    for root, dirs, files in os.walk(path):
        dirs[:] = [
            d for d in dirs
            if d not in ignores and not os.path.relpath(os.path.join(root, d), path).startswith('.git')
        ]
        for file in files:
            full_path = Path(root) / file
            rel_path = full_path.relative_to(path)
            rel_str = str(rel_path)

            if rel_str in ignores or rel_path.parts[0] in ignores:
                continue

            findings = scan_file_for_secrets(full_path)
            if findings:
                results[rel_str] = findings

    return results

def main():
    parser = argparse.ArgumentParser(description="Scan dotfiles for SSH keys and secret tokens.")
    parser.add_argument("-t", "--target", default=os.path.dirname(os.path.abspath(__file__)), help="Directory or file to scan (default: current repo)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output if no secrets found")
    parser.add_argument("--exit-code", action="store_true", help="Exit with code 1 if secrets/keys are found, 0 otherwise")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()

    if not target_path.exists():
        print(f"Error: Target path '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    results = scan_path(target_path, DEFAULT_IGNORES)
    total_findings = sum(len(f) for f in results.values())

    if args.json:
        out = {
            "target": str(target_path),
            "clean": total_findings == 0,
            "total_secrets_found": total_findings,
            "results": results
        }
        print(json.dumps(out, indent=2))
    else:
        if total_findings == 0:
            if not args.quiet:
                print(f"[OK] Secret Scanner: No SSH private keys or secrets found in '{target_path}'.")
        else:
            print(f"[WARNING] Secret Scanner detected {total_findings} potential secret(s)/SSH key(s) in {len(results)} file(s):")
            print("=" * 64)
            for rel_file, findings in results.items():
                print(f"\nFile: {rel_file}")
                for item in findings:
                    print(f"  - Line {item['line']}: [{item['type']}] {item['detail']}")
                    if item.get('snippet'):
                        print(f"    Snippet: {item['snippet']}")
            print("=" * 64)

    if args.exit_code and total_findings > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
