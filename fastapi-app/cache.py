"""Redis cache (optional: REDIS_URL). Fail-open: any Redis problem counts as a miss, so the portal
works the same without caching, only slower. After an error Redis is skipped for 30 s, so an outage
costs one short timeout, not one per request. Loaders are single-flighted in this process because the
portal and its workers run in one backend process."""
import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from dotenv import load_dotenv
from redis.asyncio import Redis

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "")
PREFIX = os.getenv("REDIS_PREFIX", "b4h")
VERSION = "v1"

log = logging.getLogger("b4h.cache")
_client: Any | None = None
_skip_until = 0.0
_locks: dict[str, asyncio.Lock] = {}


def key(*parts: str) -> str:
    return f"{PREFIX}:{VERSION}:" + ":".join(parts)


def enabled() -> bool:
    return _client is not None or bool(REDIS_URL)


def configure(client) -> None:
    global _client, _skip_until
    _client = client
    _skip_until = 0.0


def _client_for_use():
    global _client
    if _client is None and REDIS_URL:
        _client = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
            health_check_interval=30,
        )
    return _client


def _paused() -> bool:
    return time.monotonic() < _skip_until


def _pause(exc: Exception) -> None:
    global _skip_until
    now = time.monotonic()
    if now >= _skip_until:
        _skip_until = now + 30
        log.warning("Redis unavailable (%r); caching paused for 30 s", exc)


def _normalize(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


async def connect() -> None:
    if not REDIS_URL:
        log.info("Redis cache disabled")
        return
    client = _client_for_use()
    if client is None:
        return
    try:
        await client.ping()
        log.info("Redis cache OK")
    except Exception as exc:
        _pause(exc)


async def close() -> None:
    global _client
    client = _client
    _client = None
    if client is not None:
        try:
            await client.aclose()
        except Exception as exc:
            _pause(exc)


async def get_json(k: str) -> Any | None:
    client = _client_for_use()
    if client is None or _paused():
        return None
    try:
        value = await client.get(k)
        return None if value is None else json.loads(value)
    except Exception as exc:
        _pause(exc)
        return None


async def set_json(k: str, value: Any, ttl: float) -> None:
    client = _client_for_use()
    if client is None or _paused():
        return
    try:
        await client.set(k, json.dumps(value, separators=(",", ":"), default=str), px=int(ttl * 1000))
    except Exception as exc:
        _pause(exc)


async def delete(*keys: str) -> None:
    client = _client_for_use()
    if client is None or _paused() or not keys:
        return
    try:
        await client.delete(*keys)
    except Exception as exc:
        _pause(exc)


async def delete_prefix(prefix: str) -> None:
    client = _client_for_use()
    if client is None or _paused():
        return
    try:
        batch = []
        async for k in client.scan_iter(match=f"{prefix}*", count=500):
            batch.append(k)
            if len(batch) == 500:
                await client.delete(*batch)
                batch.clear()
        if batch:
            await client.delete(*batch)
    except Exception as exc:
        _pause(exc)


async def get_or_load(
    k: str,
    ttl: float,
    loader: Callable[[], Awaitable[Any]],
    *,
    fresh: bool = False,
) -> tuple[Any, str]:
    if not enabled():
        return _normalize(await loader()), "off"
    if not fresh:
        cached = await get_json(k)
        if cached is not None:
            return cached, "hit"

    lock = _locks.setdefault(k, asyncio.Lock())
    async with lock:
        if not fresh:
            cached = await get_json(k)
            if cached is not None:
                return cached, "hit"
        value = _normalize(await loader())
        await set_json(k, value, ttl)
        return value, "bypass" if fresh else "miss"
