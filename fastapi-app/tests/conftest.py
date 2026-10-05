"""Shared test setup.

These tests never talk to the real box. `fake_box` replaces the box connection with a fake that
answers from a table you fill in per test, and records every request the backend sent, so a test
can check both the API response AND exactly what would have been sent to the box.

Run from the fastapi-app folder:
    uv add --dev pytest
    uv run pytest -v
"""
import os
import sys
import time

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from b4h import B4HError  # noqa: E402
import core  # noqa: E402
from core import box  # noqa: E402
from main import app  # noqa: E402
import db  # noqa: E402
import cache  # noqa: E402

# Tests never use the DATABASE_URL from .env (your real database): only TEST_DATABASE_URL, via the
# `database` fixture below. Without it, the app behaves as if no database is configured.
db.DATABASE_URL = ""
cache.REDIS_URL = ""
cache.configure(None)


class FakeRedis:
    def __init__(self):
        self.data: dict[str, tuple[str, float | None]] = {}
        self.calls = 0
        self.fail = False

    def _call(self):
        self.calls += 1
        if self.fail:
            raise ConnectionError("down")

    async def get(self, name):
        self._call()
        entry = self.data.get(name)
        if entry is None:
            return None
        value, expires = entry
        if expires is not None and time.monotonic() >= expires:
            self.data.pop(name, None)
            return None
        return value

    async def set(self, name, value, px=None):
        self._call()
        expires = time.monotonic() + px / 1000 if px is not None else None
        self.data[name] = (value, expires)
        return True

    async def delete(self, *names):
        self._call()
        for name in names:
            self.data.pop(name, None)

    async def scan_iter(self, match=None, count=None):
        self._call()
        prefix = match[:-1] if match and match.endswith("*") else match
        for name in list(self.data):
            if prefix is None or name.startswith(prefix):
                yield name

    async def ping(self):
        self._call()
        return True

    async def aclose(self):
        self._call()


@pytest.fixture
def redis_cache(monkeypatch):
    fake = FakeRedis()
    cache.configure(fake)
    monkeypatch.setattr(cache, "_skip_until", 0.0)
    yield fake
    cache.configure(None)


class FakeBox:
    """Stands in for the box. Fill `replies` with {(METHOD, path): reply}.

    A reply can be: plain data (returned as the box's `data`), an Exception instance (raised),
    or a function(body) -> data. Unlisted endpoints raise an error so a test can't silently hit
    something it didn't expect.
    """

    def __init__(self):
        self.replies: dict[tuple[str, str], object] = {}
        self.calls: list[tuple[str, str, object]] = []    # (method, path, json body)
        self.uploads: list[tuple[str, str, dict]] = []    # (method, path, files)
        self.images: dict[str, object] = {}                # get_bytes: path -> (bytes, type) | Exception
        self.image_calls: list[tuple[str, dict | None]] = []
        self.logins = 0
        self.session_id = "S1"

    def _answer(self, method, path, body):
        key = (method, path)
        if key not in self.replies:
            raise AssertionError(f"Test didn't expect the backend to call the box: {method} {path}")
        reply = self.replies[key]
        if isinstance(reply, Exception):
            raise reply
        return reply(body) if callable(reply) else reply

    async def call(self, method, path, body=None, _retry=True):
        self.calls.append((method, path, body))
        return self._answer(method, path, body)

    async def upload(self, path, files, data=None, method="POST", _retry=True):
        self.uploads.append((method, path, files))
        return self._answer(method, path, files)

    async def get_bytes(self, path, params=None):
        self.image_calls.append((path, params))
        reply = self.images.get(path, httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", "http://box" + path), response=httpx.Response(404)))
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, list):          # a list = different answers on each call
            reply = reply.pop(0)
        return reply

    async def login(self):
        self.logins += 1

    async def relogin(self, stale_session):
        self.logins += 1

    async def close(self):
        pass

    def sent(self, method, path):
        """Bodies of all box calls made to this endpoint."""
        return [b for m, p, b in self.calls if m == method and p == path]


@pytest.fixture
def fake_box(monkeypatch):
    fake = FakeBox()
    for name in ("call", "upload", "get_bytes", "login", "relogin", "close"):
        monkeypatch.setattr(box, name, getattr(fake, name))
    monkeypatch.setattr(box, "session_id", "S1")
    core.invalidate_people_cache()          # every test starts with an empty /api/people cache
    monkeypatch.setattr(core, "API_KEY", "")  # access check off, except in the tests about it
    return fake


@pytest.fixture
def client(fake_box):
    # No `with`: the startup login to the real box is skipped.
    return TestClient(app, raise_server_exceptions=False)


def box_error(code=1073741825, message="general", path="/x"):
    return B4HError(code, message, path)


# ---- database (alarm tests) ----
# Alarm tests need a real PostgreSQL: set TEST_DATABASE_URL to an EMPTY database you don't mind
# losing (its tables are dropped and recreated), e.g. postgresql://postgres@localhost:5432/b4h_test
# or a throwaway Neon branch. Without it those tests are skipped.

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
_schema_ready = False


async def _reset_schema(engine) -> None:
    from sqlmodel import SQLModel
    import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


async def _truncate(engine) -> None:
    from sqlalchemy import text
    from sqlmodel import SQLModel
    tables = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def database(monkeypatch):
    """Empty tables, wired into db.sessions(). Yields the session factory."""
    if not TEST_DATABASE_URL:
        pytest.skip("Set TEST_DATABASE_URL to run database tests")
    import asyncio

    import db
    from routers import alarms as alarms_router

    global _schema_ready
    engine = db.make_engine(TEST_DATABASE_URL, null_pool=True)   # NullPool: safe across event loops
    if not _schema_ready:
        asyncio.run(_reset_schema(engine))
        _schema_ready = True
    asyncio.run(_truncate(engine))
    monkeypatch.setattr(alarms_router, "_box_id", None)      # box ids restart at 1 after the truncate
    db.configure(engine)
    yield db.sessions()
    db._sessions = db._engine = None       # other tests see "no database" again
    asyncio.run(engine.dispose())


# ---- sample box data, copied from real responses ----

DEVICE_CONFIG = [
    {"channel_type": 1, "device_id": 1, "device_name": "Hikvision", "manufacturer": "unknown", "proto": "rtsp",
     "rtsp_param": {"user": "testuser", "password": "s3cret!",
                    "url": "rtsp://testuser:s3cret!@192.168.90.24:554/ISAPI/Streaming/channels/201"}},
    {"channel_type": 1, "device_id": 2, "device_name": "IPCAM-D3", "manufacturer": "unknown", "proto": "rtsp",
     "rtsp_param": {"user": "testuser", "password": "s3cret!",
                    "url": "rtsp://testuser:s3cret!@192.168.90.24:554/ISAPI/Streaming/channels/301"}},
    {"channel_type": 1, "device_id": 3, "device_name": "CAM3-D4", "manufacturer": "unknown", "proto": "rtsp",
     "rtsp_param": {"user": "testuser", "password": "s3cret!",
                    "url": "rtsp://testuser:s3cret!@192.168.90.24:554/ISAPI/Streaming/channels/401"}},
]
DEVICE_STATE = [
    {"device_id": 1, "state": 0, "channels": [{"pull_stream": True}]},
    {"device_id": 2, "state": 0, "channels": [{"pull_stream": False}]},
    {"device_id": 3, "state": 3, "channels": []},
]
TASK_LIST = {"list": [{"task_name": "FR", "device_list": [{"device_id": 1}]}]}