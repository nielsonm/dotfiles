#!/usr/bin/env bash
# Installation script to safely install dotfiles across macOS (OSX) and Linux environments.
set -euo pipefail

# Detect Operating System
OS_NAME="$(uname -s)"
case "${OS_NAME}" in
  Darwin*)  IS_OSX=true;  IS_LINUX=false; PLATFORM="macOS" ;;
  Linux*)   IS_OSX=false; IS_LINUX=true;  PLATFORM="Linux" ;;
  *)        IS_OSX=false; IS_LINUX=false; PLATFORM="Unknown (${OS_NAME})" ;;
esac

echo "========================================="
echo " Installing dotfiles for: ${PLATFORM}"
echo "========================================="

# Set source and destination directories
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${1:-$HOME}"

echo "Source Directory     : ${SRC_DIR}"
echo "Destination Directory: ${DEST_DIR}"
echo ""

mkdir -p "${DEST_DIR}"

# Files to link/copy into home directory
FILES_TO_LINK=(
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

# Subdirectories to link/copy
DIRS_TO_LINK=(
  ".drush"
  ".vim"
  ".config"
)

# Portable symlink function handling BSD (macOS) vs GNU (Linux) ln flags
safe_symlink() {
  local target="$1"
  local link_name="$2"

  if [ "${IS_OSX}" = true ]; then
    # macOS BSD ln uses -h to avoid following existing symlinks to directories
    ln -sfh "${target}" "${link_name}"
  else
    # Linux GNU ln uses -n to avoid following existing symlinks to directories
    ln -sfn "${target}" "${link_name}"
  fi
}

echo "--> Setting up file symlinks..."
for file in "${FILES_TO_LINK[@]}"; do
  src="${SRC_DIR}/${file}"
  dest="${DEST_DIR}/${file}"

  if [ -f "${src}" ]; then
    if [ -f "${dest}" ] && [ ! -L "${dest}" ]; then
      echo "  [Backup] Moving existing ${dest} to ${dest}.bak"
      mv "${dest}" "${dest}.bak"
    fi
    safe_symlink "${src}" "${dest}"
    echo "  [Link] ${file} -> ${dest}"
  fi
done

echo "--> Setting up directory symlinks..."
for dir in "${DIRS_TO_LINK[@]}"; do
  src="${SRC_DIR}/${dir}"
  dest="${DEST_DIR}/${dir}"

  if [ -d "${src}" ]; then
    if [ -d "${dest}" ] && [ ! -L "${dest}" ]; then
      echo "  [Backup] Moving existing directory ${dest} to ${dest}.bak"
      mv "${dest}" "${dest}.bak"
    fi
    safe_symlink "${src}" "${dest}"
    echo "  [Link] ${dir}/ -> ${dest}/"
  fi
done

# Set up .gitconfig template if no active gitconfig exists
if [ -f "${SRC_DIR}/.gitconfig.safe" ] && [ ! -f "${DEST_DIR}/.gitconfig" ]; then
  cp "${SRC_DIR}/.gitconfig.safe" "${DEST_DIR}/.gitconfig"
  echo "  [Copy] .gitconfig.safe -> ${DEST_DIR}/.gitconfig"
fi

# Vim Pathogen & Plugins setup
echo ""
echo "--> Setting up Vim plugins (Pathogen, Fugitive, Syntastic)..."
mkdir -p "${DEST_DIR}/.vim/autoload" "${DEST_DIR}/.vim/bundle" "${DEST_DIR}/.vim/pack/tpope/start"

if command -v curl >/dev/null 2>&1; then
  curl -LSso "${DEST_DIR}/.vim/autoload/pathogen.vim" https://tpo.pe/pathogen.vim || true
fi

FUGITIVE_DIR="${DEST_DIR}/.vim/pack/tpope/start/fugitive"
if [ ! -d "${FUGITIVE_DIR}" ]; then
  git clone https://tpope.io/vim/fugitive.git "${FUGITIVE_DIR}" || true
else
  (cd "${FUGITIVE_DIR}" && git pull --quiet || true)
fi

if command -v vim >/dev/null 2>&1; then
  vim -u NONE -c "helptags ${FUGITIVE_DIR}/doc" -c q || true
fi

SYNTASTIC_DIR="${DEST_DIR}/.vim/bundle/syntastic"
if [ ! -d "${SYNTASTIC_DIR}" ]; then
  git clone --depth=1 https://github.com/vim-syntastic/syntastic.git "${SYNTASTIC_DIR}" || true
else
  (cd "${SYNTASTIC_DIR}" && git pull --quiet || true)
fi

# OS-Specific Package Manager & Setup Steps
echo ""
echo "--> Running OS-specific setup for ${PLATFORM}..."

if [ "${IS_OSX}" = true ]; then
  echo "  [macOS] Checking Homebrew installation..."
  if ! command -v brew >/dev/null 2>&1; then
    echo "  [macOS] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  else
    echo "  [macOS] Homebrew is already installed: $(brew --version | head -n1)"
  fi

elif [ "${IS_LINUX}" = true ]; then
  echo "  [Linux] Checking system packages..."
  if command -v apt-get >/dev/null 2>&1; then
    echo "  [Debian/Ubuntu Linux detected]"
    # Ensure essential tools exist
    for pkg in git curl build-essential; do
      if ! dpkg -s "${pkg}" >/dev/null 2>&1; then
        echo "  [Notice] Package '${pkg}' is not installed. Run 'sudo apt-get install ${pkg}' if needed."
      fi
    done
  elif command -v dnf >/dev/null 2>&1; then
    echo "  [Fedora/RHEL Linux detected]"
  elif command -v pacman >/dev/null 2>&1; then
    echo "  [Arch Linux detected]"
  fi
fi

echo ""
echo "========================================="
echo " Installation Complete for ${PLATFORM}!"
echo "========================================="
