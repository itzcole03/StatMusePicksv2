#!/usr/bin/env bash
# Simple runner for cron/systemd on Linux/macOS.
# Activates `.venv` if present and calls the backend CLI to run the daily sync.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$REPO_ROOT/.venv"

export PYTHONUNBUFFERED=1

if [[ -f "$VENV_PATH/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$VENV_PATH/bin/activate"
fi

cd "$REPO_ROOT"

# Optional: pass YYYY-MM-DD as first arg to run for a specific date
if [[ ${1:-} ]]; then
  python -m backend.cli.run_daily_sync --when "$1"
else
  python -m backend.cli.run_daily_sync
fi
