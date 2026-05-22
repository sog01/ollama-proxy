# ollama-proxy

Reverse-tunnel inference gateway. An Ollama-compatible HTTP front-end (`proxy-inference`)
fronts one or more GPU/inference nodes (`ai-inference`) that have **zero inbound
connectivity**. The AI node dials *out* to the proxy over a persistent WebSocket and
registers itself; the proxy multiplexes Ollama API requests over that single socket.

```
client (curl / Open WebUI / SDK)
        │  HTTP (Ollama API)
        ▼
proxy-inference  (public, FastAPI)
        ▲
        │  WebSocket (AI node dials out)
        │
ai-inference     (behind NAT, outbound only)
        │  HTTP localhost
        ▼
local Ollama (:11434)
```

## Quickstart

Use the Makefile for the common flow:

```bash
make check-deps          # bootstrap system deps + both service venvs + seed .env files
$EDITOR proxy-inference/.env
$EDITOR ai-inference/.env

make run-proxy           # terminal 1 — public host
make run-ai              # terminal 2 — GPU box, behind NAT
```

`make run-proxy` / `make run-ai` auto-bootstrap the venv if it's missing, so a fresh
checkout can go straight to `make run-proxy`. Override host/port with
`make run-proxy PROXY_HOST=127.0.0.1 PROXY_PORT=9000`. Run `make help` for the full list.

Manual equivalent without Make:

```bash
./scripts/check_deps.sh

# terminal 1 — proxy
cd proxy-inference && source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080

# terminal 2 — AI node
cd ai-inference && source venv/bin/activate
python -m src.main
```

## Smoke tests

`scripts/test_curl.sh` runs curl against the proxy. HTTP endpoints have no client auth
(mirrors real Ollama).

```bash
make test                            # version + tags + chat (stream/unary) + generate
make test-tags
make test-chat-stream MODEL=qwen2.5:3b-instruct
make test-chat        MODEL=qwen2.5:3b-instruct
make test-generate-stream MODEL=qwen2.5:3b-instruct

# overrides
PROXY_URL=http://proxy.example.com:8080 MODEL=llama3.1:8b \
  ./scripts/test_curl.sh chat-stream
```

Or by hand with the standard Ollama contract:

```bash
curl http://localhost:8080/api/chat -d '{
  "model": "llama3.1:8b",
  "messages": [{"role":"user","content":"hello"}],
  "stream": true
}'
```

> The AI-node ↔ proxy WebSocket still requires `Bearer $PROXY_NODE_API_KEY` — that
> auth is mandatory because the proxy is publicly reachable. Restrict client access by
> putting the proxy behind a reverse proxy / VPN / network ACL.

See `proxy-inference/README.md` and `ai-inference/README.md` for service-specific docs.

## Supported OS

macOS and Ubuntu Linux only. Bootstrap scripts exit on anything else.
