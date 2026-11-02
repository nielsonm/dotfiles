# Testing & Quality Assurance

The dotfiles repository maintains an automated Python test suite using standard `unittest`.

---

## 1. Running the Test Suite

Run all tests via `Makefile` or `unittest`:
```bash
# Run full suite via make
make test

# Or run directly via Python
python3 -m unittest discover tests

# Run in verbose mode
python3 -m unittest discover -v tests
```

---

## 2. Test Suite Breakdown (95 Tests Total)

| Test Module | Coverage Area | Key Verification Scenarios |
| :--- | :--- | :--- |
| **[`test_wiki.py`](https://github.com/nielsonm/dotfiles/blob/main/tests/test_wiki.py)** | GitHub Wiki Validation | Verifies `Home.md`, `_Sidebar.md`, `_Footer.md`, clean HTML compilation of all Markdown, internal & file link integrity, code fence balancing, and navigation sidebar validation. |
| **[`test_find_media_duplicates.py`](https://github.com/nielsonm/dotfiles/blob/main/tests/test_find_media_duplicates.py)** | Duplicate Media Scanner | Two-stage hashing, cross-format (`.epub`/`.azw3`), episode separation (`S01E01` != `S01E02`), VobSub pairing, `.filepart` detection, non-destructive `# rm` generation. |
| **[`test_jf_file_compare.py`](https://github.com/nielsonm/dotfiles/blob/main/tests/test_jf_file_compare.py)** | Jellyfin CIFS Sync | Extension presets, metadata caching, probe performance, sample hashing, dry-run synchronization plans. |
| **[`test_check_secrets.py`](https://github.com/nielsonm/dotfiles/blob/main/tests/test_check_secrets.py)** | Secret & SSH Key Scanner | Signature patterns (AWS, GitHub, Slack, OpenAI, SSH private keys), Shannon entropy detection, JSON formatting, exit code flags. |
| **[`test_check_diffs.py`](https://github.com/nielsonm/dotfiles/blob/main/tests/test_check_diffs.py)** | Config Drift Auditor | Home directory comparison, unified diff generation, missing/added file detection, output report generation. |
| **[`test_sync_active_config.py`](https://github.com/nielsonm/dotfiles/blob/main/tests/test_sync_active_config.py)** | Active Config Sync | Pulling tracked configs, secret gate enforcement, stash handling, machine-and-date branch creation. |
| **[`test_install_uninstall.py`](https://github.com/nielsonm/dotfiles/blob/main/tests/test_install_uninstall.py)** | Install & Uninstall | Symlink creation, `.bak` backup/restore, crontab managed block creation and idempotency, `--no-cron` flag. |

---

## 3. Test Design Principles

- **Zero Global Side-Effects**: All tests use `tempfile.TemporaryDirectory()` for mocks and sandboxes.
- **Mocked Git & Cron**: System state mutations (e.g. `crontab -l`, `git stash`) are tested against isolated mock scripts and files.
- **Fast Execution**: Full 90-test suite runs in under 15 seconds.
