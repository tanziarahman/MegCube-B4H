"""Rebuild dashboard bucket and day totals for existing events.

The rebuild is idempotent and safe to run while polling: each local day is rebuilt in its own
transaction, so stopping halfway leaves earlier days complete and later days ready to retry.
"""
import argparse
import asyncio
from datetime import date, datetime, timedelta

import cache
import db
from counting.builder import rebuild_buckets
from counting.settings import box_tz
from dashboard_data.stats import local_day_range, rebuild_days
from sqlalchemy import text


async def run(sessions, since: date | None = None, quiet: bool = True) -> int:
    """Rebuild all dashboard rows and return the number of local days processed."""
    tz = box_tz()
    async with sessions() as session:
        boxes = [row[0] for row in (await session.exec(text("SELECT id FROM boxes ORDER BY id"))).all()]
    processed = 0
    for box_id in boxes:
        async with sessions() as session:
            bounds = (await session.exec(text(
                "SELECT min(occurred_at), max(occurred_at) FROM events WHERE box_id = :box_id"),
                params={"box_id": box_id})).first()
        if not bounds or bounds[0] is None:
            continue
        first = bounds[0].astimezone(tz).date()
        last = bounds[1].astimezone(tz).date()
        if since:
            first = max(first, since)
        day = first
        while day <= last:
            start, end = local_day_range(day, tz)
            async with sessions() as session:
                async with session.begin():
                    event_rows = (await session.exec(text("""
                        SELECT DISTINCT camera_id,
                               date_bin('15 minutes', occurred_at,
                                        TIMESTAMPTZ '2000-01-01 00:00:00+00')
                        FROM events
                        WHERE box_id = :box_id AND occurred_at >= :start AND occurred_at < :end
                    """), params={"box_id": box_id, "start": start, "end": end})).all()
                    old_rows = (await session.exec(text("""
                        SELECT cb.camera_id, cb.bucket_start
                        FROM count_buckets cb
                        JOIN cameras c ON c.id = cb.camera_id
                        WHERE c.box_id = :box_id AND cb.local_date = :day
                    """), params={"box_id": box_id, "day": day})).all()
                    touched = {(int(row[0]), row[1]) for row in [*event_rows, *old_rows]}
                    await rebuild_buckets(session, touched, tz)
                    await rebuild_days(session, box_id, {day})
            processed += 1
            if not quiet:
                print(f"{day}: {len(touched)} buckets, daily stats rebuilt", flush=True)
            day += timedelta(days=1)
    await cache.delete_prefix(cache.key("dash", ""))
    return processed


async def _main(since: date | None) -> None:
    if not db.DATABASE_URL:
        raise SystemExit("Set DATABASE_URL in fastapi-app/.env first")
    engine = db.make_engine(db.DATABASE_URL, null_pool=True)
    db.configure(engine)
    try:
        total = await run(db.sessions(), since, quiet=False)
        print(f"Done: {total} local days rebuilt")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild dashboard bucket and daily statistics.")
    parser.add_argument("--since", type=date.fromisoformat, help="only local days from YYYY-MM-DD")
    asyncio.run(_main(parser.parse_args().since))
