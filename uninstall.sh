#!/usr/bin/env bash
# Uninstall script to remove symlinks created by install.sh and restore backups (.bak).
set -euo pipefail

# Parse arguments
DEST_DIR=""
REMOVE_CRON=true
if [ "${SKIP_CRON:-false}" = "true" ] || [ "${SKIP_CRON:-0}" = "1" ]; then
  REMOVE_CRON=false
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --no-cron)
      REMOVE_CRON=false
      shift
      ;;
    --with-cron)
      REMOVE_CRON=true
      shift
      ;;
    -h|--help)
      echo "Usage: ./uninstall.sh [DEST_DIR] [--no-cron]"
      exit 0
      ;;
    *)
      if [ -z "${DEST_DIR}" ]; then
        DEST_DIR="$1"
      fi
      shift
      ;;
  esac
done

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${DEST_DIR:-$HOME}"

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

# Automated crontab removal
remove_crontab() {
  echo ""
  echo "--> Removing dotfiles crontab jobs..."
  if [ "${REMOVE_CRON}" != true ]; then
    echo "  [Crontab] Skipped (--no-cron or SKIP_CRON specified)."
    return 0
  fi

  if ! command -v crontab >/dev/null 2>&1; then
    echo "  [Crontab] Notice: 'crontab' command not found. Skipping."
    return 0
  fi

  local existing_cron
  existing_cron="$(crontab -l 2>/dev/null || true)"

  if ! echo "${existing_cron}" | grep -q "BEGIN DOTFILES MANAGED BLOCK"; then
    echo "  [Crontab] No dotfiles managed crontab block found."
    return 0
  fi

  local clean_cron
  clean_cron="$(echo "${existing_cron}" | sed '/# BEGIN DOTFILES MANAGED BLOCK/,/# END DOTFILES MANAGED BLOCK/d' || true)"
  local remaining_lines
  remaining_lines="$(echo "${clean_cron}" | grep -v '^[[:space:]]*$' || true)"

  if [ -z "${remaining_lines}" ]; then
    crontab -r 2>/dev/null || true
    echo "  [Crontab] Removed dotfiles crontab block (crontab is now empty)."
  else
    echo "${clean_cron}" | crontab -
    echo "  [Crontab] Removed dotfiles crontab block (preserved other user jobs)."
  fi
}

remove_crontab

echo ""
echo "========================================="
echo " Uninstallation & Restoration Complete!"
echo "========================================="
