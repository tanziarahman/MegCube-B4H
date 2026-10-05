"""Reads new records from the box (polling alarm_history) into `events` and fires the alarm rules.

Each poll reads the time window [cursor - overlap, now] (capped at MAX_WINDOW, so catching up after
downtime goes in slices) and saves the records with ON CONFLICT DO NOTHING. Only records we hadn't
seen go on to people counting (sightings) and the rules, in the same transaction, so re-reading the
overlap is harmless.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import counting
import cache
from core import BOX_BASE_URL, BOX_MAX_PAGE_SIZE, BOX_TIMEZONE_NAME, RECOG_MAJOR, alarm_history_page, box
from counting.settings import box_tz
from models import Box, Camera, Event, EventSource, IngestCursor, IngestStream

from . import engine
from .normalize import normalize

log = logging.getLogger("b4h.ingest")

OVERLAP = timedelta(seconds=int(os.getenv("ALARM_POLL_OVERLAP_SECONDS", "60")))
FIRST_LOOKBACK = timedelta(minutes=5)      # first run: don't replay the box's whole history as alarms
MAX_WINDOW = timedelta(minutes=15)         # catching up after downtime: one slice per poll
# The box stamps records with ITS clock. If it runs ahead of this PC, its newest records look
# "in the future": each query also asks this far past now, so they aren't held back until this
# PC's clock catches up. (A box clock that runs BEHIND is covered by OVERLAP.)
FUTURE_SLACK = timedelta(minutes=10)
MAX_PAGES = 100                            # 3000 records per slice; more is logged

# The box needs different queries for these (captures need the "structure" entry). Same request
# bodies as routers/recognition.py and routers/capture.py.
_STREAM_ALARM_TYPES = {
    IngestStream.RECOGNITION: [{"major_type": RECOG_MAJOR, "minor_type": ["face_comparison_successful", "stranger"]}],
    IngestStream.CAPTURE: [
        {"major_type": RECOG_MAJOR, "minor_type": ["face_capture", "body_capture"]},
        {"major_type": "structure", "minor_type": ["face", "pedestrian", "vehicle", "non_motor", "plate"]},
    ],
}


def _ms(at: datetime) -> str:
    return str(int(at.timestamp() * 1000))


async def fetch_records(stream: IngestStream, start: datetime, end: datetime) -> list[dict]:
    """Every box record of this stream in [start, end]."""
    condition: dict = {"start_time": _ms(start), "end_time": _ms(end), "alarm_type": _STREAM_ALARM_TYPES[stream]}
    if stream == IngestStream.RECOGNITION:
        condition["ext"] = {"query_type": 0, "de_dup": 0}
    records: list[dict] = []
    for _ in range(MAX_PAGES):
        page = await alarm_history_page({"offset": len(records), "size": BOX_MAX_PAGE_SIZE,
                                         "query_condition": condition})
        batch = page.get("list") or []
        records.extend(batch)
        if len(batch) < BOX_MAX_PAGE_SIZE:      # a short page is the last one
            return records
    log.warning("More than %s records between %s and %s (%s); the rest is skipped",
                len(records), start, end, stream.value)
    return records


# ---------- box and cameras ----------

async def ensure_box(session: AsyncSession) -> int:
    """The `boxes` row for the box in .env (B4H_BASE_URL), created on first use."""
    stmt = pg_insert(Box.__table__).values(name="B4H box", base_url=BOX_BASE_URL, timezone=BOX_TIMEZONE_NAME)
    stmt = stmt.on_conflict_do_update(index_elements=["base_url"], set_={"timezone": BOX_TIMEZONE_NAME})
    return (await session.exec(stmt.returning(Box.__table__.c.id))).one()[0]


async def sync_cameras(session: AsyncSession, box_id: int) -> None:
    """Copy the box's device list into `cameras`; devices no longer on the box are soft-deleted."""
    config = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100}) or []
    now = datetime.now(timezone.utc)
    seen = []
    for device in config:
        device_id = device.get("device_id")
        if device_id is None:
            continue
        seen.append(int(device_id))
        stmt = pg_insert(Camera.__table__).values(
            box_id=box_id, device_id=int(device_id), name=device.get("device_name") or f"Device {device_id}",
            channel_type=device.get("channel_type"), last_synced_at=now)
        await session.exec(stmt.on_conflict_do_update(
            index_elements=["box_id", "device_id"],
            set_={"name": stmt.excluded.name, "channel_type": stmt.excluded.channel_type,
                  "last_synced_at": now, "deleted_at": None, "updated_at": now},
        ))
    await session.exec(
        update(Camera).where(Camera.box_id == box_id, col(Camera.device_id).not_in(seen),
                             col(Camera.deleted_at).is_(None)).values(deleted_at=now)
    )


