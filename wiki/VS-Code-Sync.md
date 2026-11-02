# Visual Studio Code Synchronization

VS Code settings, keybindings, code snippets, and installed extensions are synchronized and backed up via [`vscode_sync.sh`](file:///home/mike/work/dotfiles/vscode_sync.sh) (aliased to `backup_vscode.sh`).

---

## 1. Directory Structure

Stored under [`VSCodeBackup/`](file:///home/mike/work/dotfiles/VSCodeBackup):
```
VSCodeBackup/
├── settings.json       # User settings
├── keybindings.json    # Custom keyboard shortcuts
├── snippets/           # User snippet definitions
└── extensions.txt      # Installed marketplace extension list
```

---

## 2. Usage

### Backup Settings & Extensions:
```bash
./vscode_sync.sh backup
# or using legacy name
./backup_vscode.sh backup
```
- Copies `settings.json`, `keybindings.json`, and `snippets/` from `~/.config/Code/User`.
- Runs `code --list-extensions` to record all installed extensions in `extensions.txt`.

### Restore Settings & Reinstall Extensions:
```bash
./vscode_sync.sh restore
```
- Creates `~/.config/Code/User` if missing.
- Copies backed up JSON configuration files and snippets into place.
- Reinstalls all extensions listed in `extensions.txt` using `xargs -L 1 code --install-extension`.

---

## 3. Automated Backup Cron

Configured via [`install.sh#L235`](file:///home/mike/work/dotfiles/install.sh#L235):
```cron
0 7 * * * /bin/bash /home/mike/work/dotfiles/vscode_sync.sh backup >> /home/mike/work/dotfiles/vscode_backup.log 2>&1
```
Runs daily at 7:00 AM, logging backup status to [`vscode_backup.log`](file:///home/mike/work/dotfiles/vscode_backup.log).
