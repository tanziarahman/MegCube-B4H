# main.py
import asyncio
import json
import logging
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from b4h_client import B4HClient, B4HError

logging.basicConfig(level=logging.INFO)

B4H_BASE_URL = os.getenv("B4H_BASE_URL", "https://192.168.90.200")
B4H_USER = os.getenv("B4H_USER", "admin")
B4H_PASS = os.getenv("B4H_PASS", "Shohan@98")
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "./media"))
MEDIA_DIR.mkdir(exist_ok=True)

b4h = B4HClient(B4H_BASE_URL, B4H_USER, B4H_PASS, verify_tls=False)

# In-memory store + fan-out to the frontend. Swap for Postgres/Redis later.
recent_events: deque[dict] = deque(maxlen=500)
subscribers: set[asyncio.Queue] = set()


async def publish(event: dict) -> None:
    recent_events.appendleft(event)
    for q in list(subscribers):
        q.put_nowait(event)


def normalize(alarm_info: dict, image_files: list[str], source: str) -> dict:
    g = alarm_info.get("global_info", {})
    add = alarm_info.get("additional", {})
    return {
        "id": g.get("data_uuid") or f"{g.get('device_id')}-{g.get('time_ms')}",
        "source": source,  # "push" or "ws"
        "device_sn": g.get("device_id"),
        "time_ms": int(g.get("time_ms", 0) or 0),
        "major": add.get("alarm_major"),
        "minor": add.get("alarm_minor"),
        "images": image_files,  # served from /media/<name>
        "raw": alarm_info,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    await b4h.login()
    # Optional: real-time pull over websocket. Leave HTTP push on as well if you want retries.
    ws_task = None
    if os.getenv("B4H_USE_WS", "0") == "1":
        async def on_ws_alarm(info: dict, blobs: list[bytes]):
            files = []
            for i, blob in enumerate(blobs):
                name = f"ws_{datetime.now():%Y%m%d_%H%M%S_%f}_{i}.jpg"
                (MEDIA_DIR / name).write_bytes(blob)
                files.append(name)
            await publish(normalize(info, files, "ws"))
        ws_task = asyncio.create_task(b4h.run_alarm_stream(on_ws_alarm))
    yield
    if ws_task:
        ws_task.cancel()
    await b4h.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- 1) PUSH IN
@app.post("/webhook/alarm")
async def receive_alarm(request: Request, sn: str | None = None, type: str | None = None):
    form = await request.form()
    raw = form.get("alarm_info")
    if raw is None:
        return {"status": "ignored"}
    info = json.loads(raw)

    # Heartbeat-like device status every ~10 s: keep latest, don't spam the feed
    if info.get("additional", {}).get("alarm_major") == "equipment_report":
        app.state.device_status = info
        return {"status": "ok"}

    files = []
    for key, value in form.multi_items():
        if key.startswith("alarm_picture_") and hasattr(value, "read"):
            name = f"{sn}_{info['global_info'].get('time_ms')}_{key}.jpg"
            (MEDIA_DIR / name).write_bytes(await value.read())
            files.append(name)
    await publish(normalize(info, files, "push"))
    return {"status": "ok"}  # must be HTTP 200 or the box retries


# ---------------------------------------------------------- 2) FRONTEND OUT
@app.get("/api/events")
async def list_events(limit: int = 50):
    return list(recent_events)[:limit]


@app.get("/api/events/stream")
async def stream_events():
    """Server-Sent Events: in Next.js use `new EventSource('/api/events/stream')`."""
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)

    async def gen():
        try:
            while True:
                ev = await q.get()
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            subscribers.discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/media/{name}")
async def media(name: str):
    p = (MEDIA_DIR / name).resolve()
    if MEDIA_DIR.resolve() not in p.parents or not p.exists():
        raise HTTPException(404)
    return Response(p.read_bytes(), media_type="image/jpeg")


@app.get("/api/device/status")
async def device_status():
    return getattr(app.state, "device_status", None)


# ------------------------------------------------------ 3) PULL FROM B4H API
@app.get("/api/b4h/video-cap")
async def video_cap():
    return await _b4h("GET", "/media_video/cap")


