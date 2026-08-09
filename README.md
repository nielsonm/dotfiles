# Dotfiles Repository

A lightweight, cross-platform dotfiles management repository with automatic active configuration auditing, secret leakage prevention, SSH key scanning, daily machine-and-date branch syncs, Oh My Zsh / Vim plugin bootstrapping, and OS-specific setup.

---

## Prerequisites & Requirements

- **Operating System**: macOS (OSX) or Linux (Ubuntu/Debian, Fedora/RHEL, Arch).
- **Shell**: Bash 4.0+ or Zsh 5.0+.
- **Python**: Python 3.8+ (required for `check_secrets.py`, `check_diffs.py`, and `sync_active_config.py`).
- **Git**: Git 2.x+ (required for branch syncs and submodule/plugin management).
- **Optional Tools**:
  - `fzf` (recommended for interactive fuzzy searching in `git_untrack_ignore.sh`).
  - `crontab` (required for automated daily sync scheduling).

---

## Tracked Configurations Inventory

| File / Directory | Target Location | Description |
|---|---|---|
| `.bashrc` / `.bash_profile` | `~/.bashrc`, `~/.bash_profile` | Bash shell configurations & path exports |
| `.zshrc` | `~/.zshrc` | Zsh shell configuration with Oh My Zsh plugin support |
| `.tmux.conf` | `~/.tmux.conf` | Tmux terminal multiplexer status bar & keybindings |
| `.vimrc` / `.vim/` | `~/.vimrc`, `~/.vim/` | Vim editor config, plugin directories & Pathogen setup |
| `.gitconfig.safe` | `~/.gitconfig` | Safe template for Git global user settings & aliases |
| `.git-completion.bash` | `~/.git-completion.bash` | Autocompletion for Git commands in Bash |
| `.gitignore_global` | `~/.gitignore_global` | Global Git ignore rules for OS and editor artifacts |
| `.config/` | `~/.config/` | XDG application configuration directory |
| `.drush/` / `.drush.aliases...` | `~/.drush/`, `~/.drush.aliases...` | Drush aliases and settings for Drupal development |
| `bash_prompt.sh` | `~/bash_prompt.sh` | Custom Git-aware shell prompt script |
| `funzies.sh` | `~/funzies.sh` | Fun aliases, fortune, and weather utilities (`outside`) |
| `print_colors.sh` | `~/print_colors.sh` | ANSI 256-color palette viewer script |

---

## Installation & Restoration (`install.sh` / `uninstall.sh`)

### `install.sh`
Cross-platform installer for macOS and Linux. Features:
- **Non-Destructive Symlinking**: Symlinks files and directories from the repository to `$HOME`.
- **Automatic Backups**: Existing configuration files or directories in `$HOME` are safely moved to `<file>.bak` before creating symlinks.
- **Git Config Safety**: Copies `.gitconfig.safe` to `~/.gitconfig` if no active `.gitconfig` exists (preventing overwriting personal credentials).
- **Vim Plugin Bootstrapping**: Downloads Pathogen (`pathogen.vim`), clones/updates `vim-fugitive`, and clones `syntastic`.
- **Oh My Zsh Plugin Bootstrapping**: Clones/updates `zsh-autosuggestions` and `zsh-syntax-highlighting` into `~/.oh-my-zsh/custom/plugins`.
- **OS Package Checks**: Inspects system package availability (Homebrew on macOS; `apt`, `dnf`, or `pacman` on Linux).

```bash
# Run installation into $HOME
./install.sh

# Run installation into a custom target directory
./install.sh /custom/target/path
```

### `uninstall.sh`
Safely removes symlinks created by `install.sh` and restores original `.bak` configuration files and directories.

```bash
./uninstall.sh
```

---

## Key Features & Tools

