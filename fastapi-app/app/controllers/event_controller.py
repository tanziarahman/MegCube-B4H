"""Live events from the box (HTTP push or websocket), kept in memory and fanned out over SSE."""
import asyncio
import json
from collections import deque
from datetime import datetime

from app.core import config
from app.models.event import LiveEvent

recent_events: deque[dict] = deque(maxlen=500)       # swap for a database later
subscribers: set[asyncio.Queue] = set()
device_status: dict | None = None                    # latest "equipment_report" heartbeat


async def publish(event: dict) -> None:
    recent_events.appendleft(event)
    for q in list(subscribers):
        q.put_nowait(event)


def normalize(alarm_info: dict, image_files: list[str], source: str) -> dict:
    g = alarm_info.get("global_info", {})
    add = alarm_info.get("additional", {})
    return LiveEvent(
        id=g.get("data_uuid") or f"{g.get('device_id')}-{g.get('time_ms')}",
        source=source,
        device_sn=g.get("device_id"),
        time_ms=int(g.get("time_ms", 0) or 0),
        major=add.get("alarm_major"),
        minor=add.get("alarm_minor"),
        images=image_files,
        raw=alarm_info,
    ).model_dump()


async def handle_push(form, sn: str | None) -> dict:
    """Body of POST /webhook/alarm. Must answer 200 or the box keeps retrying."""
    global device_status
    raw = form.get("alarm_info")
    if raw is None:
        return {"status": "ignored"}
    info = json.loads(raw)

    if info.get("additional", {}).get("alarm_major") == "equipment_report":
        device_status = info                         # heartbeat every ~10 s: keep latest only
        return {"status": "ok"}

    files = []
    for key, value in form.multi_items():
        if key.startswith("alarm_picture_") and hasattr(value, "read"):
            name = f"{sn}_{info['global_info'].get('time_ms')}_{key}.jpg"
            (config.MEDIA_DIR / name).write_bytes(await value.read())
            files.append(name)
    await publish(normalize(info, files, "push"))
    return {"status": "ok"}


async def on_ws_alarm(info: dict, blobs: list[bytes]) -> None:
    files = []
    for i, blob in enumerate(blobs):
        name = f"ws_{datetime.now():%Y%m%d_%H%M%S_%f}_{i}.jpg"
        (config.MEDIA_DIR / name).write_bytes(blob)
        files.append(name)
    await publish(normalize(info, files, "ws"))


def list_events(limit: int, major: str | None) -> list[dict]:
    events = [e for e in recent_events if major is None or e.get("major") == major]
    return events[:limit]


async def event_stream(major: str | None):
    """Server-Sent Events generator; optional `major` filter (e.g. face_basic_business)."""
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)
    try:
        while True:
            ev = await q.get()
            if major is None or ev.get("major") == major:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
    finally:
        subscribers.discard(q)
