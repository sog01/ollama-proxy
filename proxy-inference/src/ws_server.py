"""WebSocket endpoint: AI nodes dial in, authenticate, register, multiplex."""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .auth import verify_node_authorization
from .config import settings
from .registry import Node, registry

log = logging.getLogger("proxy.ws")

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_BAD_HANDSHAKE = 4400


async def _send_json(node: Node, payload: dict) -> None:
    async with node.send_lock:
        await node.ws.send_text(json.dumps(payload))


async def _heartbeat(node: Node) -> None:
    interval = settings.proxy_heartbeat_interval
    try:
        while True:
            await asyncio.sleep(interval)
            if node.ws.client_state != WebSocketState.CONNECTED:
                return
            try:
                await _send_json(node, {"type": "ping"})
            except Exception:
                return
    except asyncio.CancelledError:
        return


async def ws_endpoint(ws: WebSocket) -> None:
    # FastAPI parses the header for us
    authz = ws.headers.get("authorization") or ws.headers.get("Authorization")
    if not verify_node_authorization(authz):
        log.warning("ws auth failed remote=%s", ws.client)
        await ws.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    await ws.accept()

    # Await register frame
    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=10)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await ws.close(code=WS_CLOSE_BAD_HANDSHAKE)
        return

    try:
        reg = json.loads(first)
    except json.JSONDecodeError:
        await ws.close(code=WS_CLOSE_BAD_HANDSHAKE)
        return

    if reg.get("type") != "register" or not reg.get("node_id"):
        await ws.close(code=WS_CLOSE_BAD_HANDSHAKE)
        return

    node = Node(
        node_id=str(reg["node_id"]),
        ws=ws,
        models=list(reg.get("models") or []),
        capabilities=dict(reg.get("capabilities") or {}),
        last_pong=time.time(),
    )
    await registry.add_node(node)

    hb_task = asyncio.create_task(_heartbeat(node))

    try:
        while True:
            text = await ws.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                log.warning("non-json frame from node_id=%s", node.node_id)
                continue

            mtype = msg.get("type")
            if mtype == "pong":
                node.last_pong = time.time()
                continue
            if mtype == "ping":
                await _send_json(node, {"type": "pong"})
                continue

            rid = msg.get("id")
            if not rid:
                continue
            pending = registry.get_request(rid)
            if pending is None:
                # late frame after timeout; ignore
                continue
            await pending.queue.put(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws_server loop error node_id=%s", node.node_id)
    finally:
        hb_task.cancel()
        await registry.remove_node(node.node_id)
        if ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.close()
            except Exception:
                pass


async def send_request(node: Node, payload: dict) -> None:
    """Public helper used by routes.py to forward a client request to a node."""
    await _send_json(node, payload)
