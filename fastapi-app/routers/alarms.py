"""Alarms: rules, email recipients, incidents, and the status of the background workers.

Stored in our database (DATABASE_URL), not on the box. The box only supplies the records the rules
are checked against (see alarms/ingest.py).
"""
import os
import uuid
from datetime import datetime, time, timezone
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import db
from alarms import ingest, mailer, worker
from alarms.rules import plain
from core import BOX_TIMEZONE_NAME, log, to_ms
from models import (AlarmRule, AlarmRuleCamera, AlarmRuleRecipient, AlarmRuleState, AlarmRuleTarget,
                    AlarmRuleWindow, AuditLog, Camera, Contact, DedupeScope, Event, EventKind, Incident,
                    IncidentEvent, IncidentStatus, IngestCursor, MatchMode, Notification, NotificationStatus,
                    Severity, TargetType)

router = APIRouter()

MAX_RECIPIENTS = int(os.getenv("ALARM_MAX_RECIPIENTS", "5"))
MAX_DAY_SECONDS = 24 * 3600
Session = Annotated[AsyncSession, Depends(db.get_session)]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dump(value):
    """Enum members -> values, recursively (for audit snapshots)."""
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if isinstance(value, (datetime, time)):
        return value.isoformat()
    return plain(value)


def _audit(session: AsyncSession, action: str, entity_type: str, entity_id, before=None, after=None,
           actor: str | None = None) -> None:
    session.add(AuditLog(actor=actor or "portal", action=action, entity_type=entity_type,
                         entity_id=str(entity_id), before=_dump(before), after=_dump(after)))


_box_id: int | None = None


async def _get_box_id(session: AsyncSession) -> int:
    global _box_id
    if _box_id is None:
        _box_id = await ingest.ensure_box(session)
        await session.commit()
    return _box_id


# =====================================================================
# Status
# =====================================================================

@router.get("/api/alarms/status")
async def alarms_status():
    """Is everything running? Also the open-incident count for the sidebar badge.
    Answers even without a database (database: false), so the page can explain what's missing."""
    cfg = mailer.SmtpConfig.from_env()
    out = {
        "database": db.enabled(),
        "workers": worker.state,
        "smtp": {"configured": cfg.configured, "host": cfg.host or None, "sender": cfg.sender or None},
        "timezone": BOX_TIMEZONE_NAME,
        "max_recipients": MAX_RECIPIENTS,
        "ingest": [],
        "open_incidents": 0,
        "notifications": {"pending": 0, "failed": 0},
    }
    if not db.enabled():
        return out
    async with db.sessions()() as session:
        cursors = (await session.exec(select(IngestCursor))).all()
        out["ingest"] = [{
            "stream": c.stream, "read_until": c.last_occurred_at, "last_success_at": c.last_success_at,
            "consecutive_failures": c.consecutive_failures, "last_error": c.last_error,
            "events_ingested": c.events_ingested,
        } for c in cursors]
        out["open_incidents"] = (await session.exec(
            select(func.count()).select_from(Incident).where(Incident.status == IncidentStatus.OPEN.value))).one()
        counts = (await session.exec(
            select(Notification.status, func.count()).where(
                col(Notification.status).in_([NotificationStatus.PENDING.value, NotificationStatus.FAILED.value])
            ).group_by(Notification.status))).all()
        out["notifications"].update({status: n for status, n in counts})
    return out


# =====================================================================
# Cameras (copied from the box)
# =====================================================================

def _camera_out(c: Camera) -> dict:
    return {"id": c.id, "device_id": c.device_id, "name": c.name, "deleted": c.deleted_at is not None}


