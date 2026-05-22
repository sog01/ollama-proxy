"""Thin httpx wrapper around the local Ollama HTTP API."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from .config import settings

log = logging.getLogger("ai.ollama")

# Long timeout for generate/chat; Ollama can take a while on cold loads.
_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=60.0, pool=None)


async def list_models() -> list[str]:
    """Fetch local Ollama tags and return a list of model names."""
    url = f"{settings.ollama_base_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(url)
            r.raise_for_status()
            data = r.json()
        models = []
        for m in data.get("models", []) or []:
            name = m.get("name") or m.get("model")
            if name:
                models.append(name)
        return models
    except Exception as e:
        log.warning("ollama tags fetch failed: %s", e)
        return []


async def call_unary(path: str, method: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Non-streaming proxied call. Returns (status, json_body)."""
    url = f"{settings.ollama_base_url}{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
        if method.upper() == "GET":
            r = await cli.get(url)
        else:
            r = await cli.request(method.upper(), url, json=body)
        try:
            payload = r.json()
        except Exception:
            payload = {"raw": r.text}
        return r.status_code, payload


async def call_stream(path: str, method: str, body: dict[str, Any]) -> AsyncIterator[tuple[str, Any]]:
    """Streaming proxied call. Yields ('chunk', dict) per NDJSON line, then ('done', status)."""
    url = f"{settings.ollama_base_url}{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as cli:
        async with cli.stream(method.upper(), url, json=body) as r:
            status = r.status_code
            if status >= 400:
                # Read whole error body
                txt = await r.aread()
                try:
                    err = json.loads(txt.decode())
                except Exception:
                    err = {"error": txt.decode(errors="replace")}
                yield ("error", (status, err.get("error") or "ollama error"))
                return
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield ("chunk", obj)
            yield ("done", status)
