"""Alarm emails: SMTP settings, building the message, and the queue worker that sends `notifications`.

Settings come from .env (never the database):
  SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM (defaults to SMTP_USER),
  SMTP_FROM_NAME ("B4H Portal"), SMTP_SECURITY (starttls | ssl | none), PORTAL_URL (for links).

Queue: rows are claimed in a short transaction (FOR UPDATE SKIP LOCKED, status 'sending', a 2-minute
lease), the transaction commits, and only then is the SMTP server contacted, so no database
connection is held during a slow send. A row whose lease runs out is claimed again.
"""
import asyncio
import html
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from zoneinfo import ZoneInfo

from sqlalchemy import text

from models import Camera, Event, Incident, Notification, NotificationStatus

log = logging.getLogger("b4h.mail")

CLAIM_BATCH = 20
LEASE = timedelta(minutes=2)
FIRST_RETRY = timedelta(seconds=30)
MAX_RETRY_GAP = timedelta(minutes=30)
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    sender_name: str
    security: str          # starttls | ssl | none
    portal_url: str

    @classmethod
    def from_env(cls) -> "SmtpConfig":
        security = os.getenv("SMTP_SECURITY", "starttls").lower()
        return cls(
            host=os.getenv("SMTP_HOST", ""),
            port=int(os.getenv("SMTP_PORT", "465" if security == "ssl" else "587")),
            user=os.getenv("SMTP_USER", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            sender=os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", ""),
            sender_name=os.getenv("SMTP_FROM_NAME", "B4H Portal"),
            security=security,
            portal_url=os.getenv("PORTAL_URL", "http://localhost:3000").rstrip("/"),
        )

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)


# ---------- message ----------

def who(incident: Incident) -> str:
    if incident.person_name:
        return incident.person_name
    return "A stranger" if incident.is_stranger else "Someone"


def subject_for(incident: Incident, camera_name: str, tz: ZoneInfo) -> str:
    local = incident.occurred_at.astimezone(tz)
    return f"[{str(incident.severity).upper()}] {incident.rule_name}: {who(incident)} on {camera_name} " \
           f"at {local:%H:%M} ({local:%Y-%m-%d})"


def build_message(cfg: SmtpConfig, to: str, subject: str, incident: Incident, camera_name: str,
                  images: list[tuple[str, bytes, str]]) -> EmailMessage:
    tz = ZoneInfo((incident.rule_snapshot or {}).get("timezone") or "UTC")
    local = incident.occurred_at.astimezone(tz)
    link = f"{cfg.portal_url}/alarms/{incident.public_id}"
    rows = [
        ("Rule", incident.rule_name),
        ("Severity", str(incident.severity).capitalize()),
        ("Camera", camera_name),
        ("Time", f"{local:%Y-%m-%d %H:%M:%S} ({tz.key})"),
        ("Who", who(incident)),
    ]
    if incident.track_id:
        rows.append(("Track ID", str(incident.track_id)))
    if incident.is_delayed:
        rows.append(("Note", f"Reported {incident.delay_seconds // 60} min late (the portal was catching up)"))

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg.sender_name, cfg.sender))
    msg["To"] = to
    msg["Message-ID"] = make_msgid(domain=cfg.sender.split("@")[-1] or None)
    msg.set_content("\n".join(f"{k}: {v}" for k, v in rows) + f"\n\nOpen the alarm: {link}\n")
    table = "".join(f"<tr><td style='padding:4px 12px 4px 0;color:#64748b'>{html.escape(k)}</td>"
                    f"<td style='padding:4px 0'><b>{html.escape(v)}</b></td></tr>" for k, v in rows)
    msg.add_alternative(
        f"<div style='font-family:Arial,sans-serif;font-size:14px'>"
        f"<h2 style='margin:0 0 12px'>{html.escape(incident.rule_name)}</h2><table>{table}</table>"
        f"<p><a href='{html.escape(link)}'>Open the alarm in the portal</a></p></div>",
        subtype="html",
    )
    for name, data, mime in images:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype or "image", subtype=subtype or "jpeg", filename=name)
    return msg


def build_test_message(cfg: SmtpConfig, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "B4H Portal: test email"
    msg["From"] = formataddr((cfg.sender_name, cfg.sender))
    msg["To"] = to
    msg.set_content("This is a test email from the B4H Portal. Alarm emails will look like they come from here.")
    return msg


def _send_sync(cfg: SmtpConfig, msg: EmailMessage) -> None:
    context = ssl.create_default_context()
    if cfg.security == "ssl":
        smtp = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=30, context=context)
    else:
        smtp = smtplib.SMTP(cfg.host, cfg.port, timeout=30)
    with smtp:
        if cfg.security == "starttls":
            smtp.starttls(context=context)
        if cfg.user:
            smtp.login(cfg.user, cfg.password)
        smtp.send_message(msg)


async def send(cfg: SmtpConfig, msg: EmailMessage) -> None:
    """smtplib blocks, so it runs in a thread."""
    await asyncio.to_thread(_send_sync, cfg, msg)


