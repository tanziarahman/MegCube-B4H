"""Box push webhook + live events for the frontend."""
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app.controllers import event_controller as ctrl
from app.core import config

router = APIRouter(tags=["events"])


@router.post("/webhook/alarm")
async def receive_alarm(request: Request, sn: str | None = None, type: str | None = None):
    return await ctrl.handle_push(await request.form(), sn)


@router.get("/api/events")
async def list_events(limit: int = 50, major: str | None = None):
    return ctrl.list_events(limit, major)


@router.get("/api/events/stream")
async def stream_events(major: str | None = None):
    """SSE. Recognition only: /api/events/stream?major=face_basic_business"""
    return StreamingResponse(ctrl.event_stream(major), media_type="text/event-stream")


@router.get("/media/{name}")
async def media(name: str):
    p = (config.MEDIA_DIR / name).resolve()
    if config.MEDIA_DIR.resolve() not in p.parents or not p.exists():
        raise HTTPException(404)
    return Response(p.read_bytes(), media_type="image/jpeg")


@router.get("/api/device/status")
async def device_status():
    return ctrl.device_status
