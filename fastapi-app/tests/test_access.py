"""API key check (API_KEY in .env) and signed live-video links."""
import time

import pytest

import core
from conftest import DEVICE_CONFIG

KEY = "test-key-123"
HISTORY = ("POST", "/device_alarm/alarm_history")
OK = {"start": "2026-09-28 00:00:00", "end": "2026-09-28 23:59:59"}


@pytest.fixture
def with_key(fake_box, monkeypatch):
    monkeypatch.setattr(core, "API_KEY", KEY)
    fake_box.replies[HISTORY] = {}
    fake_box.replies[("POST", "/device_access/device_config")] = DEVICE_CONFIG
    return fake_box


# every route the frontend uses, with a harmless request
ROUTES = [
    ("GET", "/api/recognition", OK), ("DELETE", "/api/recognition/1", None), ("GET", "/api/people", None),
    ("GET", "/api/capture", OK), ("GET", "/api/image", {"uri": "./record_1/a.jpg"}), ("GET", "/api/devices", None),
    ("GET", "/api/devices/detail", None), ("POST", "/api/devices", None), ("DELETE", "/api/devices/1", None),
    ("GET", "/api/preview/cameras", None), ("GET", "/api/preview/1/stream", None),
    ("GET", "/api/personnel/groups", None), ("GET", "/api/personnel", None), ("POST", "/api/personnel", None),
    ("PUT", "/api/personnel/p1", None), ("DELETE", "/api/personnel/p1", None),
]


@pytest.mark.parametrize("method,path,params", ROUTES)
def test_every_route_needs_the_key(client, with_key, method, path, params):
    r = client.request(method, path, params=params)
    assert r.status_code == 401, f"{method} {path} is open without a key"
    assert with_key.calls == [] and with_key.uploads == [], "nothing may reach the box without the key"


@pytest.mark.parametrize("header", [{"X-API-Key": "wrong"}, {"X-API-Key": ""}, {"X-API-Key": KEY + "x"},
                                    {"Authorization": KEY}])
def test_wrong_key(client, with_key, header):
    assert client.get("/api/recognition", params=OK, headers=header).status_code == 401


def test_right_key(client, with_key):
    assert client.get("/api/recognition", params=OK, headers={"X-API-Key": KEY}).status_code == 200


def test_key_in_url_is_not_accepted(client, with_key):
    assert client.get("/api/recognition", params={**OK, "api_key": KEY}).status_code == 401


def test_no_key_configured_means_open(client, fake_box):
    fake_box.replies[HISTORY] = {}
    assert client.get("/api/recognition", params=OK).status_code == 200


def test_root_is_open(client, with_key):
    assert client.get("/").status_code == 200


# ---------- signed live-video links ----------

def stream_status(client, path):
    """Status of a stream request, without waiting for video (camera lookup fails -> 404 means access passed)."""
    return client.get(path).status_code


def test_signed_stream_link_is_accepted(client, with_key):
    token = core.sign_stream(1)
    # 404/500/502 = passed the access check (no ffmpeg in tests); 401 = refused
    assert stream_status(client, f"/api/preview/1/stream?{token}") != 401


def test_camera_list_gives_working_links(client, with_key):
    with_key.replies[("POST", "/device_access/device_state")] = []
    with_key.replies[("POST", "/intelli_manager/task_list")] = {}
    cams = client.get("/api/preview/cameras", headers={"X-API-Key": KEY}).json()
    assert stream_status(client, f"/api/preview/{cams[0]['id']}/stream?{cams[0]['stream_token']}") != 401


def test_link_for_another_camera_is_refused(client, with_key):
    token = core.sign_stream(1)
    assert stream_status(client, f"/api/preview/2/stream?{token}") == 401


def test_expired_link_is_refused(client, with_key):
    token = core.sign_stream(1, exp=int(time.time()) - 5)
    assert stream_status(client, f"/api/preview/1/stream?{token}") == 401


def test_tampered_expiry_is_refused(client, with_key):
    token = core.sign_stream(1, exp=int(time.time()) + 60)
    exp, sig = token.split("&")
    later = f"exp={int(time.time()) + 999999}&{sig}"
    assert stream_status(client, f"/api/preview/1/stream?{later}") == 401


@pytest.mark.parametrize("query", ["", "exp=abc&sig=x", "sig=00", "exp=99999999999"])
def test_bad_links_are_refused(client, with_key, query):
    assert stream_status(client, f"/api/preview/1/stream?{query}") == 401


def test_signature_does_not_open_other_routes(client, with_key):
    token = core.sign_stream(1)
    assert client.get(f"/api/preview/cameras?{token}").status_code == 401
    assert client.get(f"/api/recognition?{token}", params=OK).status_code == 401


def test_link_signed_with_old_key_stops_working(client, with_key, monkeypatch):
    token = core.sign_stream(1)
    monkeypatch.setattr(core, "API_KEY", "a-new-key")
    assert stream_status(client, f"/api/preview/1/stream?{token}") == 401
