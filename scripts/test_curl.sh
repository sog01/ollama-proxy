#!/usr/bin/env bash
# Smoke-test the proxy from the client side.
# Mirrors the real Ollama API contract: no client-side auth header.
#
# Usage:
#   ./scripts/test_curl.sh                       # uses defaults below
#   MODEL=qwen2.5:3b-instruct ./scripts/test_curl.sh
#   PROXY_URL=http://host:8080 MODEL=llama3.1:8b ./scripts/test_curl.sh
#   ./scripts/test_curl.sh version|tags|chat-stream|chat|generate-stream|generate
set -euo pipefail

PROXY_URL="${PROXY_URL:-http://localhost:8080}"
MODEL="${MODEL:-llama3.1:8b}"

hdr() { printf "\n\033[1;34m== %s ==\033[0m\n" "$*"; }

cmd_version() {
  hdr "GET $PROXY_URL/api/version"
  curl -sS "$PROXY_URL/api/version" && echo
}

cmd_tags() {
  hdr "GET $PROXY_URL/api/tags"
  curl -sS "$PROXY_URL/api/tags" && echo
}

cmd_chat_stream() {
  hdr "POST $PROXY_URL/api/chat  (stream)  model=$MODEL"
  curl -sS -N "$PROXY_URL/api/chat" -d "{
  \"model\": \"$MODEL\",
  \"messages\": [{\"role\":\"user\",\"content\":\"say hello in 5 words\"}],
  \"stream\": true
}"
}

cmd_chat() {
  hdr "POST $PROXY_URL/api/chat  (non-stream)  model=$MODEL"
  curl -sS "$PROXY_URL/api/chat" -d "{
  \"model\": \"$MODEL\",
  \"messages\": [{\"role\":\"user\",\"content\":\"reply with OK only\"}],
  \"stream\": false
}" && echo
}

cmd_generate_stream() {
  hdr "POST $PROXY_URL/api/generate  (stream)  model=$MODEL"
  curl -sS -N "$PROXY_URL/api/generate" -d "{
  \"model\": \"$MODEL\",
  \"prompt\": \"Count from 1 to 5.\",
  \"stream\": true
}"
}

cmd_generate() {
  hdr "POST $PROXY_URL/api/generate  (non-stream)  model=$MODEL"
  curl -sS "$PROXY_URL/api/generate" -d "{
  \"model\": \"$MODEL\",
  \"prompt\": \"Reply with OK only.\",
  \"stream\": false
}" && echo
}

cmd_all() {
  cmd_version
  cmd_tags
  cmd_chat_stream
  echo
  cmd_chat
  cmd_generate_stream
  echo
  cmd_generate
}

case "${1:-all}" in
  version)         cmd_version ;;
  tags)            cmd_tags ;;
  chat-stream)     cmd_chat_stream ;;
  chat)            cmd_chat ;;
  generate-stream) cmd_generate_stream ;;
  generate)        cmd_generate ;;
  all|"")          cmd_all ;;
  *) echo "unknown subcommand: $1" >&2
     echo "usage: $0 [version|tags|chat-stream|chat|generate-stream|generate|all]" >&2
     exit 2 ;;
esac