@router.get("/api/alarms/cameras")
async def alarm_cameras(session: Session):
    """Cameras rules can watch. Refreshed from the box first; if the box is unreachable,
    the last copy is returned."""
    box_id = await _get_box_id(session)
    try:
        await ingest.sync_cameras(session, box_id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001 - the stored list is still useful
        await session.rollback()
        log.warning("Camera sync failed, showing the stored list: %r", exc)
    cameras = (await session.exec(select(Camera).where(Camera.box_id == box_id).order_by(Camera.device_id))).all()
    return [_camera_out(c) for c in cameras]


# =====================================================================
# Contacts (email recipients)
# =====================================================================

class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name can't be blank")
        return v.strip()


def _contact_out(c: Contact, rule_count: int = 0) -> dict:
    return {"id": c.id, "name": c.name, "email": c.email, "is_active": c.is_active, "rule_count": rule_count}


@router.get("/api/alarms/contacts")
async def list_contacts(session: Session):
    counts = dict((await session.exec(
        select(AlarmRuleRecipient.contact_id, func.count()).group_by(AlarmRuleRecipient.contact_id))).all())
    contacts = (await session.exec(select(Contact).order_by(Contact.name))).all()
    return [_contact_out(c, counts.get(c.id, 0)) for c in contacts]


async def _flush_or_409(session: AsyncSession, message: str) -> None:
    """Write pending changes; a unique-key clash becomes 409 with `message`."""
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, message)


@router.post("/api/alarms/contacts", status_code=201)
async def create_contact(body: ContactIn, session: Session):
    contact = Contact(name=body.name, email=body.email.lower(), is_active=body.is_active)
    session.add(contact)
    await _flush_or_409(session, f"A recipient with the email {contact.email} already exists")
    _audit(session, "create", "contact", contact.id, after=_contact_out(contact))
    await session.commit()
    return _contact_out(contact)


@router.put("/api/alarms/contacts/{contact_id}")
async def update_contact(body: ContactIn, session: Session, contact_id: int = Path(..., ge=1)):
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(404, f"Recipient #{contact_id} doesn't exist")
    before = _contact_out(contact)
    contact.name, contact.email, contact.is_active = body.name, body.email.lower(), body.is_active
    contact.updated_at = _now()
    session.add(contact)
    await _flush_or_409(session, f"A recipient with the email {contact.email} already exists")
    _audit(session, "update", "contact", contact_id, before=before, after=_contact_out(contact))
    await session.commit()
    return _contact_out(contact)


@router.delete("/api/alarms/contacts/{contact_id}")
async def delete_contact(session: Session, contact_id: int = Path(..., ge=1)):
    """Also removes them from every rule. Emails already sent keep their address."""
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(404, f"Recipient #{contact_id} doesn't exist")
    _audit(session, "delete", "contact", contact_id, before=_contact_out(contact))
    await session.delete(contact)
    await session.commit()
    return {"deleted": contact_id}


@router.post("/api/alarms/test-email")
async def test_email(body: dict):
    """Send a test email now (not through the queue), to check the SMTP settings."""
    try:
        to = ContactIn(name="test", email=body.get("to", "")).email
    except ValueError:
        raise HTTPException(422, "Enter a valid email address")
    cfg = mailer.SmtpConfig.from_env()
    if not cfg.configured:
        raise HTTPException(409, "Email isn't set up: set SMTP_HOST and SMTP_FROM in fastapi-app/.env")
    try:
        await mailer.send(cfg, mailer.build_test_message(cfg, to))
    except Exception as exc:  # noqa: BLE001 - show the SMTP server's own message
        raise HTTPException(502, f"The email server refused: {type(exc).__name__}: {exc}")
    return {"sent_to": to}


# =====================================================================
# Rules
# =====================================================================

class WindowIn(BaseModel):
    iso_dow: int = Field(ge=1, le=7)          # 1 = Monday
    start: time
    end: time                                 # end < start: runs past midnight

    @model_validator(mode="after")
    def _not_empty(self):
        if self.start == self.end:
            raise ValueError("A time window can't start and end at the same time")
        return self


