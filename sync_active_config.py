#!/usr/bin/env python3
"""
Script to pull active configuration changes from $HOME into this repo,
create a new Git branch named after the machine hostname and current date,
and automatically commit and push the changes.
Includes a Secret Guard scanner to prevent accidental leaks of sensitive tokens.
"""

import os
import sys
import re
import shutil
import subprocess
import argparse
import socket
from datetime import datetime
from pathlib import Path

DEFAULT_IGNORES = {
    ".git",
    ".gitignore",
    "README.md",
    "install.sh",
    "uninstall.sh",
    "check_diffs.py",
    "check_diffs.sh",
    "sync_active_config.py",
    "sync_active_config.sh",
    "diff_report.txt",
    "Makefile",
}

# Regex patterns for detecting sensitive data
SECRET_PATTERNS = [
    (re.compile(r'-----BEGIN\s+(?:RSA|OPENSSH|EC|DSA|PRIVATE)\s+KEY-----'), "Private SSH/Crypto Key"),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), "AWS Access Key ID"),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), "GitHub Personal Access Token"),
    (re.compile(r'gho_[a-zA-Z0-9]{36}'), "GitHub OAuth Token"),
    (re.compile(r'xox[baprs]-[0-9a-zA-Z]{10,48}'), "Slack Token"),
    (re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'), "JWT Bearer Token"),
]

def run_cmd(cmd, cwd=None, check=True):
    res = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command '{' '.join(cmd)}' failed (exit code {res.returncode}):\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
    return res

def get_machine_name():
    try:
        name = socket.gethostname().split('.')[0]
        if name and name != "localhost":
            return name
    except Exception:
        pass
    return os.environ.get("HOSTNAME", "machine")

def sanitize_branch_name(name):
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in name)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-.")

def scan_repo_files(repo_dir, ignores):
    repo_files = []
    repo_path = Path(repo_dir).resolve()

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [
            d for d in dirs
            if d not in ignores and not os.path.relpath(os.path.join(root, d), repo_path).startswith('.git')
        ]
        for file in files:
            full_path = Path(root) / file
            rel_path = full_path.relative_to(repo_path)
            rel_str = str(rel_path)
            if rel_str in ignores or rel_path.parts[0] in ignores:
                continue
            repo_files.append(rel_path)

    return sorted(repo_files)

def scan_file_for_secrets(file_path):
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for idx, line in enumerate(f, 1):
                for pattern, desc in SECRET_PATTERNS:
                    if pattern.search(line):
                        findings.append((idx, desc, line.strip()[:60]))
    except Exception:
        pass
    return findings

def sync_active_configs(source_dir, repo_dir, ignores):
    source_path = Path(source_dir).resolve()
    repo_path = Path(repo_dir).resolve()

    repo_files = scan_repo_files(repo_path, ignores)
    updated_files = []
    checked_files = []

    for rel_path in repo_files:
        src_file = source_path / rel_path
        dest_file = repo_path / rel_path

        if src_file.exists() and src_file.is_file():
            checked_files.append(str(rel_path))
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            needs_copy = False
            if not dest_file.exists():
                needs_copy = True
            else:
                try:
                    with open(src_file, 'rb') as f1, open(dest_file, 'rb') as f2:
                        if f1.read() != f2.read():
                            needs_copy = True
                except Exception:
                    needs_copy = True

            if needs_copy:
                shutil.copy2(src_file, dest_file)
                updated_files.append(str(rel_path))

    return checked_files, updated_files

