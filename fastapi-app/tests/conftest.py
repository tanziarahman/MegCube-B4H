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

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from b4h import B4HError  # noqa: E402
import core  # noqa: E402
from core import box  # noqa: E402
from main import app  # noqa: E402


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