# Security & Audit Tools

The repository includes proactive security auditing to prevent accidental commit of API credentials, tokens, and private keys into public or shared version control.

---

## 1. Secret & SSH Key Guard (`check_secrets.py`)

### Overview
Located at [`check_secrets.py`](file:///home/mike/work/dotfiles/check_secrets.py) (wrapper: [`check_secrets.sh`](file:///home/mike/work/dotfiles/check_secrets.sh)). Scans directories or specific files against signature patterns and Shannon entropy thresholds.

### Detection Signatures:
- **SSH Private Keys**: OpenSSH, RSA, DSA, EC, PGP, and Putty PPK private keys.
- **Cloud Provider Keys**:
  - AWS Access Key IDs (`AKIA...`, `ASIA...`) & Secret Access Keys
  - Google Cloud Service Account Keys, API keys (`AIza...`)
  - Azure Shared Access Signatures, Client Secrets
- **AI & Developer API Tokens**:
  - OpenAI (`sk-...`, `sk-proj-...`)
  - Anthropic (`sk-ant-...`)
  - GitHub Personal Access Tokens (`ghp_...`, `gho_...`, `github_pat_...`)
  - Slack API tokens (`xoxb-...`, `xoxp-...`, `xoxa-...`)
  - Stripe Live & Secret API Keys (`sk_live_...`, `rk_live_...`)
  - Generic High-Entropy API Secrets & Passwords in plaintext configs

### Usage
```bash
# Scan repository root
./check_secrets.sh

# Scan target path
./check_secrets.sh -t ~/.config

# Output in JSON format (for automation pipelines)
./check_secrets.sh --json

# Return non-zero exit code on detected secrets (ideal for pre-commit hooks)
./check_secrets.sh --exit-code

# Quiet mode (only outputs if secrets are found)
./check_secrets.sh --quiet
```

---

## 2. Active Config Drift Auditor (`check_diffs.py`)

### Overview
Located at [`check_diffs.py`](file:///home/mike/work/dotfiles/check_diffs.py) (wrapper: [`check_diffs.sh`](file:///home/mike/work/dotfiles/check_diffs.sh)). Compares currently active system files in `$HOME` against the repository copies to detect uncommitted drift or changes made directly outside the repo.

### Features:
- Detects modified, added, and missing files.
- Generates clean, colorized unified diffs.
- Writes full inspection reports to [`diff_report.txt`](file:///home/mike/work/dotfiles/diff_report.txt).

### Usage
```bash
# Generate diff report between active configs and repository
./check_diffs.sh
# or via Makefile
make diff

# Inspect saved diff report
cat diff_report.txt
```
