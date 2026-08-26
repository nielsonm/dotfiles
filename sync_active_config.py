#!/usr/bin/env python3
"""
Script to pull active configuration changes from $HOME into this repo,
scan for secrets/SSH keys to prevent accidental leaks, create a new Git branch
named after the machine hostname and current date, and automatically commit and push.
"""

import os
import sys
import shutil
import subprocess
import argparse
import filecmp
import socket
from datetime import datetime
from pathlib import Path

# Import secret scanner
try:
    from check_secrets import scan_file_for_secrets, scan_path
except ImportError:
    scan_file_for_secrets = None
    scan_path = None

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
    "Antigravity",
    "antigravity",
    "obsidian",
    "libreoffice",
    "evolution",
    "dconf",
    "totem",
    "goa-1.0",
    "gnome-session",
    "ibus",
}

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

def sync_active_configs(source_dir, repo_dir, ignores, skip_secrets=True, dry_run=False):
    """Compare and optionally copy active config files from source into repo.

    Args:
        source_dir: Path to the active config directory (typically $HOME).
        repo_dir: Path to the dotfiles repo directory.
        ignores: Set of file/directory names to skip.
        skip_secrets: When True, block files containing secrets from syncing.
        dry_run: When True, only report which files differ without copying.

    Returns:
        Tuple of (checked_files, updated_files, blocked_files) lists.
    """
    source_path = Path(source_dir).resolve()
    repo_path   = Path(repo_dir).resolve()

    repo_files    = scan_repo_files(repo_path, ignores)
    updated_files = []
    checked_files = []
    blocked_files = []

    for rel_path in repo_files:
        src_file  = source_path / rel_path
        dest_file = repo_path / rel_path

        if src_file.exists() and src_file.is_file():
            checked_files.append(str(rel_path))

            # Secret check before syncing
            if skip_secrets and scan_file_for_secrets:
                findings = scan_file_for_secrets(src_file)
                if findings:
                    print(f"  [SECRET GUARD BLOCKED] '{rel_path}' contains secret(s)/SSH key(s):")
                    for item in findings:
                        print(f"    - [{item['type']}] Line {item['line']}: {item['detail']}")
                    blocked_files.append(str(rel_path))
                    continue

            needs_copy = False
            if not dest_file.exists():
                needs_copy = True
            else:
                try:
                    if src_file.stat().st_size != dest_file.stat().st_size or not filecmp.cmp(src_file, dest_file, shallow=False):
                        needs_copy = True
                except Exception:
                    needs_copy = True

            if needs_copy:
                if not dry_run:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)
                updated_files.append(str(rel_path))

    return checked_files, updated_files, blocked_files

def stash_if_dirty(repo_dir):
    """Stash any uncommitted changes to allow clean branch switching.

    Returns:
        True if changes were stashed, False otherwise.
    """
    status = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    if status.stdout.strip():
        print("Stashing uncommitted changes before branch switch...")
        run_cmd(["git", "stash", "push", "-m", "sync_active_config auto-stash"], cwd=repo_dir)
        return True
    return False

def stash_pop_if_stashed(repo_dir, was_stashed):
    """Pop the auto-stash if one was created."""
    if was_stashed:
        print("Restoring stashed changes...")
        run_cmd(["git", "stash", "pop"], cwd=repo_dir, check=False)

def _print_sync_summary(checked, updated, blocked):
    """Print a summary of the sync operation results."""
    print(f"Checked {len(checked)} config files.")
    if blocked:
        print(f"Secret Guard blocked {len(blocked)} file(s) containing secret keys or tokens.")
    if updated:
        print(f"Found {len(updated)} updated config file(s) from active environment:")
        for u in updated:
            print(f"  - {u}")
    else:
        print("No differences found in active config files.")

