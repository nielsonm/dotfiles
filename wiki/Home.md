# Dotfiles Repository Wiki

Welcome to the **Dotfiles & Systems Automation Wiki**. This repository manages cross-platform shell configurations, editor settings, developer tooling, automated sync pipelines, secret leak prevention guards, and media library synchronization.

---

## Current Status Dashboard

| Component / System | Status | Key Script / Entry Point | Description |
| :--- | :---: | :--- | :--- |
| **Dotfiles Core** | ![Passing](https://img.shields.io/badge/status-active-success) | [`install.sh`](file:///home/mike/work/dotfiles/install.sh) | Symlinks configurations with automatic `.bak` backups |
| **Automated Testing** | ![95/95 Tests Passing](https://img.shields.io/badge/tests-95%2F95%20passing-brightgreen) | `make test` / `python3 -m unittest` | Full unittest discovery across 7 test modules |
| **Secret & SSH Guard** | ![Passing](https://img.shields.io/badge/security-enforced-blue) | [`check_secrets.py`](file:///home/mike/work/dotfiles/check_secrets.py) | Scans for API tokens, private SSH keys, and secrets |
| **Configuration Audit** | ![Passing](https://img.shields.io/badge/audit-active-blue) | [`check_diffs.py`](file:///home/mike/work/dotfiles/check_diffs.py) | Unified diff audit between `$HOME` and repository |
| **Daily Config Sync** | ![Scheduled](https://img.shields.io/badge/cron-09%3A00%20daily-orange) | [`sync_active_config.py`](file:///home/mike/work/dotfiles/sync_active_config.py) | Daily automated branch sync with secret safeguards |
| **VS Code Sync** | ![Scheduled](https://img.shields.io/badge/cron-07%3A00%20daily-orange) | [`vscode_sync.sh`](file:///home/mike/work/dotfiles/vscode_sync.sh) | Settings, keybindings, snippets, and extension backups |
| **Jellyfin File Compare** | ![Passing](https://img.shields.io/badge/tool-ready-blue) | [`jfFileCompare.py`](file:///home/mike/work/dotfiles/jfFileCompare.py) | Fast multi-threaded CIFS/local media synchronization |
| **Media Duplicate Scanner** | ![Passing](https://img.shields.io/badge/tool-ready-blue) | [`find_media_duplicates.py`](file:///home/mike/work/dotfiles/find_media_duplicates.py) | Safe, non-destructive duplicate media scanner & cleaner |

---

## Repository Architecture

```mermaid
graph TD
    subgraph Core ["Dotfiles Core"]
        A["install.sh"] --> B["$HOME Symlinks (.bashrc, .zshrc, .vim, .config)"]
        A --> C["Crontab Managed Block (07:00 & 09:00 Daily)"]
        D["uninstall.sh"] --> E["Restore Original .bak Files & Clean Crontab"]
    end

    subgraph Sync ["Automation & Security"]
        F["sync_active_config.py"] --> G["check_secrets.py (Security Gate)"]
        F --> H["check_diffs.py (Audit Drift)"]
        I["vscode_sync.sh"] --> J["VSCodeBackup/ (Settings, Extensions, Keybindings)"]
    end

    subgraph Media ["Media Tools"]
        K["jfFileCompare.py"] --> L["Jellyfin / CIFS Network Sync"]
        M["find_media_duplicates.py"] --> N["duplicates_report.txt & cleanup_duplicates.sh"]
    end

    subgraph Tests ["Quality Assurance (95 Tests)"]
        O["make test"] --> P["Unit Tests (test_*.py)"]
    end
```

---

## Active Crontab Configuration

The following automated jobs are scheduled in the user crontab:
```cron
# Daily VS Code settings and extension backup at 7:00 AM
0 7 * * * /bin/bash /home/mike/work/dotfiles/vscode_sync.sh backup >> /home/mike/work/dotfiles/vscode_backup.log 2>&1

# Daily active dotfiles pull, diff, secret scan, and branch sync at 9:00 AM
0 9 * * * /home/mike/work/dotfiles/sync_active_config.sh >> /home/mike/work/dotfiles/sync_cron.log 2>&1
```

---

## Wiki Pages Directory

- **[Installation and Setup](Installation-and-Setup)**: Step-by-step installation, restoration, Vim pathogen bootstrap, Oh My Zsh plugins, and crontab scheduling.
- **[Security and Audit Tools](Security-and-Audit-Tools)**: Complete guide on `check_secrets.py` pattern matching, entropy, ignore rules, and `check_diffs.py`.
- **[Configuration Sync](Configuration-Sync)**: Machine-and-date branch synchronization workflow, clean Git stash handling, and safety guards.
- **[VS Code Sync](VS-Code-Sync)**: Backing up and restoring VS Code configurations, keybindings, snippets, and marketplace extensions.
- **[Media Management Tools](Media-Management-Tools)**: Complete documentation for `jfFileCompare.py` (Jellyfin sync) and `find_media_duplicates.py` (safe multi-stage duplicate scanner).
- **[Testing and Quality Assurance](Testing-and-Quality-Assurance)**: Test structure, executing suites, fixture mock environments, and verification standards.
