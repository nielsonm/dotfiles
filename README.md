# Dotfiles Repository

A lightweight, cross-platform dotfiles management repository with automatic active configuration auditing, daily machine-and-date branch syncs, and OS-specific setup.

---

## Key Features & Tools

### 1. Installation (`install.sh`)
Cross-platform installer for macOS (OSX) and Linux. Uses safe symlinks, backups existing files, and bootstraps Vim plugins.

```bash
./install.sh
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

### 3. Automated Daily Sync (`sync_active_config.sh`)
Pulls active config changes into a new branch named `<machine-name>-<YYYY-MM-DD>`, commits them, and pushes automatically to your remote Git repository.

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

To keep machine-specific aliases or tokens out of tracked dotfiles, place them in:
- `~/.bashrc.local` (automatically sourced by `.bashrc`)
- `~/.zshrc.local` (automatically sourced by `.zshrc`)
