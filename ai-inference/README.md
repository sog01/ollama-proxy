# ai-inference

Outbound-only inference node. Dials the public `proxy-inference` over WebSocket,
authenticates with `NODE_API_KEY`, registers locally-available Ollama models, then handles
forwarded requests by calling local Ollama and streaming the result back.

## Config (`.env`)

See `.env.example`. Required: `PROXY_WS_URL`, `NODE_API_KEY`. `NODE_ID` is auto-generated
if blank. `OLLAMA_BASE_URL` defaults to `http://localhost:11434`.

## Run

```bash
./scripts/check_deps.sh
source venv/bin/activate
python -m src.main
```

## Behavior

- Connects outbound to the proxy. Never listens.
- Auto-reconnect with exponential backoff + jitter (capped at `RECONNECT_MAX_BACKOFF`).
- Re-registers on every (re)connect; `models` list is refreshed from `GET /api/tags`.
- Replies to proxy `ping` with `pong`, sends `ping` itself on heartbeat interval.
