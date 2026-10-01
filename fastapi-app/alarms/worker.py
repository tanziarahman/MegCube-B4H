"""Background loops started with the app: box polling (ingest + rules) and the email sender.

They run inside the FastAPI process, so run the backend as ONE process (no `--workers N`).
Turned on when DATABASE_URL is set; ALARM_WORKERS=0 turns them off (e.g. a second instance).
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import db
from core import box
from models import IngestStream

from . import ingest, mailer

log = logging.getLogger("b4h.alarms")

POLL_SECONDS = float(os.getenv("ALARM_POLL_SECONDS", "5"))
MAIL_POLL_SECONDS = 5.0
CAMERA_SYNC_EVERY = timedelta(minutes=10)
MAX_BACKOFF_SECONDS = 60.0

# Shown by GET /api/alarms/status.
state: dict = {
    "ingest": {"running": False, "last_ok": None, "last_error": None},
    "mailer": {"running": False, "last_ok": None, "last_error": None},
}
_tasks: list[asyncio.Task] = []


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def ingest_loop() -> None:
    sessions = db.sessions()
    box_id = None
    synced_at = None
    failures = 0
    state["ingest"]["running"] = True
    while True:
        try:
            async with sessions() as session:
                async with session.begin():
                    if box_id is None:
                        box_id = await ingest.ensure_box(session)
                    if synced_at is None or _now() - synced_at > CAMERA_SYNC_EVERY:
                        await ingest.sync_cameras(session, box_id)
                        synced_at = _now()
            for stream in IngestStream:
                await ingest.poll_stream(sessions, box_id, stream)
            failures = 0
            state["ingest"].update(last_ok=_now().isoformat(), last_error=None)
            await asyncio.sleep(POLL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep polling; the box may just be rebooting
            failures += 1
            state["ingest"]["last_error"] = f"{type(exc).__name__}: {exc}"[:500]
            delay = min(MAX_BACKOFF_SECONDS, POLL_SECONDS * 2 ** min(failures, 6))
            log.warning("Alarm polling failed (%s in a row), retrying in %.0f s: %r", failures, delay, exc)
            await asyncio.sleep(delay)


async def mail_loop() -> None:
    sessions = db.sessions()
    cfg = mailer.SmtpConfig.from_env()
    state["mailer"]["running"] = True
    if not cfg.configured:
        log.warning("SMTP_HOST / SMTP_FROM aren't set: alarm emails stay queued until they are")
    while True:
        try:
            if cfg.configured:
                await mailer.run_once(sessions, box, cfg)
                state["mailer"].update(last_ok=_now().isoformat(), last_error=None)
            await asyncio.sleep(MAIL_POLL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            state["mailer"]["last_error"] = f"{type(exc).__name__}: {exc}"[:500]
            log.warning("Alarm email loop failed: %r", exc)
            await asyncio.sleep(MAX_BACKOFF_SECONDS)


def start() -> None:
    if not db.enabled():
        log.info("DATABASE_URL isn't set: alarms are off")
        return
    if os.getenv("ALARM_WORKERS", "1") == "0":
        log.info("ALARM_WORKERS=0: alarm polling and emails are off in this process")
        return
    _tasks.extend([asyncio.create_task(ingest_loop(), name="alarm-ingest"),
                   asyncio.create_task(mail_loop(), name="alarm-mail")])
    log.info("Alarm workers started (polling every %.0f s)", POLL_SECONDS)


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
    for part in state.values():
        part["running"] = False