# ---------- snapshot images from the box ----------

def _is_image(data: bytes, content_type: str) -> bool:
    if content_type.startswith("image/"):
        return True
    return data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"


async def fetch_image(box, path: str | None) -> tuple[bytes, str] | None:
    """Image bytes from the box, or None (missing, rotated out, box offline). Never raises."""
    if not path:
        return None
    try:
        data, content_type = await box.get_bytes("/device_storage/get_image", {"image_uri": path})
    except Exception as exc:  # noqa: BLE001 - an email without a picture is better than no email
        log.info("Snapshot %s not attached: %r", path, exc)
        return None
    if not data or len(data) > MAX_ATTACHMENT_BYTES or not _is_image(data, content_type or ""):
        return None
    return data, content_type if content_type.startswith("image/") else "image/jpeg"


async def incident_images(box, incident: Incident, event: Event | None) -> list[tuple[str, bytes, str]]:
    out = []
    paths = [("snapshot", incident.snapshot_path)]
    if event is not None and event.panorama_path and event.panorama_path != incident.snapshot_path:
        paths.append(("panorama", event.panorama_path))
    for name, path in paths:
        image = await fetch_image(box, path)
        if image:
            data, mime = image
            out.append((f"{name}.{'png' if mime.endswith('png') else 'jpg'}", data, mime))
    return out


# ---------- queue ----------

def retry_gap(attempts: int) -> timedelta:
    """30 s, 1 min, 2 min, ... capped at 30 min."""
    return min(FIRST_RETRY * (2 ** max(0, attempts - 1)), MAX_RETRY_GAP)


_CLAIM = text("""
    UPDATE notifications
       SET status = 'sending', attempts = attempts + 1, locked_until = now() + make_interval(secs => :lease)
     WHERE id IN (
           SELECT id FROM notifications
            WHERE attempts < max_attempts
              AND ((status = 'pending' AND next_attempt_at <= now())
                   OR (status = 'sending' AND locked_until < now()))
            ORDER BY next_attempt_at
            LIMIT :batch
            FOR UPDATE SKIP LOCKED)
 RETURNING id
""")

_GIVE_UP_STALE = text("""
    UPDATE notifications
       SET status = 'failed', locked_until = NULL, last_error = coalesce(last_error, 'Gave up: no answer from the sender')
     WHERE status = 'sending' AND locked_until < now() AND attempts >= max_attempts
""")


async def claim(sessions) -> list[int]:
    async with sessions() as session:
        async with session.begin():
            await session.exec(_GIVE_UP_STALE)
            result = await session.exec(_CLAIM, params={"lease": LEASE.total_seconds(), "batch": CLAIM_BATCH})
            return [row[0] for row in result.all()]


async def deliver(sessions, box, cfg: SmtpConfig, notification_id: int, image_cache: dict) -> bool:
    """Send one claimed notification and record the outcome. Returns True when sent."""
    async with sessions() as session:
        n = await session.get(Notification, notification_id)
        if n is None or n.status != NotificationStatus.SENDING:
            return False
        incident = await session.get(Incident, n.incident_id)
        camera = await session.get(Camera, incident.camera_id) if incident else None
        event = await session.get(Event, incident.trigger_event_id) if incident and incident.trigger_event_id else None

    error = None
    if incident is None:
        error = "The incident no longer exists"
    else:
        try:
            if (incident.rule_snapshot or {}).get("attach_snapshot", True):
                if incident.id not in image_cache:
                    image_cache[incident.id] = await incident_images(box, incident, event)
                images = image_cache[incident.id]
            else:
                images = []
            camera_name = camera.name if camera else f"Camera {incident.camera_id}"
            msg = build_message(cfg, n.to_address, n.subject or incident.rule_name, incident, camera_name, images)
            await send(cfg, msg)
        except Exception as exc:  # noqa: BLE001 - every failure is recorded on the row and retried
            error = f"{type(exc).__name__}: {exc}"[:1000]

    now = datetime.now(timezone.utc)
    async with sessions() as session:
        async with session.begin():
            n = await session.get(Notification, notification_id)
            if n is None:
                return False
            n.locked_until = None
            if error is None:
                n.status, n.sent_at, n.last_error = NotificationStatus.SENT, now, None
            elif n.attempts >= n.max_attempts:
                n.status, n.last_error = NotificationStatus.FAILED, error
            else:
                n.status, n.last_error = NotificationStatus.PENDING, error
                n.next_attempt_at = now + retry_gap(n.attempts)
            session.add(n)
    if error:
        log.warning("Alarm email %s to %s failed (attempt %s): %s", notification_id, n.to_address, n.attempts, error)
    return error is None


async def run_once(sessions, box, cfg: SmtpConfig) -> int:
    """Send everything that's due. Returns how many were sent."""
    ids = await claim(sessions)
    cache: dict = {}
    sent = 0
    for notification_id in ids:
        sent += await deliver(sessions, box, cfg, notification_id, cache)
    return sent
