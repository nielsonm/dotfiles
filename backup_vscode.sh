#!/bin/bash
# Script to backup and restore VS Code settings, keybindings, snippets, and extensions.

# Paths
SOURCE_DIR="$HOME/.config/Code/User" # Use "$HOME/.config/Code/User" for Linux
BACKUP_DIR="$HOME/work/dotfiles/VSCodeBackup"

# Main script
if [ "$1" == "backup" ]; then
    echo "Starting VS Code Backup..."
    mkdir -p "$BACKUP_DIR"
    cp "$SOURCE_DIR/settings.json" "$BACKUP_DIR/" 2>/dev/null
    cp "$SOURCE_DIR/keybindings.json" "$BACKUP_DIR/" 2>/dev/null
    cp -r "$SOURCE_DIR/snippets" "$BACKUP_DIR/" 2>/dev/null
    # Export extension list
    code --list-extensions > "$BACKUP_DIR/extensions.txt"
    echo "Backup completed successfully to $BACKUP_DIR!"
# Restore script
elif [ "$1" == "restore" ]; then
    echo "Starting VS Code Restore..."
    if [ ! -d "$BACKUP_DIR" ]; then
        echo "Error: Backup directory $BACKUP_DIR does not exist."
        exit 1
    fi
    # Create the source directory if it doesn't exist
    mkdir -p "$SOURCE_DIR"
    cp "$BACKUP_DIR/settings.json" "$SOURCE_DIR/" 2>/dev/null
    cp "$BACKUP_DIR/keybindings.json" "$SOURCE_DIR/" 2>/dev/null
    cp -r "$BACKUP_DIR/snippets" "$SOURCE_DIR/" 2>/dev/null
    # Restore extensions
    if [ -f "$BACKUP_DIR/extensions.txt" ]; then
        echo "Installing extensions..."
        xargs -L 1 code --install-extension < "$BACKUP_DIR/extensions.txt"
    fi
    echo "Restore completed successfully!"

else
    echo "Usage: ./vscode_sync.sh [backup|restore]"
fi

