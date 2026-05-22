# proxy-inference

Public-facing Ollama-compatible HTTP gateway. Accepts standard Ollama API requests on
:8080 and forwards them to AI nodes over an authenticated WebSocket the nodes opened
themselves.

## Endpoints

| Method | Path                | Notes                                                 |
|--------|---------------------|-------------------------------------------------------|
| GET    | `/`                 | Returns `Ollama is running` (health)                  |
| GET    | `/api/version`      | `{"version": "..."}`                                  |
| GET    | `/api/tags`         | Aggregated models from all connected nodes            |
| POST   | `/api/show`         | Proxied to a node hosting the model                   |
| POST   | `/api/generate`     | Stream (NDJSON) or non-stream JSON                    |
| POST   | `/api/chat`         | Stream (NDJSON) or non-stream JSON                    |
| POST   | `/api/embeddings`   | Proxied to node (optional)                            |
| WS     | `/ws` (configurable)| AI-node connect endpoint, `Authorization: Bearer ...` |

## Config (`.env`)

See `.env.example`. Required: `PROXY_NODE_API_KEY` (used by AI nodes on the `/ws`
handshake). HTTP client endpoints are open by default — they mirror real Ollama, which
ships no auth. Put the proxy behind a reverse proxy / network ACL / VPN if you need to
restrict client access.

## Run

```bash
./scripts/check_deps.sh
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080
```
