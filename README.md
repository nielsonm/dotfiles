# Dotfiles Repository

A lightweight, cross-platform dotfiles management repository with automatic active configuration auditing, secret leakage prevention, daily machine-and-date branch syncs, and OS-specific setup.

---

## Key Features & Tools

### 1. Installation & Restoration (`install.sh` / `uninstall.sh`)
- **`install.sh`**: Cross-platform installer for macOS (OSX) and Linux. Creates non-destructive symlinks, backs up existing files (`.bak`), and bootstraps Vim plugins.
- **`uninstall.sh`**: Safely removes symlinks created by `install.sh` and restores original `.bak` configuration files.

```bash
# Install dotfiles
./install.sh

# Uninstall and restore backups
./uninstall.sh
```

### 2. Active Config Diff Checker (`check_diffs.sh`)
Audits active configuration files in your home directory (`~`) against the repository and prints color-coded unified diffs.

```bash
# Print full diff report
./check_diffs.sh

# Print summary table only
./check_diffs.sh --summary-only

# Filter for specific file
./check_diffs.sh -f .bashrc

# Export report to text file
./check_diffs.sh -o diff_report.txt
```

### 3. Automated Daily Sync & Secret Guard (`sync_active_config.sh`)
Pulls active config changes into a new branch named `<machine-name>-<YYYY-MM-DD>`, scans for sensitive tokens/keys, commits them, and pushes automatically to your remote Git repository.

```bash
# Run sync manually
./sync_active_config.sh

# Test without making changes
./sync_active_config.sh --dry-run

# Commit locally without pushing
./sync_active_config.sh --no-push

# Setup daily cron job (runs automatically at 9:00 AM daily)
./sync_active_config.sh --install-cron
```

---

## Machine-Specific Customizations (`.local` pattern)

`.bashrc` and `.zshrc` automatically load un-tracked local override files if present in your home directory:
- `~/.bashrc.local`
- `~/.zshrc.local`

Use these files to store work-specific environment variables, private paths, or machine-unique aliases without dirtying your tracked dotfiles repo.

---

## Makefile Shortcuts

```bash
make install    # Run installer with symlinks
make uninstall  # Remove symlinks & restore backups
make diff       # View diff report between active config and repo
make sync       # Run machine+date branch sync (with secret scan) & push
make cron       # Install daily automated cron job
```
