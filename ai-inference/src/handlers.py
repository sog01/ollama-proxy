"""Map proxy-forwarded requests to local Ollama calls and send responses back over WS."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from . import ollama_client

log = logging.getLogger("ai.handlers")

# A "send" function injected by ws_client. Sends a single JSON frame.
SendFn = Callable[[dict[str, Any]], Awaitable[None]]


async def handle_request(send: SendFn, msg: dict[str, Any]) -> None:
    rid = msg.get("id")
    path = msg.get("path") or ""
    method = (msg.get("method") or "POST").upper()
    stream = bool(msg.get("stream", False))
    body = msg.get("body") or {}

    if not rid or not path:
        log.warning("malformed request frame: %s", msg)
        return

    try:
        if stream:
            await _handle_stream(send, rid, path, method, body)
        else:
            await _handle_unary(send, rid, path, method, body)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.exception("handler error id=%s path=%s", rid, path)
        await send({"type": "error", "id": rid, "status": 500, "message": f"node exception: {e}"})


async def _handle_unary(send: SendFn, rid: str, path: str, method: str, body: dict[str, Any]) -> None:
    status, payload = await ollama_client.call_unary(path, method, body)
    await send({"type": "response", "id": rid, "status": status, "body": payload})


async def _handle_stream(send: SendFn, rid: str, path: str, method: str, body: dict[str, Any]) -> None:
    status = 200
    async for kind, val in ollama_client.call_stream(path, method, body):
        if kind == "chunk":
            await send({"type": "chunk", "id": rid, "data": val})
        elif kind == "error":
            status, msg = val
            await send({"type": "error", "id": rid, "status": status, "message": str(msg)})
            return
        elif kind == "done":
            status = int(val)
            break
    await send({"type": "done", "id": rid, "status": status})


__all__ = ["handle_request"]