def setup_cron_job(script_path):
    abs_script = Path(script_path).resolve()
    cron_cmd = f"0 9 * * * {abs_script} >> {abs_script.parent}/sync_cron.log 2>&1"

    # Get current crontab
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
    parser = argparse.ArgumentParser(
        description="Pull active configs, check for secrets, commit to machine+date branch, and push.",
    )
    parser.add_argument("-s", "--source", default=os.path.expanduser("~"), help="Source active config directory (default: $HOME)")
    parser.add_argument("-r", "--repo", default=os.path.dirname(os.path.abspath(__file__)), help="Repo directory (default: script location)")
    parser.add_argument("-b", "--branch", help="Custom branch name (default: <machine-name>-<YYYY-MM-DD>)")
    parser.add_argument("--remote", default="origin", help="Git remote to push to (default: origin)")
    parser.add_argument("--no-push", action="store_true", help="Commit changes locally without pushing to remote")
    parser.add_argument("--dry-run", action="store_true", help="Show files that would be updated without modifying repo or git state")
    parser.add_argument("--allow-secrets", action="store_true", help="Bypass secret guard scanner check during sync")
    parser.add_argument("--install-cron", action="store_true", help="Install a daily cron job to run this script automatically at 09:00 AM")

    args = parser.parse_args()

    repo_dir   = Path(args.repo).resolve()
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

    # Determine machine name & date for branch name
    machine_name = get_machine_name()
    date_str     = datetime.now().strftime("%Y-%m-%d")
    branch_name  = sanitize_branch_name(args.branch or f"{machine_name}-{date_str}")
    skip_secrets = not args.allow_secrets

    print("=== Dotfiles Active Config Sync ===")
    print(f"Source (Active): {source_dir}")
    print(f"Target (Repo)  : {repo_dir}")
    print(f"Target Branch  : {branch_name}")

    # --- Pre-flight: check what would change (dry-run comparison) ---
    checked, pending, blocked = sync_active_configs(
        source_dir, repo_dir, DEFAULT_IGNORES,
        skip_secrets=skip_secrets, dry_run=True,
    )
    _print_sync_summary(checked, pending, blocked)

    if args.dry_run:
        print("[Dry Run] Skipping git branch, commit, and push operations.")
        return

    if not pending:
        print("Nothing to sync — skipping branch creation.")
        return

    # --- Stash any uncommitted changes for safe branch switching ---
    was_stashed = stash_if_dirty(repo_dir)

    # --- Switch to (or create) today's branch ---
    branch_check = run_cmd(["git", "branch", "--list", branch_name], cwd=repo_dir)
    if branch_check.stdout.strip():
        print(f"Switching to existing local branch '{branch_name}'...")
        run_cmd(["git", "checkout", branch_name], cwd=repo_dir)
    else:
        print(f"Creating and switching to new branch '{branch_name}' off 'main'...")
        run_cmd(["git", "checkout", "-b", branch_name, "main"], cwd=repo_dir)

    # --- Sync files (now on the correct branch) ---
    checked, updated, blocked = sync_active_configs(
        source_dir, repo_dir, DEFAULT_IGNORES,
        skip_secrets=skip_secrets, dry_run=False,
    )

    # --- Stage, commit, push ---
    run_cmd(["git", "add", "-A"], cwd=repo_dir)
    status_res     = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    staged_changes = [line for line in status_res.stdout.splitlines() if line.strip()]

    if not staged_changes:
        print(f"No changes to commit on branch '{branch_name}'.")
    else:
        commit_msg = f"Sync active dotfiles from {machine_name} on {date_str}"
        print(f"Committing changes: '{commit_msg}'...")
        run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_dir)

        if args.no_push:
            print("Skipping push (--no-push specified).")
        else:
            print(f"Pushing branch '{branch_name}' to remote '{args.remote}'...")
            push_res = run_cmd(
                ["git", "push", "-u", args.remote, branch_name],
                cwd=repo_dir, check=False,
            )
            if push_res.returncode == 0:
                print(f"Successfully pushed branch '{branch_name}' to '{args.remote}'.")
            else:
                print(f"Warning: Push to '{args.remote}' failed:\n{push_res.stderr}", file=sys.stderr)

    stash_pop_if_stashed(repo_dir, was_stashed)
    print("Sync complete!")

if __name__ == "__main__":
    main()
