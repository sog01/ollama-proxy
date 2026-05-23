#!/usr/bin/env bash
# Bootstrap ai-inference venv + deps + .env
set -euo pipefail

SVC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SVC_DIR"

OS="$(uname -s)"
case "$OS" in
  Darwin|Linux) ;;
  *) echo "[err] Unsupported OS: $OS (macOS/Ubuntu only)" >&2; exit 1;;
esac

log()  { printf "\033[1;34m[ai-inference]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[ai-inference]\033[0m %s\n" "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# Use sudo only if not root AND sudo exists. Root containers often lack sudo.
if [ "$(id -u)" -eq 0 ] || ! have sudo; then
  SUDO=""
else
  SUDO="sudo"
fi

install_zstd() {
  if have zstd; then
    log "zstd present"
    return
  fi
  case "$OS" in
    Darwin)
      if ! have brew; then
        echo "[err] Homebrew required to install zstd on macOS. https://brew.sh" >&2
        exit 1
      fi
      log "brew install zstd"
      brew install zstd
      ;;
    Linux)
      log "apt-get install zstd"
      $SUDO apt-get update
      $SUDO apt-get install -y zstd
      ;;
  esac
}

install_ollama() {
  if have ollama; then
    log "ollama CLI present"
    return
  fi
  case "$OS" in
    Darwin)
      if ! have brew; then
        echo "[err] Homebrew required to install ollama on macOS. https://brew.sh" >&2
        exit 1
      fi
      log "brew install ollama"
      brew install ollama
      ;;
    Linux)
      log "curl https://ollama.com/install.sh | sh"
      curl -fsSL https://ollama.com/install.sh | sh
      ;;
  esac
}

# Ollama needs zstd for model decompression. Install zstd first, then ollama.
install_zstd
install_ollama

if curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
  log "local Ollama responding on :11434"

  # Pre-pull default models. Skip failing ones (network, name change) — don't abort bootstrap.
  MODELS=(
    "glm-4.7-flash"           # user-requested
    "qwen2.5-coder:7b"        # strong coding model, Alibaba
    "deepseek-coder-v2:16b"   # strong coding model, DeepSeek (MoE lite)
  )
  for m in "${MODELS[@]}"; do
    if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$m"; then
      log "model present: $m"
    else
      log "ollama pull $m"
      ollama pull "$m" || warn "pull failed for $m — skipping"
    fi
  done
else
  warn "ollama installed but not reachable at http://localhost:11434 — start it before running ai-inference (model pulls skipped)"
fi

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
  log ".env created from .env.example — EDIT IT to set PROXY_WS_URL and NODE_API_KEY"
else
  log ".env present"
fi

log "Ready. Run:"
echo "    cd $SVC_DIR && source venv/bin/activate && python -m src.main"
