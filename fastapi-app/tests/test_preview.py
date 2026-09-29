"""/api/preview/cameras and /api/preview/{id}/stream (ffmpeg is replaced by a fake process)"""
import pytest

from conftest import DEVICE_CONFIG, DEVICE_STATE, TASK_LIST
from routers import preview

CONFIG = ("POST", "/device_access/device_config")
STATE = ("POST", "/device_access/device_state")
TASKS = ("POST", "/intelli_manager/task_list")

JPG1 = b"\xff\xd8frame-one\xff\xd9"
JPG2 = b"\xff\xd8frame-two\xff\xd9"


class FakeStream:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def read1(self, n):
        return self.chunks.pop(0) if self.chunks else b""

    def readline(self):
        return self.chunks.pop(0) if self.chunks else b""


class FakeProc:
    """Pretends to be ffmpeg: stdout gives the chunks, then ends; stderr gives the error lines."""
    started: list["FakeProc"] = []

    def __init__(self, args, out=(), err=()):
        self.args, self.killed = args, False
        self.stdout, self.stderr = FakeStream(out), FakeStream(err)
        FakeProc.started.append(self)

    def kill(self):
        self.killed = True


@pytest.fixture
def ffmpeg(monkeypatch):
    """Call ffmpeg(out=[...chunks], err=[...lines]) to decide what the fake ffmpeg produces."""
    FakeProc.started = []
    monkeypatch.setattr(preview.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setitem(preview._active, "count", 0)

    def setup(out=(), err=()):
        monkeypatch.setattr(preview.subprocess, "Popen", lambda args, **kw: FakeProc(args, out=out, err=err))
    return setup


# ---------- camera list ----------

def test_cameras(client, fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    fake_box.replies[STATE] = DEVICE_STATE
    fake_box.replies[TASKS] = TASK_LIST
    r = client.get("/api/preview/cameras")
    rows = [{k: v for k, v in c.items() if k != "stream_token"} for c in r.json()]
    assert rows == [
        {"id": 1, "name": "Hikvision", "online": True, "task": "FR"},
        {"id": 2, "name": "IPCAM-D3", "online": True, "task": None},
        {"id": 3, "name": "CAM3-D4", "online": False, "task": None},
    ]
    assert all(c["stream_token"].startswith("exp=") for c in r.json())
    assert "s3cret" not in r.text and "rtsp" not in r.text


@pytest.mark.parametrize("states,tasks", [(None, None), ([], {}), ([], {"list": []}), ([], {"list": [{"task_name": "X"}]})])
def test_cameras_missing_state_and_tasks(client, fake_box, states, tasks):
    fake_box.replies[CONFIG] = DEVICE_CONFIG[:1]
    fake_box.replies[STATE] = states
    fake_box.replies[TASKS] = tasks
    row = client.get("/api/preview/cameras").json()[0]
    assert (row["online"], row["task"]) == (False, None)


def test_cameras_none_configured(client, fake_box):
    fake_box.replies[CONFIG] = None
    fake_box.replies[STATE] = None
    fake_box.replies[TASKS] = None
    assert client.get("/api/preview/cameras").json() == []


# ---------- stream ----------

def test_stream_sends_frames_and_stops_ffmpeg(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    # frames arrive split across chunks, with junk before the first one
    ffmpeg(out=[b"junk" + JPG1[:5], JPG1[5:] + JPG2[:3], JPG2[3:]])
    r = client.get("/api/preview/1/stream")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("multipart/x-mixed-replace; boundary=frame")
    assert r.content == (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + JPG1 + b"\r\n"
                         b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + JPG2 + b"\r\n")
    assert FakeProc.started[0].killed, "ffmpeg must be stopped when the stream ends"
    assert preview._active["count"] == 0, "the stream slot must be freed"


@pytest.mark.parametrize("hd,channel", [(False, "202"), (True, "201")])
def test_grid_uses_sub_stream_and_hd_uses_main(client, fake_box, ffmpeg, hd, channel):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    ffmpeg(out=[JPG1])
    client.get("/api/preview/1/stream", params={"hd": hd})
    url = [a for a in FakeProc.started[0].args if a.startswith("rtsp://")][0]
    assert url.endswith(f"/channels/{channel}")


def test_stream_options(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    ffmpeg(out=[JPG1])
    client.get("/api/preview/3/stream", params={"width": 640, "fps": 5})
    args = FakeProc.started[0].args
    assert "scale='min(640,iw)':-2" in args and args[args.index("-r") + 1] == "5"
    assert args[args.index("-rtsp_transport") + 1] == "tcp"


@pytest.mark.parametrize("url,expected", [
    ("rtsp://u:p@h:554/ISAPI/Streaming/channels/201", "rtsp://u:p@h:554/ISAPI/Streaming/channels/202"),
    ("rtsp://u:p@h:554/ISAPI/Streaming/channels/1601", "rtsp://u:p@h:554/ISAPI/Streaming/channels/1602"),
    ("rtsp://u:p@h:554/ISAPI/Streaming/channels/202", "rtsp://u:p@h:554/ISAPI/Streaming/channels/202"),
    ("rtsp://h/stream1", "rtsp://h/stream1"),                  # not Hikvision: unchanged
])
def test_sub_stream_address(url, expected):
    assert preview._sub_stream(url) == expected


def test_stream_camera_gives_no_video(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    ffmpeg(out=[], err=[b"rtsp://...: 401 Unauthorized\n"])
    r = client.get("/api/preview/1/stream")
    assert r.status_code == 502 and "401 Unauthorized" in r.json()["detail"]
    assert FakeProc.started[0].killed and preview._active["count"] == 0


def test_lots_of_ffmpeg_error_output_is_read_not_left_to_block(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    ffmpeg(out=[JPG1], err=[b"warning %d\n" % i for i in range(5000)])
    assert client.get("/api/preview/1/stream").status_code == 200
    import time
    for _ in range(50):
        if not FakeProc.started[0].stderr.chunks:
            break
        time.sleep(0.02)
    assert FakeProc.started[0].stderr.chunks == [], "stderr must be drained"


def test_too_many_streams(client, fake_box, ffmpeg, monkeypatch):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    ffmpeg(out=[JPG1])
    monkeypatch.setitem(preview._active, "count", preview.MAX_STREAMS)
    r = client.get("/api/preview/1/stream")
    assert r.status_code == 503 and "Too many live videos" in r.json()["detail"]
    assert FakeProc.started == [] and fake_box.calls == []


def test_slot_freed_when_box_lookup_fails(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    client.get("/api/preview/99/stream")          # unknown camera
    assert preview._active["count"] == 0


def test_stream_unknown_camera(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    assert client.get("/api/preview/99/stream").status_code == 404
    assert FakeProc.started == []


def test_stream_camera_without_rtsp(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = [{"device_id": 4, "device_name": "Picture cam", "channel_type": 2}]
    assert client.get("/api/preview/4/stream").status_code == 404


def test_stream_ffmpeg_not_installed(client, fake_box, monkeypatch):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    monkeypatch.setattr(preview.shutil, "which", lambda name: None)
    monkeypatch.setattr(preview, "FFMPEG", "C:/nowhere/ffmpeg.exe")
    r = client.get("/api/preview/1/stream")
    assert r.status_code == 500 and "ffmpeg not found" in r.json()["detail"]
    assert preview._active["count"] == 0


@pytest.mark.parametrize("params", [{"width": 100}, {"width": 5000}, {"fps": 0}, {"fps": 60}, {"width": "big"},
                                    {"hd": "maybe"}])
def test_stream_bad_params(client, fake_box, ffmpeg, params):
    assert client.get("/api/preview/1/stream", params=params).status_code == 422
    assert fake_box.calls == [] and FakeProc.started == []


def test_stream_bad_camera_id(client, fake_box, ffmpeg):
    assert client.get("/api/preview/abc/stream").status_code == 422