def setup_cron_job(script_path):
    abs_script = Path(script_path).resolve()
    cron_cmd = f"0 9 * * * {abs_script} >> {abs_script.parent}/sync_cron.log 2>&1"

    res = run_cmd(["crontab", "-l"], check=False)
    current_cron = res.stdout if res.returncode == 0 else ""

    if str(abs_script) in current_cron:
        print("Cron job is already installed in user crontab.")
        return

    new_cron = current_cron.strip() + "\n" + cron_cmd + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
    if proc.returncode == 0:
        print(f"Successfully added daily cron job (runs at 09:00 AM daily):\n  {cron_cmd}")
    else:
        print(f"Failed to install cron job: {proc.stderr}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Pull active configs, commit to machine+date branch, and push automatically.")
    parser.add_argument("-s", "--source", default=os.path.expanduser("~"), help="Source active config directory (default: $HOME)")
    parser.add_argument("-r", "--repo", default=os.path.dirname(os.path.abspath(__file__)), help="Repo directory (default: script location)")
    parser.add_argument("-b", "--branch", help="Custom branch name (default: <machine-name>-<YYYY-MM-DD>)")
    parser.add_argument("--remote", default="origin", help="Git remote to push to (default: origin)")
    parser.add_argument("--no-push", action="store_true", help="Commit changes locally without pushing to remote")
    parser.add_argument("--dry-run", action="store_true", help="Show files that would be updated without modifying repo or git state")
    parser.add_argument("--install-cron", action="store_true", help="Install a daily cron job to run this script automatically at 09:00 AM")
    parser.add_argument("--skip-secret-check", action="store_true", help="Bypass secret guard scan")

    args = parser.parse_args()

    repo_dir = Path(args.repo).resolve()
    source_dir = Path(args.source).resolve()

    if args.install_cron:
        script_file = repo_dir / "sync_active_config.sh"
        setup_cron_job(script_file if script_file.exists() else Path(__file__))
        if not any([args.branch, args.dry_run]) and len(sys.argv) == 2:
            return

    if not repo_dir.exists():
        print(f"Error: Repo directory '{repo_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"=== Dotfiles Active Config Sync ===")
    print(f"Source (Active): {source_dir}")
    print(f"Target (Repo)  : {repo_dir}")

    machine_name = get_machine_name()
    date_str = datetime.now().strftime("%Y-%m-%d")

    if args.branch:
        branch_name = sanitize_branch_name(args.branch)
    else:
        branch_name = sanitize_branch_name(f"{machine_name}-{date_str}")

    print(f"Target Branch  : {branch_name}")

    os.chdir(repo_dir)

    # 1. Switch to target branch FIRST before modifying working directory
    if not args.dry_run:
        cur_branch_res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        cur_branch = cur_branch_res.stdout.strip()

        if cur_branch != branch_name:
            branch_check = run_cmd(["git", "branch", "--list", branch_name])
            if branch_check.stdout.strip():
                print(f"Switching to existing local branch '{branch_name}'...")
                run_cmd(["git", "checkout", branch_name])
            else:
                print(f"Creating and switching to new branch '{branch_name}'...")
                run_cmd(["git", "checkout", "-b", branch_name])

    # 2. Copy active configs from $HOME to repo
    checked, updated = sync_active_configs(source_dir, repo_dir, DEFAULT_IGNORES)

    print(f"Checked {len(checked)} config files.")
    if updated:
        print(f"Found {len(updated)} updated config file(s) from active environment:")
        for u in updated:
            print(f"  - {u}")
    else:
        print("No differences found in active config files.")

    # 3. Secret Guard Scanner
    if not args.skip_secret_check and updated:
        print("Running Secret Guard scan on updated files...")
        secret_detected = False
        for u in updated:
            file_p = repo_dir / u
            findings = scan_file_for_secrets(file_p)
            if findings:
                secret_detected = True
                print(f"  [SECRET DETECTED] in {u}:")
                for line_no, desc, snippet in findings:
                    print(f"    Line {line_no} ({desc}): {snippet}")

        if secret_detected:
            print("\nError: Secret Guard detected potential sensitive keys/tokens! Sync aborted.", file=sys.stderr)
            print("Use --skip-secret-check if you are certain these values are safe.", file=sys.stderr)
            sys.exit(1)

    if args.dry_run:
        print("[Dry Run] Skipping git branch, commit, and push operations.")
        return

    # 4. Stage and commit changes
    run_cmd(["git", "add", "-A"])

    status_res = run_cmd(["git", "status", "--porcelain"])
    staged_changes = [line for line in status_res.stdout.splitlines() if line.strip()]

    if not staged_changes:
        print(f"No changes to commit on branch '{branch_name}'.")
    else:
        commit_msg = f"Sync active dotfiles from {machine_name} on {date_str}"
        print(f"Committing changes: '{commit_msg}'...")
        run_cmd(["git", "commit", "-m", commit_msg])

        if args.no_push:
            print("Skipping push (--no-push specified).")
        else:
            print(f"Pushing branch '{branch_name}' to remote '{args.remote}'...")
            push_res = run_cmd(["git", "push", "-u", args.remote, branch_name], check=False)
            if push_res.returncode == 0:
                print(f"Successfully pushed branch '{branch_name}' to '{args.remote}'.")
            else:
                print(f"Warning: Push to '{args.remote}' failed:\n{push_res.stderr}", file=sys.stderr)

    print("Sync complete!")

if __name__ == "__main__":
    main()