class TargetIn(BaseModel):
    type: TargetType
    value: str = Field(min_length=1, max_length=64)     # box person_id or group_id
    label: str | None = Field(None, max_length=200)


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    is_enabled: bool = True
    severity: Severity = Severity.WARNING
    event_kinds: list[EventKind] = Field(min_length=1)
    match_mode: MatchMode = MatchMode.ANYONE
    min_match_score: float | None = Field(None, ge=0, le=100)
    min_liveness: float | None = Field(None, ge=0, le=100)
    timezone: str = BOX_TIMEZONE_NAME
    cooldown_seconds: int = Field(300, ge=0, le=MAX_DAY_SECONDS)
    dedupe_scope: DedupeScope = DedupeScope.CAMERA
    max_delay_seconds: int = Field(300, ge=0, le=MAX_DAY_SECONDS)
    email_delayed: bool = False
    attach_snapshot: bool = True
    camera_ids: list[int] = Field(min_length=1)
    windows: list[WindowIn] = Field(default_factory=list, max_length=100)
    targets: list[TargetIn] = Field(default_factory=list, max_length=500)
    recipient_ids: list[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name can't be blank")
        return v.strip()

    @field_validator("timezone")
    @classmethod
    def _zone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"Unknown time zone '{v}'")
        return v

    @model_validator(mode="after")
    def _consistent(self):
        kinds = {plain(k) for k in self.event_kinds}
        if len(kinds) != len(self.event_kinds):
            raise ValueError("event_kinds has duplicates")
        if self.match_mode == MatchMode.STRANGERS and EventKind.STRANGER.value not in kinds:
            raise ValueError("'Strangers only' needs the 'stranger' event kind")
        if self.match_mode in (MatchMode.KNOWN, MatchMode.TARGETS) and EventKind.MATCHED.value not in kinds:
            raise ValueError("Rules about known people need the 'matched' event kind")
        if self.match_mode == MatchMode.TARGETS and not self.targets:
            raise ValueError("Pick at least one person or group")
        if len(set(self.recipient_ids)) > MAX_RECIPIENTS:
            raise ValueError(f"At most {MAX_RECIPIENTS} recipients per rule")
        return self


class RuleUpdate(RuleIn):
    version: int = Field(ge=1)                # the version you edited; a newer one on the server -> 409


class EnabledIn(BaseModel):
    is_enabled: bool


async def _rule_children(session: AsyncSession, rule_ids: list[int]) -> dict[int, dict]:
    out = {rid: {"camera_ids": [], "windows": [], "targets": [], "recipient_ids": [], "last_fired_at": None}
           for rid in rule_ids}
    if not rule_ids:
        return out
    for row in (await session.exec(select(AlarmRuleCamera).where(col(AlarmRuleCamera.rule_id).in_(rule_ids)))).all():
        out[row.rule_id]["camera_ids"].append(row.camera_id)
    for row in (await session.exec(select(AlarmRuleWindow).where(col(AlarmRuleWindow.rule_id).in_(rule_ids))
                                   .order_by(AlarmRuleWindow.iso_dow, AlarmRuleWindow.start_time))).all():
        out[row.rule_id]["windows"].append({"iso_dow": row.iso_dow, "start": row.start_time.strftime("%H:%M"),
                                            "end": row.end_time.strftime("%H:%M")})
    for row in (await session.exec(select(AlarmRuleTarget).where(col(AlarmRuleTarget.rule_id).in_(rule_ids)))).all():
        out[row.rule_id]["targets"].append({"type": plain(row.target_type), "value": row.target_value,
                                            "label": row.label})
    for row in (await session.exec(
            select(AlarmRuleRecipient).where(col(AlarmRuleRecipient.rule_id).in_(rule_ids)))).all():
        out[row.rule_id]["recipient_ids"].append(row.contact_id)
    for rid, fired in (await session.exec(
            select(AlarmRuleState.rule_id, func.max(AlarmRuleState.last_fired_at))
            .where(col(AlarmRuleState.rule_id).in_(rule_ids)).group_by(AlarmRuleState.rule_id))).all():
        out[rid]["last_fired_at"] = fired
    for children in out.values():
        children["camera_ids"].sort()
        children["recipient_ids"].sort()
    return out


