#!/usr/bin/env bash
# Shell wrapper script for sync_active_config.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/sync_active_config.py" "$@"
