#!/usr/bin/env zsh

set -e

# 1. Ensure we are inside a Git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: Not inside a Git repository." >&2
  exit 1
fi

# 2. Get list of tracked files
tracked_files=($(git ls-files))

if [[ ${#tracked_files[@]} -eq 0 ]]; then
  echo "No tracked files found in this repository."
  exit 0
fi

selected_files=()

# 3. Interactive Selection (fzf preferred, fallback to Zsh select)
if command -v fzf >/dev/null 2>&1; then
  echo "Select file(s) to untrack and ignore (Press Tab to multi-select, Enter to confirm):"
  selected_files=($(git ls-files | fzf -m --prompt="Untrack & Ignore > "))
else
  echo "fzf is not installed. Using standard Zsh selection menu..."
  PS3="Select a file number to untrack and ignore (or type 'q' to quit): "
  select file in "${tracked_files[@]}"; do
    if [[ "$REPLY" == "q" ]]; then
      break
    elif [[ -n "$file" ]]; then
      selected_files+=("$file")
      break
    else
      echo "Invalid selection."
    fi
  done
fi

if [[ ${#selected_files[@]} -eq 0 ]]; then
  echo "No files selected. Exiting."
  exit 0
fi

echo "\nSelected file(s):"
for file in "${selected_files[@]}"; do
  echo "  - $file"
done

echo ""
read -q "reply?Do you want to untrack these file(s) and add them to .gitignore? (y/N) "
echo ""

if [[ "$reply" =~ ^[Yy]$ ]]; then
  gitignore_path="$(git rev-parse --show-toplevel)/.gitignore"

  for file in "${selected_files[@]}"; do
    # Remove from Git index
    git rm --cached "$file"

    # Avoid duplicate lines in .gitignore
    if ! grep -qxF "$file" "$gitignore_path" 2>/dev/null; then
      echo "$file" >> "$gitignore_path"
      echo "Added '$file' to .gitignore"
    else
      echo "'$file' is already in .gitignore"
    fi
  done

  # Stage .gitignore
  git add "$gitignore_path"
  
  echo ""
  read -q "commit_reply?Do you want to commit these changes now? (y/N) "
  echo ""
  if [[ "$commit_reply" =~ ^[Yy]$ ]]; then
    git commit -m "Untrack and ignore selected file(s)"
    echo "Changes committed successfully!"
  fi

  echo "Done!"
else
  echo "Operation cancelled."
fi
