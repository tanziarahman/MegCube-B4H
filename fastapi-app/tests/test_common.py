"""/api/image (image proxy) and /api/devices (camera list used by the Recognition page)"""
import httpx
import pytest

from conftest import DEVICE_CONFIG

JPEG = b"\xff\xd8\xff\xe0fake-jpeg\xff\xd9"
GET_IMAGE = "/device_storage/get_image"


# ---------- security: only box image files may be proxied ----------

@pytest.mark.parametrize("uri", [
    "../etc/passwd.jpg",
    "./record_1/../../etc/shadow.jpg",
    "/etc/passwd",
    "/etc/hosts.jpg",                    # image extension but not an allowed folder
    "http://evil.com/a.jpg",
    "./record_1/face.jpg.exe",
    "./record_1/face",                   # no extension
    "./record_1/face.txt",
    "",
    "config/box.jpg",
])
def test_rejects_non_image_paths(client, fake_box, uri):
    r = client.get("/api/image", params={"uri": uri})
    assert r.status_code == 400
    assert fake_box.image_calls == [], "nothing may be fetched from the box"


def test_missing_uri(client, fake_box):
    assert client.get("/api/image").status_code == 422


@pytest.mark.parametrize("uri", [
    "./record_1/a.jpg", "record_1/a.JPG", "./group/1/b.png", "group/b.jpeg",
    "/home/appdata/face/c.bmp", "./record_2/d.webp"])
def test_accepts_box_image_paths(client, fake_box, uri):
    fake_box.images[GET_IMAGE] = (JPEG, "image/jpeg")
    assert client.get("/api/image", params={"uri": uri}).status_code == 200


# ---------- fetching ----------

def test_returns_image_with_cache_header(client, fake_box):
    fake_box.images[GET_IMAGE] = (JPEG, "image/jpeg")
    r = client.get("/api/image", params={"uri": "./record_1/a.jpg"})
    assert r.status_code == 200 and r.content == JPEG
    assert r.headers["content-type"] == "image/jpeg"
    assert "max-age" in r.headers["cache-control"]
    assert fake_box.image_calls[0] == (GET_IMAGE, {"image_uri": "./record_1/a.jpg"})


@pytest.mark.parametrize("uri,expected", [("./record_1/a.png", "image/png"), ("./record_1/a.jpg", "image/jpeg"),
                                          ("./record_1/a.bmp", "image/bmp")])
def test_guesses_type_when_box_sends_octet_stream(client, fake_box, uri, expected):
    fake_box.images[GET_IMAGE] = (JPEG, "application/octet-stream")
    assert client.get("/api/image", params={"uri": uri}).headers["content-type"] == expected


def test_falls_back_to_web_path_when_get_image_returns_json_error(client, fake_box):
    fake_box.images[GET_IMAGE] = (b'{"code": 5, "message": "not found"}', "application/json")
    fake_box.images["/web/record_1/a.jpg"] = (JPEG, "image/jpeg")
    r = client.get("/api/image", params={"uri": "./record_1/a.jpg"})
    assert r.status_code == 200 and r.content == JPEG


def test_absolute_path_is_tried_directly(client, fake_box):
    fake_box.images["/home/appdata/f/c.jpg"] = (JPEG, "image/jpeg")
    r = client.get("/api/image", params={"uri": "/home/appdata/f/c.jpg"})
    assert r.status_code == 200
    assert [p for p, _ in fake_box.image_calls][:2] == [GET_IMAGE, "/home/appdata/f/c.jpg"]


@pytest.mark.parametrize("bad_content", [b"", b"<!DOCTYPE html><html>login</html>", b"<html>err</html>"])
def test_html_or_empty_replies_are_not_passed_on_as_images(client, fake_box, bad_content):
    fake_box.images[GET_IMAGE] = (bad_content, "text/html")
    fake_box.images["/web/record_1/a.jpg"] = (bad_content, "text/html")
    assert client.get("/api/image", params={"uri": "./record_1/a.jpg"}).status_code == 404


def test_session_expired_relogs_in_once_and_retries(client, fake_box):
    fake_box.images[GET_IMAGE] = [(b'{"code": 512}', "application/json"), (JPEG, "image/jpeg")]
    r = client.get("/api/image", params={"uri": "./record_1/a.jpg"})
    assert r.status_code == 200 and fake_box.logins == 1


def test_session_expired_twice_does_not_loop(client, fake_box):
    fake_box.images[GET_IMAGE] = [(b'{"code": 512}', "application/json"), (b'{"code": 512}', "application/json")]
    fake_box.images["/web/record_1/a.jpg"] = (b'{"code": 512}', "application/json")
    r = client.get("/api/image", params={"uri": "./record_1/a.jpg"})
    assert r.status_code == 404 and fake_box.logins == 1


def test_all_paths_404(client, fake_box):
    assert client.get("/api/image", params={"uri": "./record_1/gone.jpg"}).status_code == 404


def test_box_unreachable(client, fake_box):
    fake_box.images[GET_IMAGE] = httpx.ConnectError("refused")
    assert client.get("/api/image", params={"uri": "./record_1/a.jpg"}).status_code == 503


# ---------- /api/devices (used by the Recognition page to show camera names) ----------

def test_devices_list_exists(client, fake_box):
    """BUG CHECK: routers/common.py has only a placeholder comment where GET /api/devices used to be."""
    fake_box.replies[("POST", "/device_access/device_config")] = DEVICE_CONFIG
    fake_box.replies[("POST", "/device_access/device_state")] = []
    r = client.get("/api/devices")
    assert r.status_code == 200, f"GET /api/devices returned {r.status_code}"
    assert r.json() == [{"device_id": 1, "device_name": "Hikvision"}, {"device_id": 2, "device_name": "IPCAM-D3"},
                        {"device_id": 3, "device_name": "CAM3-D4"}]
    assert "s3cret" not in r.text and "rtsp" not in r.text, "camera addresses/passwords must not reach the browser"


def test_devices_list_empty(client, fake_box):
    fake_box.replies[("POST", "/device_access/device_config")] = None
    assert client.get("/api/devices").json() == []