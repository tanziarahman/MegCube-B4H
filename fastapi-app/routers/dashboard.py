"""Operational dashboard: live camera health from the box, activity from our database or box
fallback, with every part served through the optional Redis cache."""
import asyncio
import logging
import os
from datetime import date as date_type, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import DBAPIError

import cache
import db
from core import BOX_TZ
from dashboard_data import box_source, queries

log = logging.getLogger("b4h.dashboard")
router = APIRouter()

SOURCE = os.getenv("DASHBOARD_SOURCE", "auto")
HEALTH_TTL = float(os.getenv("DASHBOARD_HEALTH_CACHE_SECONDS", "15"))
TODAY_TTL = float(os.getenv("DASHBOARD_TODAY_CACHE_SECONDS", "15"))
PAST_TTL = float(os.getenv("DASHBOARD_PAST_CACHE_SECONDS", "3600"))
INGEST_LAG = int(os.getenv("DASHBOARD_INGEST_LAG_SECONDS", "120"))
COVERAGE_TTL = 300
_DATABASE_ERRORS = (DBAPIError, OSError, asyncio.TimeoutError, HTTPException)


def _today() -> date_type:
    return (datetime.now(BOX_TZ) if BOX_TZ is not None else datetime.now()).date()


async def _load_coverage() -> dict:
    async with db.sessions()() as session:
        return await queries.coverage(session)


async def _load_database_activity(coverage: dict, day: date_type) -> dict:
    with_previous = SOURCE == "database" or (
        coverage["start"] is not None and day - timedelta(days=1) >= date_type.fromisoformat(coverage["start"]))
    async with db.sessions()() as session:
        activity = await queries.activity(session, coverage["box_id"], day, with_previous=with_previous)
    if not with_previous:
        activity["activity"].update(await box_source.previous_totals(day - timedelta(days=1)))
    return activity


def _attention(health: dict) -> list[dict]:
    rows = health["devices"]
    attention = [
        {"severity": "critical", "type": "offline_camera", "message": f"{row['name']} is offline",
         "device_id": row["id"]}
        for row in rows if not row["online"]
    ]
    attention.extend(
        {"severity": "warning", "type": "stream_not_pulling",
         "message": f"{row['name']} is not pulling a stream", "device_id": row["id"]}
        for row in rows if row["online"] and not row["pulling_stream"]
    )
    attention.extend(
        {"severity": "warning", "type": "no_task", "message": f"{row['name']} has no analysis task",
         "device_id": row["id"]}
        for row in rows if not row["task"]
    )
    if health["clock"]["source"] != "box":
        attention.append({"severity": "warning", "type": "clock_unavailable",
                          "message": "Box clock could not be read", "device_id": None})
    return attention


@router.get("/api/dashboard/summary")
async def dashboard_summary(
    date: str | None = Query(None, description="Box-local date: YYYY-MM-DD"),
    fresh: bool = Query(False, description="Skip the cache (the Refresh button)"),
):
    """Return one operational dashboard snapshot for a single box-local day."""
    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(422, "date must use YYYY-MM-DD") from exc
    else:
        day = _today()
    today = _today()
    previous = day - timedelta(days=1)

    health, health_state = await cache.get_or_load(
        cache.key("dash", "health"), HEALTH_TTL, box_source.load_health, fresh=fresh)
    coverage = None
    fallback_reason = None
    if SOURCE != "box" and db.enabled():
        try:
            coverage, _ = await cache.get_or_load(
                cache.key("dash", "coverage"), COVERAGE_TTL, _load_coverage)
        except _DATABASE_ERRORS:
            if SOURCE == "database":
                raise
            log.warning("Dashboard database coverage unavailable; using box", exc_info=True)
            fallback_reason = "database unavailable"

    if coverage is None or coverage["box_id"] is None:
        source = "box"
    elif SOURCE == "database":
        source = "database"
    elif coverage["start"] and day >= date_type.fromisoformat(coverage["start"]):
        source = "database"
    else:
        source = "box"

    ttl = TODAY_TTL if day >= today else PAST_TTL
    activity_state = "off"
    if source == "database":
        async def load_activity():
            return await _load_database_activity(coverage, day)
    else:
        async def load_activity():
            return await box_source.load_activity(
                day, {str(row["id"]): row["name"] for row in health["devices"]})

    try:
        activity, activity_state = await cache.get_or_load(
            cache.key("dash", "activity", day.isoformat(), source), ttl, load_activity, fresh=fresh)
    except _DATABASE_ERRORS:
        if SOURCE == "database":
            raise
        log.warning("Dashboard database activity unavailable; using box", exc_info=True)
        fallback_reason = "database unavailable"
        source = "box"
        async def load_box_activity():
            return await box_source.load_activity(
                day, {str(row["id"]): row["name"] for row in health["devices"]})
        activity, activity_state = await cache.get_or_load(
            cache.key("dash", "activity", day.isoformat(), source), ttl, load_box_activity, fresh=fresh)

    attention = _attention(health)
    last_success = (activity.get("ingest") or {}).get("last_success_at")
    if source == "database" and last_success:
        last = datetime.fromisoformat(last_success)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        lag = int((datetime.now(timezone.utc) - last).total_seconds())
        if lag > INGEST_LAG:
            attention.append({
                "severity": "warning", "type": "ingest_lagging",
                "message": f"Dashboard numbers may be behind: box records were last read {lag // 60} min ago",
                "device_id": None,
            })
    rows = health["devices"]
    online = [row for row in rows if row["online"]]
    return {
        "date": day.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "period": {
            "start": f"{day} 00:00:00", "end": f"{day} 23:59:59",
            "previous_start": f"{previous} 00:00:00", "previous_end": f"{previous} 23:59:59",
        },
        "health": {
            "devices_total": len(rows), "devices_online": len(online),
            "devices_offline": len(rows) - len(online),
            "streams_pulling": sum(row["pulling_stream"] for row in rows),
            "tasks_total": health["tasks_total"], "clock": health["clock"],
        },
        "activity": activity["activity"],
        "insights": activity["insights"],
        "devices": rows,
        "attention": attention,
        "meta": {
            "source": source, "fallback_reason": fallback_reason,
            "coverage_start": coverage["start"] if coverage else None,
            "cache": {"health": health_state, "activity": activity_state},
            "ingest_last_success_at": last_success,
        },
    }
