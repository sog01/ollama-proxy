"""FastAPI entry point: mounts HTTP routes + WebSocket endpoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import settings
from .routes import router as http_router
from .ws_server import ws_endpoint

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

app = FastAPI(title="ollama-proxy", version=settings.proxy_version)
app.include_router(http_router)
app.add_api_websocket_route(settings.proxy_ws_path, ws_endpoint)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.proxy_host,
        port=settings.proxy_port,
        log_level=settings.log_level,
    )
