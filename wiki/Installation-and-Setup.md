# Installation & Setup Guide

The dotfiles repository provides an idempotent, non-destructive installer ([`install.sh`](https://github.com/nielsonm/dotfiles/blob/main/install.sh)) and a full restore utility ([`uninstall.sh`](https://github.com/nielsonm/dotfiles/blob/main/uninstall.sh)).

---

## Prerequisites

- **OS**: macOS (OSX) or Linux (Ubuntu, Debian, Fedora, Arch)
- **Shell**: Bash 4.0+ or Zsh 5.0+
- **Python**: Python 3.10+ (required for sync, secret scanner, diff auditor, and media tools)
- **Git**: Git 2.20+
- **Cron**: `cron` daemon active for automated daily scheduling

---

## 1. Quick Installation

```bash
# Clone the repository
git clone https://github.com/nielsonm/dotfiles.git ~/work/dotfiles
cd ~/work/dotfiles

# Run installer
./install.sh
# or via Makefile
make install
```

### What `install.sh` Does:
1. **Backs Up Existing Files**: If any target configuration (e.g. `~/.bashrc`, `~/.zshrc`, `~/.vimrc`) exists and is not already a symlink, it is safely moved to `<file>.bak`.
2. **Creates Symlinks**: Creates atomic relative symlinks from `$HOME` into `~/work/dotfiles`.
3. **Bootstraps Vim**:
   - Downloads Pathogen (`pathogen.vim`) if not present.
   - Bootstraps `vim-fugitive` and `syntastic` into `~/.vim/bundle/`.
4. **Bootstraps Oh My Zsh Plugins**:
   - Clones `zsh-autosuggestions` and `zsh-syntax-highlighting` into `~/.oh-my-zsh/custom/plugins/`.
5. **Configures Crontab**:
   - Inserts a managed block into user crontab for daily sync (9:00 AM) and VS Code backup (7:00 AM).

---

## 2. Installation Options

```bash
# Skip crontab modification during install
./install.sh --no-cron
# or
SKIP_CRON=true ./install.sh

# Install into a custom destination directory (used for testing or sandboxes)
./install.sh /path/to/target/home
```

---

## 3. Uninstallation & Restoration

```bash
# Remove all symlinks, restore .bak files, and clean crontab
./uninstall.sh
# or via Makefile
make uninstall

# Uninstall without modifying crontab
./uninstall.sh --no-cron
```

The uninstaller removes only the managed symlinks and the `# BEGIN DOTFILES MANAGED BLOCK` in `crontab`, leaving all independent user cron jobs untouched.