async def camera_ids(session: AsyncSession, box_id: int, device_ids: set[int]) -> dict[int, int]:
    """device_id -> cameras.id, adding a row for a device we haven't synced yet."""
    if not device_ids:
        return {}
    stmt = pg_insert(Camera.__table__).values(
        [{"box_id": box_id, "device_id": d, "name": f"Device {d}"} for d in sorted(device_ids)])
    await session.exec(stmt.on_conflict_do_nothing(index_elements=["box_id", "device_id"]))
    rows = await session.exec(select(Camera.device_id, Camera.id).where(
        Camera.box_id == box_id, col(Camera.device_id).in_(device_ids)))
    return {device_id: camera_id for device_id, camera_id in rows.all()}


# ---------- one poll ----------

async def save_events(session: AsyncSession, box_id: int, rows: list[dict], source: EventSource,
                      received_at: datetime) -> list[Event]:
    """Insert normalized records; returns only the ones that weren't already stored."""
    if not rows:
        return []
    cameras = await camera_ids(session, box_id, {r["device_id"] for r in rows})
    values = []
    for row in rows:
        row = dict(row)
        values.append({**{k: v for k, v in row.items() if k != "device_id"},
                       "box_id": box_id, "camera_id": cameras[row["device_id"]],
                       "source": source.value, "received_at": received_at,
                       "kind": row["kind"].value})
    stmt = pg_insert(Event).on_conflict_do_nothing(index_elements=["box_id", "kind", "alarm_id"]).returning(Event)
    result = await session.exec(stmt, params=values)
    return [row[0] for row in result.all()]


async def poll_stream(sessions, box_id: int, stream: IngestStream, now: datetime | None = None) -> int:
    """Read one window of one stream. Returns how many new events were saved."""
    now = now or datetime.now(timezone.utc)
    async with sessions() as session:
        cursor = await session.get(IngestCursor, (box_id, stream.value))
        last = cursor.last_occurred_at if cursor else None

    start = (last - OVERLAP) if last else now - FIRST_LOOKBACK
    end = min(now + FUTURE_SLACK, start + MAX_WINDOW)
    read_until = min(end, now)     # the cursor never moves past this PC's clock
    try:
        records = await fetch_records(stream, start, end)
    except Exception as exc:
        await _record_failure(sessions, box_id, stream, now, exc)
        raise

    rows = [n for n in map(normalize, records) if n is not None]
    async with sessions() as session:
        async with session.begin():
            new_events = await save_events(session, box_id, rows, EventSource.POLL, now)
            await counting.attach(session, new_events, box_id)      # sightings + 15-minute buckets
            await engine.process(session, new_events, box_id)
            cursor = await session.get(IngestCursor, (box_id, stream.value)) or \
                IngestCursor(box_id=box_id, stream=stream.value)
            cursor.last_occurred_at = max(read_until, cursor.last_occurred_at or read_until)   # never backwards
            cursor.overlap_seconds = int(OVERLAP.total_seconds())
            cursor.last_run_at = cursor.last_success_at = now
            cursor.consecutive_failures = 0
            cursor.last_error = None
            cursor.events_ingested = (cursor.events_ingested or 0) + len(new_events)
            session.add(cursor)
    await _forget_dashboard_days(new_events)
    return len(new_events)


async def _forget_dashboard_days(events: list[Event]) -> None:
    """Late records change past dashboard numbers: drop their copy and the next day's copy."""
    if not events or not cache.enabled():
        return
    tz = box_tz()
    today = datetime.now(timezone.utc).astimezone(tz).date()
    keys = []
    for day in {e.occurred_at.astimezone(tz).date() for e in events}:
        for d in (day, day + timedelta(days=1)):
            if d < today or (d == today and day < today):
                keys.append(cache.key("dash", "activity", d.isoformat(), "database"))
    await cache.delete(*keys)


async def _record_failure(sessions, box_id: int, stream: IngestStream, now: datetime, exc: Exception) -> None:
    try:
        async with sessions() as session:
            async with session.begin():
                cursor = await session.get(IngestCursor, (box_id, stream.value)) or \
                    IngestCursor(box_id=box_id, stream=stream.value)
                cursor.last_run_at = now
                cursor.consecutive_failures = (cursor.consecutive_failures or 0) + 1
                cursor.last_error = f"{type(exc).__name__}: {exc}"[:1000]
                session.add(cursor)
    except Exception:  # noqa: BLE001 - don't hide the original error
        log.exception("Could not record the ingest failure")
