"""Reconnecting WebSocket client. Dials proxy, registers, multiplexes requests."""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

from websockets.exceptions import ConnectionClosed

try:
    # websockets >= 13: new asyncio API uses `additional_headers`
    from websockets.asyncio.client import connect as _ws_connect
    _HEADERS_KW = "additional_headers"
    _NEW_API = True
except ImportError:
    # websockets 12.x legacy API uses `extra_headers`
    from websockets import connect as _ws_connect  # type: ignore
    _HEADERS_KW = "extra_headers"
    _NEW_API = False

try:
    # only present on legacy stack
    from websockets.exceptions import InvalidStatusCode  # type: ignore
except ImportError:
    InvalidStatusCode = ()  # type: ignore

try:
    # only present on new stack
    from websockets.exceptions import InvalidStatus  # type: ignore
except ImportError:
    InvalidStatus = ()  # type: ignore

from . import handlers, ollama_client
from .config import settings

log = logging.getLogger("ai.ws")


class WSClient:
    def __init__(self) -> None:
        self.node_id = settings.resolved_node_id()
        self._send_lock = asyncio.Lock()
        self._ws = None  # type: ignore[assignment]
        self._tasks: set[asyncio.Task] = set()

    async def _send(self, payload: dict[str, Any]) -> None:
        ws = self._ws
        if ws is None:
            return
        async with self._send_lock:
            await ws.send(json.dumps(payload))

    async def _heartbeat(self) -> None:
        interval = settings.heartbeat_interval
        try:
            while True:
                await asyncio.sleep(interval)
                try:
                    await self._send({"type": "ping"})
                except Exception:
                    return
        except asyncio.CancelledError:
            return

    async def _register(self) -> None:
        models = await ollama_client.list_models()
        await self._send({
            "type": "register",
            "node_id": self.node_id,
            "models": models,
            "capabilities": {"stream": True},
        })
        log.info("registered node_id=%s models=%s", self.node_id, models)

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == "ping":
            await self._send({"type": "pong"})
            return
        if mtype == "pong":
            return
        if mtype == "request":
            t = asyncio.create_task(handlers.handle_request(self._send, msg))
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)
            return
        log.warning("unknown frame from proxy: %s", mtype)

    async def _run_once(self) -> None:
        url = settings.proxy_ws_url
        headers = {"Authorization": f"Bearer {settings.node_api_key}"}
        log.info("connecting %s (api=%s)", url, "new" if _NEW_API else "legacy")
        kwargs = {_HEADERS_KW: headers, "max_size": None, "ping_interval": None}
        async with _ws_connect(url, **kwargs) as ws:
            self._ws = ws
            try:
                await self._register()
                hb = asyncio.create_task(self._heartbeat())
                try:
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            log.warning("non-json frame from proxy")
                            continue
                        await self._dispatch(msg)
                finally:
                    hb.cancel()
                    # cancel in-flight handlers on disconnect
                    for t in list(self._tasks):
                        t.cancel()
                    self._tasks.clear()
            finally:
                self._ws = None

    async def run_forever(self) -> None:
        backoff = 1.0
        cap = settings.reconnect_max_backoff
        while True:
            try:
                await self._run_once()
                # clean close: try immediate reconnect with small jitter
                backoff = 1.0
            except InvalidStatus as e:  # new API: HTTP-level reject during handshake
                resp = getattr(e, "response", None)
                code = getattr(resp, "status_code", None)
                if code in (401, 403):
                    log.error("auth rejected by proxy (HTTP %s). Fix NODE_API_KEY.", code)
                else:
                    log.warning("ws handshake failed: %s", e)
            except InvalidStatusCode as e:  # legacy API equivalent
                code = getattr(e, "status_code", None)
                if code in (401, 403):
                    log.error("auth rejected by proxy (HTTP %s). Fix NODE_API_KEY.", code)
                else:
                    log.warning("ws handshake failed: %s", e)
            except ConnectionClosed as e:
                if getattr(e, "code", None) == 4401:
                    log.error("auth rejected by proxy (WS 4401). Fix NODE_API_KEY.")
                else:
                    log.info("ws closed: %s", e)
            except OSError as e:
                log.info("connect failed: %s", e)
            except Exception:
                log.exception("ws loop error")

            sleep = min(cap, backoff) * (0.7 + random.random() * 0.6)
            log.info("reconnecting in %.1fs", sleep)
            await asyncio.sleep(sleep)
            backoff = min(cap, backoff * 2.0)
