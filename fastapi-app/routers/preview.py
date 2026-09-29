"""Live preview: camera list + live video for the frontend Live view page.

The box's own Preview page uses media_video/subscribe_stream + a Windows plugin to decode its video.
Browsers can't do that, so instead we read each camera's RTSP address from device_config and let
ffmpeg turn it into MJPEG, which a plain <img> tag can show. The backend starts and stops ffmpeg
itself (one per open tile). Needs ffmpeg installed (Windows: `winget install ffmpeg`), or set
FFMPEG_PATH in .env to the full path of ffmpeg.exe.

Grid tiles use the camera's light sub-stream (Hikvision channel 201 -> 202); `?hd=true` uses the
full-resolution main stream (full screen / the 1-tile layout).

At most MAX_STREAMS videos run at once (default 16, set in .env); each one keeps a worker thread
busy reading ffmpeg's output, so they get their own thread pool instead of Python's small default one.
"""
import asyncio
import collections
import logging
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from core import box, sign_stream

router = APIRouter()

FFMPEG = os.getenv("FFMPEG_PATH", "ffmpeg")
MAX_STREAMS = int(os.getenv("MAX_STREAMS", "16"))
FIRST_FRAME_TIMEOUT = 20  # seconds
log = logging.getLogger("preview")

_readers = ThreadPoolExecutor(max_workers=MAX_STREAMS + 2, thread_name_prefix="ffmpeg-read")
_active = {"count": 0}


@router.get("/api/preview/cameras")
async def preview_cameras():
    """Cameras for the Live view: id, name, online, task name, and the signed part of the stream URL.
    RTSP addresses/passwords are NOT sent to the browser."""
    configs = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 50}) or []
    states = await box.call("POST", "/device_access/device_state", {"offset": 0, "size": 50}) or []
    tasks = await box.call("POST", "/intelli_manager/task_list", {"offset": 0, "size": 50, "condition": {}}) or {}

    online = {s.get("device_id"): s.get("state") == 0 for s in states}  # state 0 = online (as on the box's page)
    task_of = {d.get("device_id"): t.get("task_name") for t in tasks.get("list", []) for d in t.get("device_list", [])}
    return [
        {
            "id": c.get("device_id"),
            "name": c.get("device_name"),
            "online": online.get(c.get("device_id"), False),
            "task": task_of.get(c.get("device_id")),
            # add to the stream URL: /api/preview/{id}/stream?<stream_token> (needed when API_KEY is set)
            "stream_token": sign_stream(c.get("device_id")) if isinstance(c.get("device_id"), int) else None,
        }
        for c in configs
    ]


def _sub_stream(url: str) -> str:
    """Hikvision: channel 201 -> 202 (sub-stream). Other URLs are left unchanged."""
    return re.sub(r"(/channels/\d+)01$", r"\g<1>02", url)


async def _rtsp_url(device_id: int) -> str:
    configs = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 50}) or []
    for c in configs:
        if c.get("device_id") == device_id:
            url = (c.get("rtsp_param") or {}).get("url")
            if url:
                return url
    raise HTTPException(404, f"Camera {device_id} not found or has no RTSP address")


def _ffmpeg_args(exe: str, rtsp_url: str, width: int, fps: int) -> list[str]:
    return [exe, "-loglevel", "error", "-rtsp_transport", "tcp", "-i", rtsp_url,
            "-an", "-vf", f"scale='min({width},iw)':-2", "-r", str(fps), "-q:v", "7", "-f", "mjpeg", "pipe:1"]


def _drain(pipe, keep: collections.deque) -> None:
    """Keep reading ffmpeg's error output so it can never fill up and freeze ffmpeg; keep the last lines."""
    try:
        for line in iter(pipe.readline, b""):
            keep.append(line.decode(errors="replace").strip())
    except (OSError, ValueError):
        pass


@router.get("/api/preview/{device_id}/stream")
async def preview_stream(
    device_id: int,
    hd: bool = Query(False, description="true = main stream (full resolution), false = sub-stream"),
    width: int = Query(960, ge=160, le=1920),
    fps: int = Query(10, ge=1, le=25),
):
    """Live MJPEG video. Frontend: <img src="http://localhost:8001/api/preview/1/stream?...">"""
    if _active["count"] >= MAX_STREAMS:
        raise HTTPException(503, f"Too many live videos open ({MAX_STREAMS}). Close some tiles or tabs and retry.")
    url = await _rtsp_url(device_id)
    if not hd:
        url = _sub_stream(url)
    exe = shutil.which(FFMPEG) or (FFMPEG if os.path.isfile(FFMPEG) else None)
    if exe is None:
        raise HTTPException(500, f"ffmpeg not found ('{FFMPEG}'). Install ffmpeg, or set FFMPEG_PATH in .env "
                                 "to the full path of ffmpeg.exe, then restart the backend")

    _active["count"] += 1
    proc = subprocess.Popen(_ffmpeg_args(exe, url, width, fps), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    errors: collections.deque = collections.deque(maxlen=20)
    drainer = threading.Thread(target=_drain, args=(proc.stderr, errors), daemon=True)
    drainer.start()
    stopped = {"done": False}

    def stop() -> None:
        """Kill ffmpeg and free the slot. Safe to call more than once."""
        if not stopped["done"]:
            stopped["done"] = True
            proc.kill()
            _active["count"] -= 1

    loop = asyncio.get_running_loop()

    def read() -> "asyncio.Future[bytes]":
        return loop.run_in_executor(_readers, proc.stdout.read1, 65536)

    # Wait for the first bytes, so a bad stream returns a clear error instead of an empty video.
    try:
        first = await asyncio.wait_for(read(), timeout=FIRST_FRAME_TIMEOUT)
    except asyncio.TimeoutError:
        first = b""
    except BaseException:
        stop()
        raise
    if not first:
        stop()
        drainer.join(timeout=2)
        err = " | ".join(errors)[-500:]
        log.warning("ffmpeg failed for camera %s (%s): %s", device_id, "HD" if hd else "SD", err or "no output")
        raise HTTPException(502, f"No video from camera {device_id}: {err or f'no frames within {FIRST_FRAME_TIMEOUT} s'}")

    async def frames():
        buf = first
        try:
            while True:
                chunk = await read()
                if not chunk:
                    break  # camera stream ended
                buf += chunk
                # cut the byte stream into single JPEG images (start FFD8 ... end FFD9)
                while True:
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9", start + 2)
                    if start == -1 or end == -1:
                        break
                    jpg, buf = buf[start:end + 2], buf[end + 2:]
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
        finally:
            stop()  # browser closed the tile -> stop ffmpeg

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"}, background=BackgroundTask(stop))