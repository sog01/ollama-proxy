#!/usr/bin/env bash
# Top-level bootstrap. Detect OS, ensure system deps, then bootstrap each service.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OS="$(uname -s)"
log() { printf "\033[1;34m[deps]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[err]\033[0m %s\n" "$*" 1>&2; }

have() { command -v "$1" >/dev/null 2>&1; }

# Use sudo only if not root AND sudo exists. Root containers often lack sudo.
if [ "$(id -u)" -eq 0 ] || ! have sudo; then
  SUDO=""
else
  SUDO="sudo"
fi

py_min_ok() {
  # require python3 >= 3.10
  local v
  v="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"
  python3 - <<'PY' "$v"
import sys
v = tuple(int(x) for x in sys.argv[1].split("."))
sys.exit(0 if v >= (3,10) else 1)
PY
}

install_macos() {
  if ! have brew; then
    err "Homebrew not found. Install from https://brew.sh and re-run."
    exit 1
  fi
  local pkgs=()
  have python3 || pkgs+=(python@3.11)
  have git || pkgs+=(git)
  have curl || pkgs+=(curl)
  have vim || pkgs+=(vim)
  if [ "${#pkgs[@]}" -gt 0 ]; then
    log "brew install ${pkgs[*]}"
    brew install "${pkgs[@]}"
  fi
}

install_ubuntu() {
  local pkgs=()
  have python3 || pkgs+=(python3)
  # python3-venv ships venv module
  python3 -c "import venv" 2>/dev/null || pkgs+=(python3-venv)
  have pip3 || pkgs+=(python3-pip)
  have git || pkgs+=(git)
  have curl || pkgs+=(curl)
  have vim || pkgs+=(vim)
  if [ "${#pkgs[@]}" -gt 0 ]; then
    log "apt-get install ${pkgs[*]}"
    $SUDO apt-get update
    $SUDO apt-get install -y "${pkgs[@]}"
  fi
}

case "$OS" in
  Darwin)
    log "Detected macOS"
    install_macos
    ;;
  Linux)
    if [ -f /etc/os-release ] && grep -qi ubuntu /etc/os-release; then
      log "Detected Ubuntu"
      install_ubuntu
    else
      err "Linux distro not supported (Ubuntu only). /etc/os-release does not look like Ubuntu."
      exit 1
    fi
    ;;
  *)
    err "Unsupported OS: $OS. macOS and Ubuntu only."
    exit 1
    ;;
esac

# Verify versions
if ! py_min_ok; then
  err "python3 >= 3.10 required."
  exit 1
fi
log "python3 $(python3 -V 2>&1 | awk '{print $2}') ok"

# Delegate to per-service bootstrap
log "Bootstrapping proxy-inference"
"$ROOT_DIR/proxy-inference/scripts/check_deps.sh"

log "Bootstrapping ai-inference"
"$ROOT_DIR/ai-inference/scripts/check_deps.sh"

log "All done."
