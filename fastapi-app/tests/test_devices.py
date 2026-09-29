"""/api/devices/detail, POST /api/devices, DELETE /api/devices/{id}"""
import pytest

from conftest import DEVICE_CONFIG, DEVICE_STATE, box_error
from routers.devices import _mask_url, _rtsp_url

CONFIG = ("POST", "/device_access/device_config")
STATE = ("POST", "/device_access/device_state")
ADD = ("POST", "/device_access/device")
DELETE = ("DELETE", "/device_access/device")


# ---------- password masking ----------

@pytest.mark.parametrize("url,expected", [
    ("rtsp://u:pw@1.2.3.4:554/ch/201", "rtsp://u:****@1.2.3.4:554/ch/201"),
    ("rtsp://u:pw@cam.local/ch", "rtsp://u:****@cam.local/ch"),
    ("rtsp://1.2.3.4:554/ch", "rtsp://1.2.3.4:554/ch"),              # no credentials
    ("rtsp://u@1.2.3.4/ch", "rtsp://u@1.2.3.4/ch"),                  # user only
    ("rtsp://u:@1.2.3.4/ch", "rtsp://u:****@1.2.3.4/ch"),            # empty password
    ("", ""),
])
def test_mask_url(url, expected):
    assert _mask_url(url) == expected


@pytest.mark.parametrize("secret", ["p@ss", "a:b", "p%40ss", "ticon449"])
def test_mask_url_never_leaks_password(secret):
    from urllib.parse import quote
    url = f"rtsp://user:{quote(secret, safe='')}@1.2.3.4:554/ch"
    masked = _mask_url(url)
    assert secret not in masked and quote(secret, safe="") not in masked


# ---------- detail list ----------

