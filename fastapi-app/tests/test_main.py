"""App startup and error handling (main.py)"""
from fastapi.testclient import TestClient

from core import box
from main import app


def test_starts_even_when_box_is_offline(monkeypatch):
    async def box_down():
        raise OSError("box offline")

    async def nothing():
        pass
    monkeypatch.setattr(box, "login", box_down)
    monkeypatch.setattr(box, "close", nothing)
    with TestClient(app) as c:      # `with` runs startup + shutdown
        assert c.get("/").status_code == 200


def test_unknown_route(client):
    assert client.get("/api/does-not-exist").status_code == 404


def test_unexpected_error_returns_500(client, fake_box):
    fake_box.replies[("POST", "/device_alarm/alarm_history")] = OSError("unexpected")
    r = client.get("/api/recognition", params={"start": "2026-09-28 00:00:00", "end": "2026-09-28 23:59:59"})
    assert r.status_code == 500      # unexpected errors: 500, no crash of the server


def test_every_route_is_registered(client):
    # read from the OpenAPI schema (works with every FastAPI version)
    paths = {(m.upper(), path) for path, ops in app.openapi()["paths"].items() for m in ops}
    expected = {
        ("GET", "/api/recognition"), ("DELETE", "/api/recognition/{alarm_id}"), ("GET", "/api/people"),
        ("GET", "/api/capture"), ("GET", "/api/image"), ("GET", "/api/devices"),
        ("GET", "/api/devices/detail"), ("POST", "/api/devices"), ("DELETE", "/api/devices/{device_id}"),
        ("GET", "/api/preview/cameras"), ("GET", "/api/preview/{device_id}/stream"),
        ("GET", "/api/personnel/groups"), ("GET", "/api/personnel"), ("POST", "/api/personnel"),
        ("PUT", "/api/personnel/{person_id}"), ("DELETE", "/api/personnel/{person_id}"),
    }
    assert expected - paths == set(), f"missing routes: {expected - paths}"