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

    def read(self):
        return b"".join(self.chunks)


class FakeProc:
    """Pretends to be ffmpeg: stdout gives the chunks, then ends."""
    started: list["FakeProc"] = []

    def __init__(self, args, stdout=None, stderr=None, out=(), err=b""):
        self.args, self.killed = args, False
        self.stdout, self.stderr = FakeStream(out), FakeStream([err])
        FakeProc.started.append(self)

    def kill(self):
        self.killed = True


@pytest.fixture
def ffmpeg(monkeypatch):
    """Call ffmpeg(out=[...chunks], err=b'...') to decide what the fake ffmpeg produces."""
    FakeProc.started = []
    monkeypatch.setattr(preview.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    def setup(out=(), err=b""):
        monkeypatch.setattr(preview.subprocess, "Popen", lambda args, **kw: FakeProc(args, out=out, err=err))
    return setup


# ---------- camera list ----------

def test_cameras(client, fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    fake_box.replies[STATE] = DEVICE_STATE
    fake_box.replies[TASKS] = TASK_LIST
    r = client.get("/api/preview/cameras")
    assert r.json() == [
        {"id": 1, "name": "Hikvision", "online": True, "task": "FR"},
        {"id": 2, "name": "IPCAM-D3", "online": True, "task": None},
        {"id": 3, "name": "CAM3-D4", "online": False, "task": None},
    ]
    assert "s3cret" not in r.text and "rtsp" not in r.text


@pytest.mark.parametrize("states,tasks", [(None, None), ([], {}), ([], {"list": []}), ([], {"list": [{"task_name": "X"}]})])
def test_cameras_missing_state_and_tasks(client, fake_box, states, tasks):
    fake_box.replies[CONFIG] = DEVICE_CONFIG[:1]
    fake_box.replies[STATE] = states
    fake_box.replies[TASKS] = tasks
    assert client.get("/api/preview/cameras").json() == [{"id": 1, "name": "Hikvision", "online": False, "task": None}]


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


def test_stream_uses_that_cameras_rtsp_url(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    ffmpeg(out=[JPG1])
    client.get("/api/preview/3/stream", params={"width": 640, "fps": 5})
    args = FakeProc.started[0].args
    assert DEVICE_CONFIG[2]["rtsp_param"]["url"] in args
    assert "scale=640:-2" in args and args[args.index("-r") + 1] == "5"
    assert args[args.index("-rtsp_transport") + 1] == "tcp"


def test_stream_camera_gives_no_video(client, fake_box, ffmpeg):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    ffmpeg(out=[], err=b"rtsp://...: 401 Unauthorized")
    r = client.get("/api/preview/1/stream")
    assert r.status_code == 502 and "401 Unauthorized" in r.json()["detail"]
    assert FakeProc.started[0].killed


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


@pytest.mark.parametrize("params", [{"width": 100}, {"width": 5000}, {"fps": 0}, {"fps": 60}, {"width": "big"}])
def test_stream_bad_params(client, fake_box, ffmpeg, params):
    assert client.get("/api/preview/1/stream", params=params).status_code == 422
    assert fake_box.calls == [] and FakeProc.started == []


def test_stream_bad_camera_id(client, fake_box, ffmpeg):
    assert client.get("/api/preview/abc/stream").status_code == 422
