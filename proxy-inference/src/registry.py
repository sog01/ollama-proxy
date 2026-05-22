"""Registry of connected AI nodes and per-request correlation queues."""
from __future__ import annotations

import asyncio
import itertools
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("proxy.registry")


@dataclass
class PendingRequest:
    id: str
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    stream: bool = False
    node_id: str | None = None


@dataclass
class Node:
    node_id: str
    ws: WebSocket
    models: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_pong: float = 0.0


class Registry:
    """Tracks connected nodes and pending request correlations."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._pending: dict[str, PendingRequest] = {}
        self._rr = itertools.count()
        self._lock = asyncio.Lock()

    # ---- node lifecycle ----
    async def add_node(self, node: Node) -> None:
        async with self._lock:
            self._nodes[node.node_id] = node
        log.info("node connected node_id=%s models=%s", node.node_id, node.models)

    async def remove_node(self, node_id: str) -> None:
        async with self._lock:
            self._nodes.pop(node_id, None)
            # fail any in-flight requests bound to this node
            dead = [p for p in self._pending.values() if p.node_id == node_id]
        for p in dead:
            await p.queue.put({"type": "error", "id": p.id, "status": 502, "message": "node disconnected"})
        log.info("node disconnected node_id=%s", node_id)

    def get_nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def aggregate_models(self) -> list[str]:
        seen: dict[str, None] = {}
        for n in self._nodes.values():
            for m in n.models:
                seen.setdefault(m, None)
        return list(seen.keys())

    def pick_node(self, model: str | None) -> Node | None:
        """Pick a node that advertises the model; else round-robin among any node."""
        nodes = list(self._nodes.values())
        if not nodes:
            return None
        if model:
            candidates = [n for n in nodes if model in n.models]
            if candidates:
                idx = next(self._rr) % len(candidates)
                return candidates[idx]
        idx = next(self._rr) % len(nodes)
        return nodes[idx]

    # ---- request correlation ----
    def new_request(self, stream: bool, node_id: str) -> PendingRequest:
        rid = f"req-{uuid.uuid4().hex[:12]}"
        pr = PendingRequest(id=rid, stream=stream, node_id=node_id)
        self._pending[rid] = pr
        return pr

    def get_request(self, rid: str) -> PendingRequest | None:
        return self._pending.get(rid)

    def drop_request(self, rid: str) -> None:
        self._pending.pop(rid, None)


registry = Registry()