def _rule_out(rule: AlarmRule, children: dict) -> dict:
    return {
        "id": rule.id, "name": rule.name, "description": rule.description, "is_enabled": rule.is_enabled,
        "severity": plain(rule.severity), "event_kinds": [plain(k) for k in rule.event_kinds],
        "match_mode": plain(rule.match_mode), "min_match_score": rule.min_match_score,
        "min_liveness": rule.min_liveness, "timezone": rule.timezone, "cooldown_seconds": rule.cooldown_seconds,
        "dedupe_scope": plain(rule.dedupe_scope), "max_delay_seconds": rule.max_delay_seconds,
        "email_delayed": rule.email_delayed, "attach_snapshot": rule.attach_snapshot, "version": rule.version,
        "created_at": rule.created_at, "updated_at": rule.updated_at, **children,
    }


async def _get_rule(session: AsyncSession, rule_id: int, lock: bool = False) -> AlarmRule:
    rule = await session.get(AlarmRule, rule_id, with_for_update=lock)
    if rule is None:
        raise HTTPException(404, f"Rule #{rule_id} doesn't exist")
    return rule


async def _rule_payload(session: AsyncSession, rule: AlarmRule) -> dict:
    return _rule_out(rule, (await _rule_children(session, [rule.id]))[rule.id])


async def _check_references(session: AsyncSession, box_id: int, body: RuleIn) -> None:
    camera_ids = set(body.camera_ids)
    found = set((await session.exec(select(Camera.id).where(
        Camera.box_id == box_id, col(Camera.id).in_(camera_ids), col(Camera.deleted_at).is_(None)))).all())
    if missing := camera_ids - found:
        raise HTTPException(422, f"Unknown or removed camera(s): {sorted(missing)}")
    recipient_ids = set(body.recipient_ids)
    found = set((await session.exec(select(Contact.id).where(col(Contact.id).in_(recipient_ids)))).all())
    if missing := recipient_ids - found:
        raise HTTPException(422, f"Unknown recipient(s): {sorted(missing)}")


def _apply_fields(rule: AlarmRule, body: RuleIn) -> None:
    rule.name, rule.description, rule.is_enabled = body.name, body.description, body.is_enabled
    rule.severity, rule.match_mode, rule.dedupe_scope = body.severity.value, body.match_mode.value, body.dedupe_scope.value
    rule.event_kinds = [k.value for k in body.event_kinds]
    rule.min_match_score, rule.min_liveness, rule.timezone = body.min_match_score, body.min_liveness, body.timezone
    rule.cooldown_seconds, rule.max_delay_seconds = body.cooldown_seconds, body.max_delay_seconds
    rule.email_delayed, rule.attach_snapshot = body.email_delayed, body.attach_snapshot


async def _replace_children(session: AsyncSession, rule_id: int, body: RuleIn) -> None:
    for model in (AlarmRuleCamera, AlarmRuleWindow, AlarmRuleTarget, AlarmRuleRecipient):
        await session.exec(delete(model).where(col(model.rule_id) == rule_id))
    session.add_all([AlarmRuleCamera(rule_id=rule_id, camera_id=c) for c in sorted(set(body.camera_ids))])
    windows = {(w.iso_dow, w.start, w.end) for w in body.windows}
    session.add_all([AlarmRuleWindow(rule_id=rule_id, iso_dow=d, start_time=s, end_time=e) for d, s, e in sorted(windows)])
    targets = {(t.type.value, t.value): t.label for t in body.targets}
    session.add_all([AlarmRuleTarget(rule_id=rule_id, target_type=kind, target_value=value, label=label)
                     for (kind, value), label in targets.items()])
    session.add_all([AlarmRuleRecipient(rule_id=rule_id, contact_id=c) for c in sorted(set(body.recipient_ids))])


@router.get("/api/alarms/rules")
async def list_rules(session: Session):
    rules = (await session.exec(select(AlarmRule).order_by(AlarmRule.name))).all()
    children = await _rule_children(session, [r.id for r in rules])
    return [_rule_out(r, children[r.id]) for r in rules]


@router.post("/api/alarms/rules", status_code=201)
async def create_rule(body: RuleIn, session: Session):
    box_id = await _get_box_id(session)
    await _check_references(session, box_id, body)
    rule = AlarmRule(box_id=box_id, name=body.name, event_kinds=[])
    _apply_fields(rule, body)
    session.add(rule)
    await _flush_or_409(session, f"A rule named '{body.name}' already exists")
    await _replace_children(session, rule.id, body)
    await session.flush()
    payload = await _rule_payload(session, rule)
    _audit(session, "create", "alarm_rule", rule.id, after=payload)
    await session.commit()
    return payload