@app.get("/api/b4h/device-info")
async def device_info():
    return await _b4h("GET", "/device_maintenance/device_info")


@app.get("/api/b4h/cameras")
async def cameras():
    """Same two calls the B4H web page makes on Resource -> Device."""
    config = await _b4h("POST", "/device_access/device_config", {"offset": 0, "size": 100})
    state = await _b4h("POST", "/device_access/device_state", {"offset": 0, "size": 100})
    return {"cameras": config, "status": state}


@app.get("/api/b4h/tasks")
async def tasks():
    return await _b4h("POST", "/intelli_manager/task_list", {})


@app.get("/api/b4h/alarm-types")
async def alarm_types():
    return await _b4h("GET", "/device_alarm/alarm_cap")


@app.post("/api/b4h/alarm-history")
async def alarm_history(body: dict):
    """
    Box limits: max 30 per page, ONE major type + ONE minor type per query.
    Example body:
    {"offset":0,"size":30,"query_condition":{"start_time":"1790200000000","end_time":"1790300000000",
      "alarm_type":[{"major_type":"face_basic_business","minor_type":["face_comparison_successful"]}]}}
    """
    return await _b4h("POST", "/device_alarm/alarm_history", body)


@app.get("/api/b4h/image")
async def b4h_image(uri: str):
    """Images referenced in history records (image_data_format == 2) live under /web/<uri>."""
    try:
        path = "/web/" + uri.lstrip("./")
        data, ctype = await b4h.get_bytes(path)
    except Exception:
        data, ctype = await b4h.get_bytes("/device_storage/get_image", {"image_uri": uri})
    return Response(data, media_type=ctype)


@app.post("/api/b4h/groups")
async def person_groups():
    return await _b4h("POST", "/face_manager/groups/query", {})


@app.post("/api/b4h/persons")
async def create_person(
    name: str = Form(...),
    photo: UploadFile = File(...),
    group_id: str | None = Form(None),  # e.g. "2" or "2,3"; empty -> Default Group only
    remarks: str | None = Form(None),
):
    """Same as B4H web: Personnel -> New Person -> upload photo + name + group."""
    img = await photo.read()
    ext = (photo.filename or "face.jpg").rsplit(".", 1)[-1].lower()
    ext = ext if ext in {"jpeg", "jpg", "png", "bmp", "jfif"} else "jpg"

    # Group IDs: "1" = Default Group (the web page always includes it).
    # group_id can be one ID or a comma list, e.g. "2" or "2,3". Swagger's "string" placeholder is ignored.
    ids = ["1"]
    if group_id and group_id.strip().lower() != "string":
        ids += [g.strip() for g in group_id.split(",") if g.strip() and g.strip() != "1"]

    # Copied exactly from what the B4H web page sends (DevTools -> Payload)
    person_info = {
        "person_info": {"name": name, "remarks": remarks or ""},
        "face_data": {
            "data_type": 0,            # 0 = image
            "save_image": True,
            "feature_version": "",
            "data": [{"data_size": len(img)}],
        },
        "groups": [{"group_id": g} for g in ids],
    }

    try:
        return await b4h.call_multipart(
            "/face_manager/person",
            fields={"person_info": json.dumps(person_info, ensure_ascii=False)},
            files={"face1": (photo.filename or f"face.{ext}", img, photo.content_type or "image/jpeg")},
        )
    except B4HError as e:
        raise HTTPException(status_code=502, detail={"b4h_code": e.code, "message": e.message, "path": e.path})


@app.post("/api/b4h/persons/query")
async def persons(body: dict):
    return await _b4h("POST", "/face_manager/person/query", body)


# Generic escape hatch while you explore: POST /api/b4h/raw {"method":"GET","path":"/device_alarm/cap"}
@app.post("/api/b4h/raw")
async def raw(body: dict):
    return await _b4h(body.get("method", "GET"), body["path"], body.get("body"))


async def _b4h(method: str, path: str, body=None):
    try:
        return await b4h.call(method, path, body)
    except B4HError as e:
        raise HTTPException(status_code=502, detail={"b4h_code": e.code, "message": e.message, "path": e.path})