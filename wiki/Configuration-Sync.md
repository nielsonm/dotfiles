# Automated Configuration Synchronization

The configuration sync pipeline maintains up-to-date dotfiles across multiple machines without committing secrets or breaking working directory states.

---

## 1. Overview (`sync_active_config.py`)

Located at [`sync_active_config.py`](https://github.com/nielsonm/dotfiles/blob/main/sync_active_config.py) (wrapper: [`sync_active_config.sh`](https://github.com/nielsonm/dotfiles/blob/main/sync_active_config.sh)).

### Architecture:
1. **Pull Active Files**: Copies tracked files from `$HOME` into the local repository clone.
2. **Security Gate**: Runs [`check_secrets.py`](https://github.com/nielsonm/dotfiles/blob/main/check_secrets.py) against every pulled file. If any file contains a secret or private key, it is blocked from being staged or committed.
3. **Machine & Date Branching**:
   - Generates a dedicated branch named: `<Hostname>-<YYYY-MM-DD>` (e.g. `Mike-FW-Laptop-13th-Gen-Intel-Core-2026-11-02`).
   - Stashes uncommitted working tree changes safely before checkout.
   - Commits changes to the machine branch.
   - Restores stashed changes and returns to the initial branch.
4. **Push to Remote**: Pushes the machine branch to GitHub for review and PR merging.

---

## 2. Usage & CLI Flags

```bash
# Perform manual configuration sync
./sync_active_config.sh
# or via Makefile
make sync

# Dry-run preview mode (shows changes without modifying git branches or pushing)
./sync_active_config.sh --dry-run

# Run sync and install daily cron job
./sync_active_config.sh --install-cron
```

---

## 3. Automated Cron Execution

The daily cron job runs at 9:00 AM:
```cron
0 9 * * * /home/mike/work/dotfiles/sync_active_config.sh >> /home/mike/work/dotfiles/sync_cron.log 2>&1
```
Execution results and secret scan warnings are written to [`sync_cron.log`](https://github.com/nielsonm/dotfiles/blob/main/sync_cron.log).
