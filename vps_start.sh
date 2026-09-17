#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON="${PYTHON_BIN:-python3}"
VENV_DIR="$PROJECT_DIR/.venv"

if ! command -v "$PYTHON" >/dev/null 2>&1 && [[ ! -x "$PYTHON" ]]; then
  echo "[setup] Python executable not found: $PYTHON" >&2
  exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
  echo "[setup] Python 3.11 or newer is required." >&2
  "$PYTHON" --version >&2 || true
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "[setup] Creating Python virtual environment at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"

if [[ ! -f "$PROJECT_DIR/requirements.txt" ]]; then
  echo "[setup] requirements.txt was not found in $PROJECT_DIR" >&2
  exit 1
fi

# NexCloud's generic template can inject stale package names through
# PY_PACKAGES. Do not let that unrelated value affect this application;
# install only the dependencies declared by this repository.
unset PY_PACKAGES
export CASINO_NON_INTERACTIVE=1

echo "[setup] Installing dependencies from requirements.txt"
# Some hosting panels set pip's global `user = true` option. That cannot be
# used from a virtualenv, so explicitly keep the install inside this venv.
# Do not self-upgrade pip here: a VPS package mirror can make that unrelated
# network request block the bot before its real dependencies are installed.
"$VENV_PYTHON" -m pip install --no-user --no-cache-dir -r requirements.txt

echo "[setup] Verifying imports"
"$VENV_PYTHON" - <<'PY'
import flask
import httpx
import qrcode
import requests
import telegram
from PIL import Image

print(f"[setup] Python dependency check passed ({telegram.__version__=})")
PY

export PYTHON_BIN="$VENV_PYTHON"
exec bash "$PROJECT_DIR/run.sh"