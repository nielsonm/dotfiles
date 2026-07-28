#!/usr/bin/env bash
# Shell wrapper script for check_secrets.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/check_secrets.py" "$@"
