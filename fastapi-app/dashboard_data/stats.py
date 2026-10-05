"""Recount dashboard statistics from events after ingest writes, avoiding drift from late records."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from counting.settings import box_tz

LOW_CONFIDENCE = 70.0
LOW_LIVENESS = 80.0


def local_day_range(day: date, tz=None) -> tuple[datetime, datetime]:
    """Return [local midnight, next local midnight) in UTC, safely across DST transitions."""
    tz = tz or box_tz()
    start = datetime.combine(day, time(0), tz)
    end = datetime.combine(day + timedelta(days=1), time(0), tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


_REBUILD_DAY = text("""
WITH e AS (
    SELECT kind, person_uuid, person_name,
           CASE WHEN coalesce(face_track_id, body_track_id) IS NOT NULL
                THEN camera_id::text || ':' || coalesce(face_track_id, body_track_id)::text
                ELSE kind || ':' || camera_id::text || ':' || alarm_id::text END AS track_key
    FROM events
    WHERE box_id = :box_id AND occurred_at >= :start AND occurred_at < :end
), k AS (
    SELECT count(DISTINCT track_key) FILTER (WHERE kind IN ('face_capture', 'body_capture')) AS tracked,
           count(DISTINCT track_key) FILTER (WHERE kind = 'face_capture') AS face,
           count(DISTINCT track_key) FILTER (WHERE kind = 'body_capture') AS body,
           count(DISTINCT track_key) FILTER (WHERE kind = 'matched') AS recognized,
           count(DISTINCT track_key) FILTER (WHERE kind = 'stranger') AS stranger,
           count(DISTINCT coalesce(person_uuid, nullif(lower(btrim(person_name)), '')))
               FILTER (WHERE kind = 'matched') AS people
    FROM e
), j AS (
    SELECT count(*) AS n FROM (
        SELECT track_key FROM e WHERE kind = 'matched'
        INTERSECT
        SELECT track_key FROM e WHERE kind = 'face_capture'
    ) x
)
INSERT INTO daily_stats (box_id, local_date, tracked_encounters, face_encounters, body_encounters,
                         recognized_encounters, stranger_encounters, unique_recognized_people,
                         recognized_capture_tracks, updated_at)
SELECT :box_id, :local_date, k.tracked, k.face, k.body, k.recognized, k.stranger, k.people, j.n, now()
FROM k, j
ON CONFLICT (box_id, local_date) DO UPDATE SET
    tracked_encounters = excluded.tracked_encounters, face_encounters = excluded.face_encounters,
    body_encounters = excluded.body_encounters, recognized_encounters = excluded.recognized_encounters,
    stranger_encounters = excluded.stranger_encounters,
    unique_recognized_people = excluded.unique_recognized_people,
    recognized_capture_tracks = excluded.recognized_capture_tracks, updated_at = excluded.updated_at
""")


async def rebuild_days(session: AsyncSession, box_id: int, days: set[date]) -> None:
    """Recount daily_stats for these box-local days from events (upsert)."""
    for day in sorted(days):
        start, end = local_day_range(day)
        # Track keys mirror the dashboard's box-mode encounter keys. Records without tracks use a
        # per-kind record key, so they never intersect across kinds.
        await session.exec(_REBUILD_DAY, params={
            "box_id": box_id, "local_date": day, "start": start, "end": end,
        })