### 1. Secret & SSH Key Guard (`check_secrets.sh`)
Scans repository or active configuration directories for SSH private keys, API tokens (AWS, GitHub, Slack, OpenAI, Anthropic, Stripe), and un-encrypted credentials to prevent accidental git leakage.

```bash
# Scan repository for secrets and SSH keys
./check_secrets.sh

# Scan a specific file or directory
./check_secrets.sh -t ~/my_project

# Output scan results in JSON format
./check_secrets.sh --json

# Suppress console output if no secrets are found
./check_secrets.sh --quiet

# Exit with non-zero status code (1) if secrets are found (ideal for CI/pre-commit)
./check_secrets.sh --exit-code
```

### 2. Active Config Diff Checker (`check_diffs.sh`)
Audits active configuration files in your home directory (`~`) against the tracked repository files and generates unified diffs.

```bash
# Print full diff report with color-coded unified diffs
./check_diffs.sh

# Print summary table of matched/modified/missing files only
./check_diffs.sh --summary-only

# Filter check to files matching a specific substring
./check_diffs.sh -f .bashrc

# Audit a custom target directory against a custom repo directory
./check_diffs.sh -t ~/custom_home -r /path/to/repo

# Export report to a text file or JSON format
./check_diffs.sh -o diff_report.txt
./check_diffs.sh --json

# Control terminal color output
./check_diffs.sh --color
./check_diffs.sh --no-color
```

### 3. Automated Daily Sync & Secret Guard (`sync_active_config.sh`)
Pulls active config changes from `$HOME` into the repo, scans modified files for secrets/keys, creates a new Git branch named `<machine-name>-<YYYY-MM-DD>`, commits the changes, and pushes to the remote repository.

```bash
# Run active config sync manually
./sync_active_config.sh

# Test sync without modifying files or git state
./sync_active_config.sh --dry-run

# Specify custom source directory, repo directory, or branch name
./sync_active_config.sh -s ~/ -r /path/to/repo -b my-custom-branch

# Commit changes locally without pushing to remote
./sync_active_config.sh --no-push

# Specify custom Git remote (default: origin)
./sync_active_config.sh --remote upstream

# Bypass Secret Guard scanner (use with caution!)
./sync_active_config.sh --allow-secrets

# Install automated daily cron job (runs automatically at 9:00 AM daily)
./sync_active_config.sh --install-cron
```

### 4. Interactive Git Untrack & Ignore (`git_untrack_ignore.sh`)
Interactive Zsh utility to untrack files currently committed to Git and append them to `.gitignore`.
- Uses `fzf` for fuzzy multi-selection if installed (press `Tab` to select multiple files).
- Falls back to a standard Zsh numbered menu if `fzf` is not available.

```bash
./git_untrack_ignore.sh
```

---

## Machine-Specific Customizations (`.local` pattern)

Both `.bashrc` and `.zshrc` automatically source un-tracked local override files if present in your home directory:
- `~/.bashrc.local`
- `~/.zshrc.local`

Use these files to define work-specific environment variables, private API tokens, local path additions, or machine-unique aliases without polluting your tracked dotfiles repository.

---

## Makefile Shortcuts & Testing

A `Makefile` is provided for quick access to core tasks and running unit tests:

```bash
make help           # Display available Makefile commands
make install        # Run dotfiles installer with symlinks & plugin setups
make uninstall      # Remove symlinks & restore original backups
make diff           # View diff report between active config and repo
make sync           # Run machine+date branch sync (with secret scan) & push
make cron           # Install daily automated cron job at 9:00 AM
make check-secrets  # Run Secret & SSH Key Guard scanner
make test           # Run full Python unit test suite
```

### Running Unit Tests
Unit tests are located in the [`tests/`](file:///home/mike/work/dotfiles/tests) directory and cover secret scanning, diff generation, install/uninstall behavior, and sync routines.

```bash
# Run unit test suite using unittest
python3 -m unittest discover tests

# Or run using pytest (pytest.ini configured)
pytest
```
