#!/usr/bin/env bash
# Bootstrap proxy-inference venv + deps + .env
set -euo pipefail

SVC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SVC_DIR"

OS="$(uname -s)"
case "$OS" in
  Darwin|Linux) ;;
  *) echo "[err] Unsupported OS: $OS (macOS/Ubuntu only)" >&2; exit 1;;
esac

log() { printf "\033[1;34m[proxy-inference]\033[0m %s\n" "$*"; }

if [ ! -d venv ]; then
  log "Creating venv"
  python3 -m venv venv
else
  log "venv exists"
fi

# shellcheck disable=SC1091
source venv/bin/activate

log "pip install -r requirements.txt"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  log ".env created from .env.example — EDIT IT to set PROXY_NODE_API_KEY"
else
  log ".env present"
fi

log "Ready. Run:"
echo "    cd $SVC_DIR && source venv/bin/activate && python -m uvicorn src.main:app --host 0.0.0.0 --port 8080"
