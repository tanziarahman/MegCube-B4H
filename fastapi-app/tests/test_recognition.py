import pytest
from fastapi.testclient import TestClient

from app.core import b4h as b4h_module
from app.main import app
from tests.fake_box import FakeBox


@pytest.fixture
def client(monkeypatch):
    fake = FakeBox()
    for name in ("login", "close", "call", "get_bytes"):
        monkeypatch.setattr(b4h_module.b4h, name, getattr(fake, name))
    with TestClient(app) as c:
        c.fake = fake
        yield c


def test_matched_page_maps_fields(client):
    d = client.get("/api/recognition/records", params={"result": "matched"}).json()
    assert d["total"] == 22 and len(d["items"]) == 10 and d["has_more"]
    r = d["items"][0]
    assert r["result"] == "matched" and r["person_name"] == "Tanzia" and r["camera_name"] == "Hikvision"
    assert r["similarity"] == 79.0 and r["group_names"] == ["Ticon", "Default Group"]
    assert r["face_image"].startswith("/api/recognition/image?uri=") and "bg_" in r["scene_image"]
    assert r["time"].endswith("+06:00")
    body = client.fake.calls[-1][2]
    assert body["size"] == 10 and body["query_condition"]["alarm_type"][0]["major_type"] == "face_basic_business"


def test_all_merges_both_types_newest_first(client):
    d = client.get("/api/recognition/records", params={"size": 30}).json()
    assert d["total"] == 27 and len(d["items"]) == 27
    times = [i["time_ms"] for i in d["items"]]
    assert times == sorted(times, reverse=True)
    assert {i["result"] for i in d["items"]} == {"matched", "stranger"}


def test_last_page(client):
    d = client.get("/api/recognition/records", params={"result": "matched", "page": 3}).json()
    assert len(d["items"]) == 2 and not d["has_more"]


def test_detail_and_filters(client):
    d = client.get("/api/recognition/records", params={"result": "matched", "name": "tanz"}).json()
    assert d["note"] and len(d["items"]) == 10
    assert client.get(f"/api/recognition/records/{d['items'][0]['id']}").status_code == 200
    assert client.get("/api/recognition/records/missing").status_code == 404


def test_image_cameras_groups(client):
    r = client.get("/api/recognition/image", params={"uri": "./snap/face_1.jpg"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get("/api/recognition/cameras").json() == [{"id": "1", "name": "Hikvision", "online": True}]
    assert client.get("/api/recognition/groups").json()[1] == {"id": "2", "name": "Ticon"}


def test_raw_only_when_asked(client):
    a = client.get("/api/recognition/records", params={"result": "stranger"}).json()["items"][0]
    b = client.get("/api/recognition/records", params={"result": "stranger", "include_raw": True}).json()["items"][0]
    assert "raw" not in a and "raw" in b and a["result"] == "stranger"


def test_existing_routes_still_registered(client):
    paths = set(app.openapi()["paths"])
    for p in ["/webhook/alarm", "/api/events", "/api/events/stream", "/api/device/status",
              "/api/b4h/video-cap", "/api/b4h/device-info", "/api/b4h/cameras", "/api/b4h/groups",
              "/api/b4h/persons", "/api/b4h/raw"]:
        assert p in paths