@router.get("/api/alarms/rules/{rule_id}")
async def get_rule(session: Session, rule_id: int = Path(..., ge=1)):
    return await _rule_payload(session, await _get_rule(session, rule_id))


@router.put("/api/alarms/rules/{rule_id}")
async def update_rule(body: RuleUpdate, session: Session, rule_id: int = Path(..., ge=1)):
    rule = await _get_rule(session, rule_id, lock=True)    # two saves at once: the second waits, then gets 409
    if rule.version != body.version:
        raise HTTPException(409, "Someone else changed this rule while you were editing it. Reload and try again.")
    await _check_references(session, rule.box_id, body)
    before = await _rule_payload(session, rule)
    _apply_fields(rule, body)
    rule.version += 1
    rule.updated_at = _now()
    session.add(rule)
    await _replace_children(session, rule_id, body)
    await _flush_or_409(session, f"A rule named '{body.name}' already exists")
    payload = await _rule_payload(session, rule)
    _audit(session, "update", "alarm_rule", rule_id, before=before, after=payload)
    await session.commit()
    return payload


@router.patch("/api/alarms/rules/{rule_id}/enabled")
async def set_rule_enabled(body: EnabledIn, session: Session, rule_id: int = Path(..., ge=1)):
    rule = await _get_rule(session, rule_id)
    rule.is_enabled = body.is_enabled
    rule.version += 1
    rule.updated_at = _now()
    session.add(rule)
    _audit(session, "enable" if body.is_enabled else "disable", "alarm_rule", rule_id)
    await session.commit()
    return await _rule_payload(session, rule)


@router.delete("/api/alarms/rules/{rule_id}")
async def delete_rule(session: Session, rule_id: int = Path(..., ge=1)):
    """Past incidents stay (they keep a copy of the rule)."""
    rule = await _get_rule(session, rule_id)
    _audit(session, "delete", "alarm_rule", rule_id, before=await _rule_payload(session, rule))
    await session.delete(rule)
    await session.commit()
    return {"deleted": rule_id}


# =====================================================================
# Incidents
# =====================================================================

class IncidentUpdate(BaseModel):
    status: IncidentStatus | None = None
    note: str | None = Field(None, max_length=2000)
    by: str | None = Field(None, max_length=100)         # who is acknowledging (shown in the history)


def _incident_out(i: Incident, camera_name: str | None) -> dict:
    return {
        "id": i.id, "public_id": str(i.public_id), "rule_id": i.rule_id, "rule_name": i.rule_name,
        "severity": plain(i.severity), "camera_id": i.camera_id, "camera_name": camera_name,
        "track_id": i.track_id, "person_uuid": i.person_uuid, "person_name": i.person_name,
        "is_stranger": i.is_stranger, "occurred_at": i.occurred_at, "detected_at": i.detected_at,
        "delay_seconds": i.delay_seconds, "is_delayed": i.is_delayed, "event_count": i.event_count,
        "last_event_at": i.last_event_at, "status": plain(i.status), "acknowledged_by": i.acknowledged_by,
        "acknowledged_at": i.acknowledged_at, "note": i.note, "snapshot_path": i.snapshot_path,
    }


def _event_out(e: Event) -> dict:
    return {
        "id": e.id, "alarm_id": e.alarm_id, "kind": plain(e.kind), "occurred_at": e.occurred_at,
        "face_track_id": e.face_track_id, "body_track_id": e.body_track_id, "person_name": e.person_name,
        "match_score": e.match_score, "liveness_score": e.liveness_score, "face_image_path": e.face_image_path,
        "body_image_path": e.body_image_path, "panorama_path": e.panorama_path,
    }


def _notification_out(n: Notification) -> dict:
    return {"id": n.id, "to_address": n.to_address, "status": plain(n.status), "attempts": n.attempts,
            "last_error": n.last_error, "sent_at": n.sent_at, "next_attempt_at": n.next_attempt_at}


