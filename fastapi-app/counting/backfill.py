"""Builds sightings for events saved before people counting existed (events.sighting_id IS NULL).

Run from fastapi-app/ (uses DATABASE_URL from .env):
    uv run python -m counting.backfill [--since YYYY-MM-DD]

Safe to re-run: events that already have a sighting are skipped. Each batch is its own transaction,
so stopping it halfway keeps what's done. It can run while the backend is polling; if both touch the
same sighting at once, one transaction fails on the unique track index and is simply retried later.
"""
import argparse
import asyncio
from datetime import date, datetime, time

from sqlalchemy import or_, tuple_
from sqlmodel import col, select

import db
from models import Event

from .builder import attach
from .settings import box_tz

BATCH_SIZE = 500


async def run(sessions, since: date | None = None, batch_size: int = BATCH_SIZE, quiet: bool = False) -> int:
    """Attach every event that has a track but no sighting, oldest first. Returns how many."""
    start = datetime.combine(since, time(0), box_tz()) if since else None
    after: tuple | None = None          # (box_id, occurred_at, id) of the last event handled
    done = 0
    while True:
        async with sessions() as session:
            async with session.begin():
                stmt = select(Event).where(
                    col(Event.sighting_id).is_(None),
                    or_(col(Event.face_track_id).is_not(None), col(Event.body_track_id).is_not(None)))
                if start is not None:
                    stmt = stmt.where(Event.occurred_at >= start)
                if after is not None:
                    stmt = stmt.where(tuple_(Event.box_id, Event.occurred_at, Event.id) > after)
                stmt = stmt.order_by(Event.box_id, Event.occurred_at, Event.id).limit(batch_size)
                events = list((await session.exec(stmt)).all())
                if not events:
                    return done
                after = (events[-1].box_id, events[-1].occurred_at, events[-1].id)
                for box_id in sorted({e.box_id for e in events}):
                    await attach(session, [e for e in events if e.box_id == box_id], box_id)
        done += len(events)
        if not quiet:
            print(f"{done} events counted (up to {after[1].astimezone(box_tz()):%Y-%m-%d %H:%M:%S})", flush=True)


async def _main(since: date | None) -> None:
    if not db.DATABASE_URL:
        raise SystemExit("Set DATABASE_URL in fastapi-app/.env first")
    engine = db.make_engine(db.DATABASE_URL, null_pool=True)
    db.configure(engine)
    try:
        total = await run(db.sessions(), since)
        print(f"Done: {total} events attached to sightings")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build sightings for events saved before people counting.")
    parser.add_argument("--since", type=date.fromisoformat, help="only events from this box-local day (YYYY-MM-DD)")
    asyncio.run(_main(parser.parse_args().since))
