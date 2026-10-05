import asyncio
from datetime import datetime, timezone

import pytest

import cache


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_round_trip_and_read_through(redis_cache):
    await cache.set_json("one", {"value": 1}, 10)
    assert await cache.get_json("one") == {"value": 1}

    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        return {"value": 2}

    assert await cache.get_or_load("two", 10, load) == ({"value": 2}, "miss")
    assert await cache.get_or_load("two", 10, load) == ({"value": 2}, "hit")
    assert calls == 1


@pytest.mark.anyio
async def test_expired_values_are_misses(redis_cache):
    await cache.set_json("expiring", {"value": 1}, 0.001)
    await asyncio.sleep(0.01)
    assert await cache.get_json("expiring") is None


@pytest.mark.anyio
async def test_fresh_bypasses_read_and_replaces_value(redis_cache):
    await cache.set_json("fresh", {"value": 1}, 10)

    async def load():
        return {"value": 2}

    assert await cache.get_or_load("fresh", 10, load, fresh=True) == ({"value": 2}, "bypass")
    assert await cache.get_json("fresh") == {"value": 2}


@pytest.mark.anyio
async def test_cache_off_loads_every_time():
    cache.configure(None)
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        return calls

    assert await cache.get_or_load("off", 10, load) == (1, "off")
    assert await cache.get_or_load("off", 10, load) == (2, "off")


@pytest.mark.anyio
async def test_redis_failures_are_fail_open(redis_cache):
    redis_cache.fail = True

    async def load():
        return {"value": 1}

    assert await cache.get_or_load("down", 10, load) == ({"value": 1}, "miss")
    calls = redis_cache.calls
    assert await cache.get_or_load("down", 10, load) == ({"value": 1}, "miss")
    assert redis_cache.calls == calls


@pytest.mark.anyio
async def test_single_flight_loads_once(redis_cache):
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return {"value": 1}

    results = await asyncio.gather(*(cache.get_or_load("flight", 10, load) for _ in range(5)))
    assert calls == 1
    assert [state for _, state in results] == ["miss", "hit", "hit", "hit", "hit"]


@pytest.mark.anyio
async def test_delete_prefix_only_removes_matching_keys(redis_cache):
    await cache.set_json("b4h:v1:dash:a", 1, 10)
    await cache.set_json("b4h:v1:dash:b", 2, 10)
    await cache.set_json("b4h:v1:other:c", 3, 10)
    await cache.delete_prefix("b4h:v1:dash:")
    assert await cache.get_json("b4h:v1:dash:a") is None
    assert await cache.get_json("b4h:v1:dash:b") is None
    assert await cache.get_json("b4h:v1:other:c") == 3


@pytest.mark.anyio
async def test_miss_and_hit_are_json_normalized(redis_cache):
    value = {"at": datetime(2026, 1, 1, tzinfo=timezone.utc)}

    async def load():
        return value

    miss, miss_state = await cache.get_or_load("datetime", 10, load)
    hit, hit_state = await cache.get_or_load("datetime", 10, load)
    assert miss_state == "miss" and hit_state == "hit"
    assert miss == hit == {"at": "2026-01-01 00:00:00+00:00"}
