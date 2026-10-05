"""Small sequential PostgreSQL queries for the database-backed dashboard."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

import core
from dashboard_data.stats import local_day_range
from models import DailyStat, EventKind
from counting.settings import box_tz


async def coverage(session: AsyncSession) -> dict:
    """Return the box id and first fully covered local day for the dashboard."""
    box_row = (await session.exec(
        text("SELECT id FROM boxes WHERE base_url = :base_url"),
        params={"base_url": core.BOX_BASE_URL},
    )).first()
    if box_row is None:
        return {"box_id": None, "start": None}
    box_id = box_row[0]
    row = (await session.exec(text("""
        SELECT min(cb.local_date)
        FROM count_buckets cb
        JOIN cameras c ON c.id = cb.camera_id
        WHERE c.box_id = :box_id
    """), params={"box_id": box_id})).first()
    first = row[0] if row and row[0] is not None else None
    return {"box_id": box_id, "start": (first + timedelta(days=1)).isoformat() if first else None}


async def activity(
    session: AsyncSession,
    box_id: int,
    day: date,
    *,
    with_previous: bool,
    now: datetime | None = None,
) -> dict:
    """Return additive bucket totals, distinct day totals, recent events and people for one day."""
    start, end = local_day_range(day)
    kinds = {name: member.value for name, member in (
        ("matched", EventKind.MATCHED), ("stranger", EventKind.STRANGER),
        ("face_capture", EventKind.FACE_CAPTURE), ("body_capture", EventKind.BODY_CAPTURE),
    )}
    camera_rows = (await session.exec(text("""
        SELECT c.id, c.device_id, c.name,
               coalesce(sum(cb.matched_events), 0), coalesce(sum(cb.stranger_events), 0),
               coalesce(sum(cb.face_capture_events), 0), coalesce(sum(cb.body_capture_events), 0),
               coalesce(sum(cb.low_confidence_events), 0), coalesce(sum(cb.low_liveness_events), 0),
               coalesce(sum(cb.identity_score_sum), 0), coalesce(sum(cb.identity_score_count), 0)
        FROM count_buckets cb
        JOIN cameras c ON c.id = cb.camera_id
        WHERE c.box_id = :box_id AND cb.local_date = :day
        GROUP BY c.id, c.device_id, c.name
    """), params={"box_id": box_id, "day": day})).all()
    hour_rows = (await session.exec(text("""
        SELECT local_hour, coalesce(sum(matched_events + stranger_events), 0)
        FROM count_buckets cb
        JOIN cameras c ON c.id = cb.camera_id
        WHERE c.box_id = :box_id AND cb.local_date = :day
        GROUP BY local_hour
    """), params={"box_id": box_id, "day": day})).all()

    previous = {}
    if with_previous:
        previous_day = day - timedelta(days=1)
        previous_rows = (await session.exec(text("""
            SELECT coalesce(sum(matched_events), 0), coalesce(sum(stranger_events), 0),
                   coalesce(sum(face_capture_events + body_capture_events), 0)
            FROM count_buckets cb
            JOIN cameras c ON c.id = cb.camera_id
            WHERE c.box_id = :box_id AND cb.local_date = :day
        """), params={"box_id": box_id, "day": previous_day})).first()
        previous = {
            "previous_matched": int(previous_rows[0]),
            "previous_strangers": int(previous_rows[1]),
            "previous_captures": int(previous_rows[2]),
        }

    daily = await session.get(DailyStat, (box_id, day))
    distincts = {
        "tracked_encounters": daily.tracked_encounters if daily else 0,
        "face_encounters": daily.face_encounters if daily else 0,
        "body_encounters": daily.body_encounters if daily else 0,
        "unique_recognized_people": daily.unique_recognized_people if daily else 0,
        "recognized_encounters": daily.recognized_encounters if daily else 0,
        "stranger_encounters": daily.stranger_encounters if daily else 0,
        "recognized_capture_tracks": daily.recognized_capture_tracks if daily else 0,
    }
    event_rows = (await session.exec(text("""
        SELECT e.alarm_id, e.kind, e.person_name, e.occurred_at, e.match_score, c.device_id, c.name
        FROM events e
        JOIN cameras c ON c.id = e.camera_id
        WHERE e.box_id = :box_id AND e.kind IN (:matched, :stranger)
          AND e.occurred_at >= :start AND e.occurred_at < :end
        ORDER BY e.occurred_at DESC, e.id DESC
        LIMIT 8
    """), params={"box_id": box_id, "matched": kinds["matched"], "stranger": kinds["stranger"],
                  "start": start, "end": end})).all()
    people_rows = (await session.exec(text("""
        SELECT person_name, count(*)
        FROM events
        WHERE box_id = :box_id AND kind = :matched AND person_name IS NOT NULL
          AND btrim(person_name) <> '' AND occurred_at >= :start AND occurred_at < :end
        GROUP BY person_name
        ORDER BY count(*) DESC, person_name
        LIMIT 5
    """), params={"box_id": box_id, "matched": kinds["matched"], "start": start, "end": end})).all()

    matched = sum(int(row[3]) for row in camera_rows)
    strangers = sum(int(row[4]) for row in camera_rows)
    face_captures = sum(int(row[5]) for row in camera_rows)
    body_captures = sum(int(row[6]) for row in camera_rows)
    scores = sum(float(row[9]) for row in camera_rows)
    score_count = sum(int(row[10]) for row in camera_rows)
    hours = {int(row[0]): int(row[1]) for row in hour_rows}
    identity_by_camera = sorted(
        ((int(row[1]), str(row[2]), int(row[3]) + int(row[4])) for row in camera_rows if int(row[3]) + int(row[4]) > 0),
        key=lambda row: (-row[2], row[0]),
    )
    capture_by_camera = sorted(
        ((int(row[1]), str(row[2]), int(row[5]) + int(row[6])) for row in camera_rows if int(row[5]) + int(row[6]) > 0),
        key=lambda row: (-row[2], row[0]),
    )
    peak = next((hour for hour in range(24) if hours.get(hour, 0) == max(hours.values(), default=0)
                 and hours.get(hour, 0) > 0), None)
    activity_data = {
        "matched": matched, "strangers": strangers, "captures": face_captures + body_captures,
        "face_captures": face_captures, "body_captures": body_captures,
        "capture_breakdown_limited": False, **previous,
    }
    insights = {
        "peak_hour": peak,
        "busiest_device_id": identity_by_camera[0][0] if identity_by_camera else None,
        "busiest_device": identity_by_camera[0][1] if identity_by_camera else None,
        "average_match_score": round(scores / score_count, 1) if score_count else None,
        "low_confidence_count": sum(int(row[7]) for row in camera_rows),
        "low_liveness_count": sum(int(row[8]) for row in camera_rows),
        "top_people": [{"name": row[0], "count": int(row[1])} for row in people_rows],
        "hourly_activity": [{"hour": hour, "count": hours.get(hour, 0)} for hour in range(24)],
        "events": [{
            "id": str(row[0]), "type": row[1], "person": row[2],
            "device_id": str(row[5]), "device": row[6],
            "time_ms": int(row[3].timestamp() * 1000),
            "score": round(float(row[4]), 1) if row[4] is not None else None,
        } for row in event_rows],
        **distincts,
        "recognition_coverage_percent": round(
            distincts["recognized_capture_tracks"] / distincts["face_encounters"] * 100, 1)
        if distincts["face_encounters"] else None,
        "busiest_capture_device": capture_by_camera[0][1] if capture_by_camera else None,
        "analysis_sampled": matched + strangers + face_captures + body_captures,
        "analysis_limited": False,
    }

    tz = box_tz()
    current = now or datetime.now(timezone.utc)
    today = current.astimezone(tz).date()
    ingest = None
    if day == today:
        row = (await session.exec(text(
            "SELECT min(last_success_at) FROM ingest_cursors WHERE box_id = :box_id"),
            params={"box_id": box_id})).first()
        last = row[0] if row else None
        ingest = {
            "last_success_at": last.isoformat() if last else None,
            "lag_seconds": int((current - last).total_seconds()) if last else None,
        }
    return {"activity": activity_data, "insights": insights, "ingest": ingest}
