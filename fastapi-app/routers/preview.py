"""Live preview: camera list + live video for the frontend Live view page.

The box's own Preview page uses media_video/subscribe_stream + a Windows plugin to decode its video.
Browsers can't do that, so instead we read each camera's RTSP address from device_config and let
ffmpeg turn it into MJPEG, which a plain <img> tag can show. Needs ffmpeg installed
(Windows: `winget install ffmpeg`, then open a new terminal), or set FFMPEG_PATH in .env.
"""
import asyncio
import logging
import os
import shutil
import subprocess

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from core import box

router = APIRouter()

FFMPEG = os.getenv("FFMPEG_PATH", "ffmpeg")
log = logging.getLogger("preview")


@router.get("/api/preview/cameras")
async def preview_cameras():
    """Cameras for the Live view: id, name, online, task name. RTSP passwords are NOT sent to the browser."""
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
        }
        for c in configs
    ]


async def _rtsp_url(device_id: int) -> str:
    configs = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 50}) or []
    for c in configs:
        if c.get("device_id") == device_id:
            url = (c.get("rtsp_param") or {}).get("url")
            if url:
                return url
    raise HTTPException(404, f"Camera {device_id} not found or has no RTSP address")


def _ffmpeg_args(rtsp_url: str, width: int, fps: int) -> list[str]:
    return [FFMPEG, "-loglevel", "error", "-rtsp_transport", "tcp", "-i", rtsp_url,
            "-an", "-vf", f"scale={width}:-2", "-r", str(fps), "-q:v", "7", "-f", "mjpeg", "pipe:1"]


@router.get("/api/preview/{device_id}/stream")
async def preview_stream(
    device_id: int,
    width: int = Query(960, ge=160, le=1920),
    fps: int = Query(10, ge=1, le=25),
):
    """Live MJPEG video. Frontend: <img src="http://localhost:8000/api/preview/1/stream" />"""
    url = await _rtsp_url(device_id)
    exe = shutil.which(FFMPEG) or (FFMPEG if os.path.isfile(FFMPEG) else None)
    if exe is None:
        raise HTTPException(500, f"ffmpeg not found ('{FFMPEG}'). Restart the backend from a NEW terminal "
                                 "after installing ffmpeg, or set FFMPEG_PATH in .env to the full path of ffmpeg.exe")
    args = _ffmpeg_args(url, width, fps)
    args[0] = exe
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for the first bytes, so a bad stream returns a clear error instead of an empty video.
    try:
        first = await asyncio.wait_for(asyncio.to_thread(proc.stdout.read1, 65536), timeout=20)
    except asyncio.TimeoutError:
        first = b""
    if not first:
        proc.kill()
        err = proc.stderr.read().decode(errors="replace").strip()[-500:]
        log.warning("ffmpeg failed for camera %s: %s", device_id, err or "no output within 20 s")
        raise HTTPException(502, f"No video from camera {device_id}: {err or 'no frames within 20 s'}")

    async def frames():
        buf = first
        try:
            while True:
                chunk = await asyncio.to_thread(proc.stdout.read1, 65536)
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
            proc.kill()  # browser closed the tile -> stop ffmpeg

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"})