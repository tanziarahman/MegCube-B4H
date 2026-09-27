"""HTTP endpoints for the Recognition page. Thin: parse input, call the controller, return models."""
from datetime import datetime, time
from typing import Literal

from fastapi import APIRouter, Query, Response

from app.controllers import device_controller, recognition_controller as ctrl
from app.core import config
from app.models.device import Camera, Group
from app.models.recognition import RecognitionPage, RecognitionQuery, RecognitionRecord

router = APIRouter(prefix="/api/recognition", tags=["recognition"])


def _today_ms() -> tuple[int, int]:
    today = datetime.now(config.TIMEZONE).date()
    start = datetime.combine(today, time.min, config.TIMEZONE)
    end = datetime.combine(today, time.max, config.TIMEZONE)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _to_ms(dt: datetime | None, default: int) -> int:
    if dt is None:
        return default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.TIMEZONE)
    return int(dt.timestamp() * 1000)


@router.get("/records", response_model=RecognitionPage, response_model_exclude_none=True)
async def list_records(
    start: datetime | None = Query(None, description="ISO date-time. Default: today 00:00"),
    end: datetime | None = Query(None, description="ISO date-time. Default: today 23:59:59"),
    result: Literal["all", "matched", "stranger"] = "all",
    camera_id: str | None = None,
    name: str | None = Query(None, description="Person name or ID contains"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=30),
    include_raw: bool = Query(False, description="Add the original box record to each item"),
):
    d_start, d_end = _today_ms()
    q = RecognitionQuery(start_ms=_to_ms(start, d_start), end_ms=_to_ms(end, d_end), result=result,
                         camera_id=camera_id, name=name, page=page, size=size, include_raw=include_raw)
    return await ctrl.list_records(q)


@router.get("/records/{record_id}", response_model=RecognitionRecord, response_model_exclude_none=True)
async def get_record(record_id: str):
    return ctrl.get_record(record_id)


@router.get("/image")
async def image(uri: str):
    data, content_type = await ctrl.get_image(uri)
    return Response(data, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"})


@router.get("/cameras", response_model=list[Camera])
async def cameras():
    return await device_controller.list_cameras()


@router.get("/groups", response_model=list[Group])
async def groups():
    return await device_controller.list_groups()


# ---- helpers while wiring up the real box ---------------------------------
@router.get("/types", tags=["debug"])
async def types():
    """Face alarm types on the box. Use it to confirm the matched / stranger minor type names."""
    return await ctrl.alarm_types()


@router.get("/raw-sample", tags=["debug"])
async def raw_sample(result: Literal["matched", "stranger"] = "matched", days: int = Query(7, ge=1, le=90)):
    """One untouched box record, to check the field mapping."""
    _, end = _today_ms()
    return await ctrl.raw_sample(result, end - days * 86_400_000, end)
