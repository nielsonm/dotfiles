#!/usr/bin/env bash
# Uninstall script to remove symlinks created by install.sh and restore backups (.bak).
set -euo pipefail

DEST_DIR="${1:-$HOME}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo " Uninstalling dotfiles from: ${DEST_DIR}"
echo "========================================="

FILES_TO_UNLINK=(
  ".bash_profile"
  ".bashrc"
  ".git-completion.bash"
  ".gitignore_global"
  ".vimrc"
  ".zshrc"
  ".tmux.conf"
  ".drush.aliases.drushrc.php"
  ".shell.pre-oh-my-zsh"
  "bash_prompt.sh"
  "funzies.sh"
  "print_colors.sh"
)

DIRS_TO_UNLINK=(
  ".drush"
  ".vim"
  ".config"
)

echo "--> Removing file symlinks and restoring backups..."
for file in "${FILES_TO_UNLINK[@]}"; do
  dest="${DEST_DIR}/${file}"
  backup="${dest}.bak"

  # Remove symlink if it points to this repo or exists as symlink
  if [ -L "${dest}" ]; then
    rm -f "${dest}"
    echo "  [Removed Link] ${dest}"
  fi

  # Restore backup file if present
  if [ -f "${backup}" ]; then
    mv "${backup}" "${dest}"
    echo "  [Restored Backup] ${backup} -> ${dest}"
  fi
done

echo "--> Removing directory symlinks and restoring backups..."
for dir in "${DIRS_TO_UNLINK[@]}"; do
  dest="${DEST_DIR}/${dir}"
  backup="${dest}.bak"

  if [ -L "${dest}" ]; then
    rm -f "${dest}"
    echo "  [Removed Directory Link] ${dest}"
  fi

  if [ -d "${backup}" ]; then
    mv "${backup}" "${dest}"
    echo "  [Restored Directory Backup] ${backup} -> ${dest}"
  fi
done

echo ""
echo "========================================="
echo " Uninstallation & Restoration Complete!"
echo "========================================="
