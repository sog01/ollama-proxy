"""Ollama-mimic HTTP routes. Forward over WS, relay back to client."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import settings
from .registry import PendingRequest, registry
from .ws_server import send_request

log = logging.getLogger("proxy.routes")

router = APIRouter()


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


async def _read_json(req: Request) -> dict[str, Any]:
    try:
        return await req.json()
    except Exception:
        return {}


async def _forward(path: str, method: str, body: dict[str, Any]) -> Any:
    """Forward a request to a node. Returns a StreamingResponse or JSONResponse."""
    model = body.get("model") if isinstance(body, dict) else None
    stream = bool(body.get("stream", path in ("/api/generate", "/api/chat", "/api/pull")))

    node = registry.pick_node(model)
    if node is None:
        return _err(503, "no inference nodes connected")

    pending = registry.new_request(stream=stream, node_id=node.node_id)
    payload = {
        "type": "request",
        "id": pending.id,
        "path": path,
        "method": method,
        "stream": stream,
        "body": body,
    }

    try:
        await send_request(node, payload)
    except Exception as e:
        registry.drop_request(pending.id)
        log.exception("forward send failed id=%s node=%s", pending.id, node.node_id)
        return _err(502, f"node send failed: {e}")

    if stream:
        return StreamingResponse(
            _stream_response(pending),
            media_type="application/x-ndjson",
        )
    return await _await_unary(pending)


async def _await_unary(pending: PendingRequest) -> JSONResponse:
    timeout = settings.proxy_request_timeout
    try:
        while True:
            msg = await asyncio.wait_for(pending.queue.get(), timeout=timeout)
            mtype = msg.get("type")
            if mtype == "response":
                registry.drop_request(pending.id)
                status = int(msg.get("status", 200))
                return JSONResponse(status_code=status, content=msg.get("body") or {})
            if mtype == "error":
                registry.drop_request(pending.id)
                return _err(int(msg.get("status", 500)), str(msg.get("message", "node error")))
            if mtype == "chunk":
                # Node ignored stream=false; accumulate then return when done
                pending.queue.put_nowait(msg)  # re-enqueue and fall through to streaming aggregate
                return await _aggregate_chunks(pending)
            # ignore unknown
    except asyncio.TimeoutError:
        registry.drop_request(pending.id)
        return _err(504, "upstream node timeout")


async def _aggregate_chunks(pending: PendingRequest) -> JSONResponse:
    timeout = settings.proxy_request_timeout
    parts: list[dict[str, Any]] = []
    status = 200
    try:
        while True:
            msg = await asyncio.wait_for(pending.queue.get(), timeout=timeout)
            mtype = msg.get("type")
            if mtype == "chunk":
                parts.append(msg.get("data") or {})
            elif mtype == "done":
                status = int(msg.get("status", 200))
                break
            elif mtype == "error":
                registry.drop_request(pending.id)
                return _err(int(msg.get("status", 500)), str(msg.get("message", "node error")))
    except asyncio.TimeoutError:
        registry.drop_request(pending.id)
        return _err(504, "upstream node timeout")
    registry.drop_request(pending.id)
    body = parts[-1] if parts else {}
    return JSONResponse(status_code=status, content=body)


async def _stream_response(pending: PendingRequest):
    """Yield NDJSON chunks from the pending queue until done/error."""
    timeout = settings.proxy_request_timeout
    try:
        while True:
            try:
                msg = await asyncio.wait_for(pending.queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                err = {"error": "upstream node timeout"}
                yield (json.dumps(err) + "\n").encode()
                return
            mtype = msg.get("type")
            if mtype == "chunk":
                data = msg.get("data") or {}
                yield (json.dumps(data) + "\n").encode()
            elif mtype == "done":
                return
            elif mtype == "error":
                err = {"error": str(msg.get("message", "node error"))}
                yield (json.dumps(err) + "\n").encode()
                return
            elif mtype == "response":
                # node decided to return unary even though we asked for stream;
                # emit body as a single chunk
                body = msg.get("body") or {}
                yield (json.dumps(body) + "\n").encode()
                return
    finally:
        registry.drop_request(pending.id)


# ---- Ollama-mimic surface ----

@router.get("/")
async def root() -> Any:
    return JSONResponse(content="Ollama is running")


@router.get("/api/version")
async def api_version() -> Any:
    return {"version": settings.proxy_version}


@router.get("/api/tags")
async def api_tags() -> Any:
    models = registry.aggregate_models()
    nodes = registry.get_nodes()
    if not nodes:
        # mimic Ollama empty shape
        return {"models": []}
    # If a node is available, ask it for richer metadata; otherwise synthesize minimal.
    node = nodes[0]
    pending = registry.new_request(stream=False, node_id=node.node_id)
    payload = {"type": "request", "id": pending.id, "path": "/api/tags", "method": "GET", "stream": False, "body": {}}
    try:
        await send_request(node, payload)
        result = await _await_unary(pending)
        # If node failed, fall back
        if isinstance(result, JSONResponse) and result.status_code < 400:
            return result
    except Exception:
        registry.drop_request(pending.id)
    return {"models": [{"name": m, "model": m} for m in models]}


@router.post("/api/show")
async def api_show(req: Request) -> Any:
    body = await _read_json(req)
    return await _forward("/api/show", "POST", body)


@router.post("/api/generate")
async def api_generate(req: Request) -> Any:
    body = await _read_json(req)
    return await _forward("/api/generate", "POST", body)


@router.post("/api/chat")
async def api_chat(req: Request) -> Any:
    body = await _read_json(req)
    return await _forward("/api/chat", "POST", body)


@router.post("/api/pull")
async def api_pull(req: Request) -> Any:
    body = await _read_json(req)
    return await _forward("/api/pull", "POST", body)


@router.post("/api/embeddings")
async def api_embeddings(req: Request) -> Any:
    body = await _read_json(req)
    return await _forward("/api/embeddings", "POST", body)


@router.post("/api/embed")
async def api_embed(req: Request) -> Any:
    body = await _read_json(req)
    return await _forward("/api/embed", "POST", body)
