"""People counting: walk-pasts and different people per camera, from our database (DATABASE_URL).

Sightings are built from the box records the alarm poller already stores (counting/builder.py); no
extra box calls. Times in and out follow the rest of the portal: query strings are
'YYYY-MM-DD HH:mm:ss' in the box's time zone, responses are ISO timestamps.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import db
from alarms.rules import plain
from core import BOX_TIMEZONE_NAME, to_ms
from counting import queries
from counting.settings import box_tz
from models import AuditLog, Camera, CountBasis

router = APIRouter()

Session = Annotated[AsyncSession, Depends(db.get_session)]
MAX_RANGE = timedelta(days=366)
# Longest range each chart granularity may cover (more points than this isn't readable).
MAX_SERIES_RANGE = {"15m": timedelta(days=7), "hour": timedelta(days=62), "day": timedelta(days=366)}
_HOURS = re.compile(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$")


class Period(BaseModel):
    start: datetime
    end: datetime
    hours: tuple[int, int] | None
    days: tuple[int, ...] | None


def _parse_time(value: str) -> datetime:
    return datetime.fromtimestamp(to_ms(value) / 1000, timezone.utc)


def period(start: str | None = None, end: str | None = None, hours: str | None = None,
           days: str | None = None) -> Period:
    """Time filters shared by every route; checked before the database is touched.
    Default: today from 00:00 (box time) until now."""
    now = datetime.now(timezone.utc)
    since = _parse_time(start) if start else \
        now.astimezone(box_tz()).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    until = _parse_time(end) if end else now
    if since >= until:
        raise HTTPException(422, "start must be before end")
    if until - since > MAX_RANGE:
        raise HTTPException(422, "The range can be at most 366 days")

    hour_window = None
    if hours:
        m = _HOURS.match(hours)
        if not m or not all(0 <= int(h) <= 23 for h in m.groups()):
            raise HTTPException(422, f"Bad hours '{hours}', expected e.g. 9-17 or 22-5 (hours 0-23)")
        hour_window = (int(m[1]), int(m[2]))

    weekdays = None
    if days:
        try:
            weekdays = tuple(sorted({int(d) for d in days.split(",") if d.strip()}))
        except ValueError:
            weekdays = ()
        if not weekdays or not all(1 <= d <= 7 for d in weekdays):
            raise HTTPException(422, f"Bad days '{days}', expected ISO weekdays 1-7, e.g. 1,2,3,4,5")
    return Period(start=since, end=until, hours=hour_window, days=weekdays)


Filters = Annotated[Period, Depends(period)]


async def _filters(session: AsyncSession, p: Period, camera_ids: list[int]) -> queries.Filters:
    """Default cameras: every camera included in counting. Asked-for cameras must exist."""
    if camera_ids:
        wanted = set(camera_ids)
        rows = (await session.exec(select(Camera).where(
            col(Camera.id).in_(wanted), col(Camera.deleted_at).is_(None)))).all()
        if missing := wanted - {c.id for c in rows}:
            raise HTTPException(422, f"Unknown or removed camera(s): {sorted(missing)}")
    else:
        rows = (await session.exec(select(Camera).where(
            col(Camera.count_enabled).is_(True), col(Camera.deleted_at).is_(None)))).all()
    return queries.Filters(cameras={c.id: plain(c.count_basis) for c in rows}, start=p.start, end=p.end,
                           hours=p.hours, days=p.days)


def _period_out(p: Period) -> dict:
    tz = box_tz()
    return {"start": p.start.astimezone(tz), "end": p.end.astimezone(tz), "timezone": BOX_TIMEZONE_NAME}


CameraIds = Annotated[list[int], Query(alias="camera_id", default_factory=list)]


@router.get("/api/counting/summary")
async def counting_summary(p: Filters, session: Session, camera_ids: CameraIds):
    """Walk-pasts, visits and different people, in total and per camera."""
    f = await _filters(session, p, camera_ids)
    return {"period": _period_out(p), **await queries.summary(session, f)}


@router.get("/api/counting/series")
async def counting_series(p: Filters, session: Session, camera_ids: CameraIds,
                          granularity: str = Query("hour", pattern="^(15m|hour|day)$")):
    """Walk-pasts over time, zero-filled."""
    if p.end - p.start > MAX_SERIES_RANGE[granularity]:
        hint = "hour" if p.end - p.start <= MAX_SERIES_RANGE["hour"] else "day"
        limit = MAX_SERIES_RANGE[granularity].days
        raise HTTPException(422, f"'{granularity}' covers at most {limit} days; use granularity={hint}")
    f = await _filters(session, p, camera_ids)
    return {"period": _period_out(p), "granularity": granularity,
            "points": await queries.series(session, f, granularity)}


@router.get("/api/counting/heatmap")
async def counting_heatmap(p: Filters, session: Session, camera_ids: CameraIds):
    """Average walk-pasts per weekday x hour (busy times)."""
    f = await _filters(session, p, camera_ids)
    return {"period": _period_out(p), **await queries.heatmap(session, f)}


@router.get("/api/counting/sightings")
async def counting_sightings(p: Filters, session: Session, camera_ids: CameraIds,
                             page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    """The walk-pasts behind the numbers, newest first. Images: GET /api/image?uri=<path>."""
    f = await _filters(session, p, camera_ids)
    return await queries.sightings(session, f, page, size)


# ---------- camera settings ----------

def _camera_out(c: Camera) -> dict:
    return {"id": c.id, "device_id": c.device_id, "name": c.name, "deleted": c.deleted_at is not None,
            "count_enabled": c.count_enabled, "count_basis": plain(c.count_basis)}


class CameraSettings(BaseModel):
    count_enabled: bool | None = None
    count_basis: CountBasis | None = None


@router.get("/api/counting/cameras")
async def counting_cameras(session: Session):
    """Cameras and their counting settings. The alarm poller keeps this list in sync with the box."""
    cameras = (await session.exec(select(Camera).order_by(Camera.device_id))).all()
    return [_camera_out(c) for c in cameras]


@router.patch("/api/counting/cameras/{camera_id}")
async def update_counting_camera(body: CameraSettings, session: Session, camera_id: int = Path(..., ge=1)):
    camera = await session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(404, f"Camera #{camera_id} doesn't exist")
    before = _camera_out(camera)
    if body.count_enabled is not None:
        camera.count_enabled = body.count_enabled
    if body.count_basis is not None:
        camera.count_basis = body.count_basis.value
    camera.updated_at = datetime.now(timezone.utc)
    session.add(camera)
    after = _camera_out(camera)
    session.add(AuditLog(actor="portal", action="update", entity_type="camera_counting", entity_id=str(camera_id),
                         before=before, after=after))
    await session.commit()
    return after
