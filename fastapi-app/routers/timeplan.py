"""Time-plan queries and stream cleanup backed by the box APIs."""
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from b4h import B4HError
from core import box, log

router = APIRouter()


class StreamHandlesIn(BaseModel):
    handles: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    device_alarm_handles: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)


class SchedulePlanIn(BaseModel):
    schedule_plan_id: str = Field(min_length=1)
    schedule_plan_name: str = Field(min_length=1, max_length=128)
    schedule_plan_type: Literal[1, 2]
    week_schedule: dict[str, list[str]]
    bind_schedule_plan: list[dict[str, Any]] = Field(default_factory=list)


class SchedulePlanCreateIn(BaseModel):
    schedule_plan_name: str = Field(min_length=1, max_length=128)
    schedule_plan_type: Literal[1, 2]
    week_schedule: dict[str, list[str]]
    bind_schedule_plan: list[dict[str, Any]] = Field(default_factory=list)


class SchedulePlanDeleteIn(BaseModel):
    schedule_plan_id: str = Field(min_length=1)
    schedule_plan_type: Literal[1, 2]


async def _optional_box_call(path: str):
    try:
        return await box.call("POST", path) or {}
    except B4HError as exc:
        if exc.code != 404:
            raise
        log.warning("Optional timeplan endpoint is unavailable on the box: %s", path)
        return {}


@router.get("/api/timeplans/time")
async def timeplan_time():
    """Return the box time configuration and its current clock value.

    The box UI loads these independently with POST requests. They are kept
    sequential here because the box rejects concurrent API queries.
    """
    system_time = await _optional_box_call("/system/get_system_time")
    current_time = await _optional_box_call("/system/get_time_info")
    if not current_time.get("time"):
        current_time = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "backend_fallback",
        }
    return {
        "system_time": system_time,
        "current_time": current_time,
        "clock_source": "box" if system_time and current_time.get("source") != "backend_fallback" else "backend_fallback",
    }


async def _query_plans(plan_type: int, size: int):
    return await box.call("POST", "/device_rules/schedule_plan/query", {
        "offset": 0,
        "size": size,
        "schedule_plan_type": plan_type,
    }) or {}


@router.get("/api/timeplans/regular")
async def regular_timeplans():
    """Return regular plans, matching the box UI's type-1 query."""
    return await _query_plans(plan_type=1, size=100)


@router.get("/api/timeplans/festival")
async def festival_timeplans():
    """Return festival plans, matching the box UI's type-2 query."""
    return await _query_plans(plan_type=2, size=50)


@router.post("/api/timeplans", status_code=201)
async def create_timeplan(body: SchedulePlanCreateIn):
    """Create a schedule plan using the box UI's POST payload."""
    result = await box.call("POST", "/device_rules/schedule_plan", body.model_dump())
    return {"data": result or {}, "schedule_plan_name": body.schedule_plan_name}


@router.put("/api/timeplans/{plan_id}")
async def update_timeplan(body: SchedulePlanIn, plan_id: str = Path(..., min_length=1)):
    """Update an existing schedule plan using the box UI's PUT payload."""
    if body.schedule_plan_id != plan_id:
        raise HTTPException(422, "plan_id must match schedule_plan_id")
    result = await box.call("PUT", "/device_rules/schedule_plan", body.model_dump())
    return {"schedule_plan_id": plan_id, "data": result or {}}


# Declared before DELETE /api/timeplans/{plan_id}: FastAPI matches routes in order, so otherwise
# "stream-subscriptions" would be taken as a plan id.
@router.delete("/api/timeplans/stream-subscriptions")
async def unsubscribe_streams(body: StreamHandlesIn):
    """Stop media-video and device-alarm stream subscriptions used by the view."""
    if not body.handles and not body.device_alarm_handles:
        raise HTTPException(422, "At least one stream handle is required")

    for handle in body.handles:
        await box.call("DELETE", "/media_video/subscribe_stream", {"handle": handle})
    for handle in body.device_alarm_handles:
        await box.call("DELETE", "/device_alarm/subscribe_stream", {"handle": handle})
    return {
        "media_video_handles": body.handles,
        "device_alarm_handles": body.device_alarm_handles,
    }


@router.delete("/api/timeplans/{plan_id}")
async def delete_timeplan(body: SchedulePlanDeleteIn, plan_id: str = Path(..., min_length=1)):
    """Delete an existing schedule plan using the box UI's DELETE payload."""
    if body.schedule_plan_id != plan_id:
        raise HTTPException(422, "plan_id must match schedule_plan_id")
    result = await box.call("DELETE", "/device_rules/schedule_plan", body.model_dump())
    return {"deleted": plan_id, "data": result or {}}