def test_detail(client, fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    fake_box.replies[STATE] = DEVICE_STATE
    r = client.get("/api/devices/detail")
    assert r.status_code == 200
    d = {x["device_id"]: x for x in r.json()}
    assert d[1] == {"device_id": 1, "device_name": "Hikvision", "device_type": "Video", "protocol": "rtsp",
                    "manufacturer": "unknown", "address": "rtsp://testuser:****@192.168.90.24:554/ISAPI/Streaming/channels/201",
                    "online": True, "state_code": 0, "pulling_stream": True}
    assert d[2]["online"] is True and d[2]["pulling_stream"] is False
    assert d[3]["online"] is False and d[3]["state_code"] == 3        # unknown state -> offline, code kept
    assert "s3cret" not in r.text


def test_detail_device_missing_from_state(client, fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG[:1]
    fake_box.replies[STATE] = []
    row = client.get("/api/devices/detail").json()[0]
    assert row["online"] is False and row["state_code"] is None and row["pulling_stream"] is False


@pytest.mark.parametrize("channel_type,label", [(1, "Video"), (2, "Picture"), (9, "Type 9"), (None, "Type None")])
def test_detail_device_type(client, fake_box, channel_type, label):
    fake_box.replies[CONFIG] = [{**DEVICE_CONFIG[0], "channel_type": channel_type}]
    fake_box.replies[STATE] = []
    assert client.get("/api/devices/detail").json()[0]["device_type"] == label


def test_detail_no_rtsp_param(client, fake_box):
    fake_box.replies[CONFIG] = [{"device_id": 5, "device_name": "Pic", "channel_type": 2}]
    fake_box.replies[STATE] = None
    row = client.get("/api/devices/detail").json()[0]
    assert row["address"] == "" and row["online"] is False


def test_detail_no_devices(client, fake_box):
    fake_box.replies[CONFIG] = None
    fake_box.replies[STATE] = None
    assert client.get("/api/devices/detail").json() == []


# ---------- building the RTSP url ----------

@pytest.mark.parametrize("url,user,pw,expected", [
    ("rtsp://1.2.3.4:554/ch/201", "admin", "pw", "rtsp://admin:pw@1.2.3.4:554/ch/201"),
    ("rtsp://u:p@1.2.3.4/ch", "", "", "rtsp://u:p@1.2.3.4/ch"),                        # credentials from URL
    ("rtsp://u:p@1.2.3.4/ch", "admin", "new", "rtsp://admin:new@1.2.3.4/ch"),          # fields win
    ("rtsp://1.2.3.4/ch", "", "", "rtsp://1.2.3.4/ch"),                                # no credentials at all
    ("rtsp://1.2.3.4/ch", "admin", "p@ss:w/rd", "rtsp://admin:p%40ss%3Aw%2Frd@1.2.3.4/ch"),  # special chars encoded
    ("RTSP://1.2.3.4/ch", "a", "b", "rtsp://a:b@1.2.3.4/ch"),                          # upper-case scheme
    ("  rtsp://1.2.3.4/ch  ", "a", "b", "rtsp://a:b@1.2.3.4/ch"),                      # pasted with spaces
])
def test_rtsp_url(url, user, pw, expected):
    assert _rtsp_url(url, user, pw)[0] == expected


# ---------- add ----------

NEW = {"name": "Gate cam", "url": "rtsp://192.168.90.24:554/ISAPI/Streaming/channels/501",
       "user": "testuser", "password": "s3cret!"}


@pytest.mark.parametrize("existing_ids,new_id", [([], 1), ([1, 2, 3], 4), ([1, 3], 2), ([2, 3], 1), ([1, 2, 5], 3)])
def test_add_uses_lowest_free_id(client, fake_box, existing_ids, new_id):
    fake_box.replies[CONFIG] = [{"device_id": i, "device_name": f"cam{i}"} for i in existing_ids]
    fake_box.replies[ADD] = None
    r = client.post("/api/devices", json=NEW)
    assert r.status_code == 201 and r.json() == {"device_id": new_id}
    sent = fake_box.sent(*ADD)[0]
    assert sent["device_id"] == new_id and sent["device_name"] == "Gate cam" and sent["proto"] == "rtsp"
    assert sent["rtsp_param"] == {"user": "testuser", "password": "s3cret!",
                                  "url": "rtsp://testuser:s3cret%21@192.168.90.24:554/ISAPI/Streaming/channels/501"}


@pytest.mark.parametrize("name", ["Hikvision", "hikvision", "  HIKVISION  "])
def test_add_duplicate_name(client, fake_box, name):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    r = client.post("/api/devices", json={**NEW, "name": name})
    assert r.status_code == 409
    assert fake_box.sent(*ADD) == []


def test_add_trims_name(client, fake_box):
    fake_box.replies[CONFIG] = []
    fake_box.replies[ADD] = None
    client.post("/api/devices", json={**NEW, "name": "  Gate cam  "})
    assert fake_box.sent(*ADD)[0]["device_name"] == "Gate cam"


@pytest.mark.parametrize("change,status", [
    ({"name": ""}, 422),
    ({"name": "x" * 65}, 422),
    ({"url": "http://1.2.3.4/stream"}, 422),
    ({"url": "rtsp:///nohost"}, 422),
    ({"url": "not a url at all"}, 422),
    ({"url": "rtsp://"}, 422),
    ({"url": "rtsp://1.2.3.4/" + "a" * 600}, 422),
    ({"protocol": "onvif"}, 422),
    ({"type": "picture"}, 501),
    ({"type": "thermal"}, 422),
    ({"password": "p" * 129}, 422),
])
def test_add_bad_input(client, fake_box, change, status):
    fake_box.replies[CONFIG] = []
    r = client.post("/api/devices", json={**NEW, **change})
    assert r.status_code == status
    assert fake_box.sent(*ADD) == []


def test_add_missing_body(client, fake_box):
    assert client.post("/api/devices").status_code == 422


def test_add_box_refuses(client, fake_box):
    fake_box.replies[CONFIG] = []
    fake_box.replies[ADD] = box_error(9, "device limit reached", "/device_access/device")
    r = client.post("/api/devices", json=NEW)
    assert r.status_code == 502 and "device limit reached" in r.json()["detail"]


def test_add_response_does_not_echo_password(client, fake_box):
    fake_box.replies[CONFIG] = []
    fake_box.replies[ADD] = None
    assert "s3cret" not in client.post("/api/devices", json=NEW).text


# ---------- delete ----------

def test_delete(client, fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    fake_box.replies[DELETE] = None
    r = client.delete("/api/devices/2")
    assert r.status_code == 200 and r.json() == {"deleted": 2}
    assert fake_box.sent(*DELETE) == [{"device_id": 2}]


def test_delete_unknown_device(client, fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    assert client.delete("/api/devices/42").status_code == 404
    assert fake_box.sent(*DELETE) == []


@pytest.mark.parametrize("bad", ["0", "-1", "abc"])
def test_delete_bad_id(client, fake_box, bad):
    assert client.delete(f"/api/devices/{bad}").status_code == 422
    assert fake_box.calls == []


def test_delete_box_refuses(client, fake_box):
    """e.g. the camera is still used by a task."""
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    fake_box.replies[DELETE] = box_error(1073741830, "device in use")
    assert client.delete("/api/devices/1").status_code == 502