def _box_time(value: str | None) -> datetime | None:
    """'YYYY-MM-DD HH:mm:ss' in the box's time zone -> aware datetime."""
    return datetime.fromtimestamp(to_ms(value) / 1000, timezone.utc) if value else None


@router.get("/api/alarms/incidents")
async def list_incidents(
    session: Session,
    status: list[IncidentStatus] = Query(default_factory=list),
    rule_id: int | None = Query(None, ge=1),
    camera_id: int | None = Query(None, ge=1),
    start: str | None = None,
    end: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """Newest first. start/end: 'YYYY-MM-DD HH:mm:ss' in the box's time zone."""
    conditions = []
    if status:
        conditions.append(col(Incident.status).in_([s.value for s in status]))
    if rule_id:
        conditions.append(Incident.rule_id == rule_id)
    if camera_id:
        conditions.append(Incident.camera_id == camera_id)
    if (since := _box_time(start)) is not None:
        conditions.append(Incident.occurred_at >= since)
    if (until := _box_time(end)) is not None:
        conditions.append(Incident.occurred_at <= until)
    total = (await session.exec(select(func.count()).select_from(Incident).where(*conditions))).one()
    rows = (await session.exec(
        select(Incident, Camera.name).join(Camera, col(Camera.id) == Incident.camera_id).where(*conditions)
        .order_by(col(Incident.occurred_at).desc(), col(Incident.id).desc())
        .offset((page - 1) * size).limit(size)
    )).all()
    return {"total": total, "page": page, "size": size, "items": [_incident_out(i, name) for i, name in rows]}


async def _find_incident(session: AsyncSession, ref: str) -> Incident:
    """By number, or by the public id used in email links."""
    incident = None
    if ref.isdigit():
        incident = await session.get(Incident, int(ref))
    else:
        try:
            public_id = uuid.UUID(ref)
        except ValueError:
            raise HTTPException(404, "No such alarm")
        incident = (await session.exec(select(Incident).where(Incident.public_id == public_id))).first()
    if incident is None:
        raise HTTPException(404, "No such alarm")
    return incident


@router.get("/api/alarms/incidents/{ref}")
async def get_incident(session: Session, ref: str):
    incident = await _find_incident(session, ref)
    camera = await session.get(Camera, incident.camera_id)
    events = (await session.exec(
        select(Event).join(IncidentEvent, col(IncidentEvent.event_id) == Event.id)
        .where(IncidentEvent.incident_id == incident.id).order_by(col(Event.occurred_at).desc()).limit(50)
    )).all()
    notifications = (await session.exec(
        select(Notification).where(Notification.incident_id == incident.id).order_by(Notification.id))).all()
    return {
        **_incident_out(incident, camera.name if camera else None),
        "rule_snapshot": incident.rule_snapshot,
        "events": [_event_out(e) for e in events],
        "notifications": [_notification_out(n) for n in notifications],
    }


@router.patch("/api/alarms/incidents/{incident_id}")
async def update_incident(body: IncidentUpdate, session: Session, incident_id: int = Path(..., ge=1)):
    """Acknowledge, resolve, mark as a false alarm, reopen, or add a note."""
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "No such alarm")
    before = {"status": plain(incident.status), "note": incident.note}
    if body.status is not None and body.status.value != plain(incident.status):
        incident.status = body.status.value
        if body.status == IncidentStatus.OPEN:
            incident.acknowledged_at = incident.acknowledged_by = None
        elif incident.acknowledged_at is None:
            # Acknowledged, resolved and false alarm all mean someone has looked at it.
            incident.acknowledged_at = _now()
            incident.acknowledged_by = (body.by or "").strip() or "portal"
    if body.note is not None:
        incident.note = body.note.strip() or None
    incident.updated_at = _now()
    session.add(incident)
    _audit(session, "update", "incident", incident_id, before=before,
           after={"status": plain(incident.status), "note": incident.note}, actor=body.by)
    await session.commit()
    camera = await session.get(Camera, incident.camera_id)
    return _incident_out(incident, camera.name if camera else None)
