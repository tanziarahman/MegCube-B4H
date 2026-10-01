"""Checks new events against the enabled alarm rules and turns matches into incidents and queued emails.

Runs inside the same transaction that saved the events, so a crash never leaves an event saved
without its alarm, and a replay never fires twice (only genuinely new events reach this code).
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import (AlarmRule, AlarmRuleCamera, AlarmRuleRecipient, AlarmRuleState, AlarmRuleTarget,
                    AlarmRuleWindow, Camera, Contact, DedupeScope, Event, EventKind, Incident, IncidentEvent,
                    Notification)

from .mailer import subject_for
from .rules import RuleSpec, plain

# With dedupe_scope = track, an incident for the same track is reused if it started within this time.
TRACK_REUSE = timedelta(days=1)


async def load_rules(session: AsyncSession, box_id: int) -> list[RuleSpec]:
    rules = (await session.exec(
        select(AlarmRule).where(AlarmRule.box_id == box_id, col(AlarmRule.is_enabled).is_(True))
    )).all()
    if not rules:
        return []
    ids = [r.id for r in rules]
    cameras, windows, targets, recipients = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for row in (await session.exec(select(AlarmRuleCamera).where(col(AlarmRuleCamera.rule_id).in_(ids)))).all():
        cameras[row.rule_id].append(row.camera_id)
    for row in (await session.exec(select(AlarmRuleWindow).where(col(AlarmRuleWindow.rule_id).in_(ids)))).all():
        windows[row.rule_id].append(row)
    for row in (await session.exec(select(AlarmRuleTarget).where(col(AlarmRuleTarget.rule_id).in_(ids)))).all():
        targets[row.rule_id].append(row)
    for row in (await session.exec(
            select(AlarmRuleRecipient).where(col(AlarmRuleRecipient.rule_id).in_(ids)))).all():
        recipients[row.rule_id].append(row.contact_id)
    return [RuleSpec.from_rule(r, cameras[r.id], windows[r.id], targets[r.id], recipients[r.id]) for r in rules]


async def process(session: AsyncSession, events: list[Event], box_id: int) -> list[Incident]:
    """Fire the rules for these (new) events. Returns the incidents created."""
    if not events:
        return []
    rules = await load_rules(session, box_id)
    if not rules:
        return []
    camera_names = {c.id: c.name for c in (await session.exec(select(Camera).where(Camera.box_id == box_id))).all()}
    contacts = {c.id: c for c in (await session.exec(select(Contact).where(col(Contact.is_active).is_(True)))).all()}

    created: list[Incident] = []
    for event in sorted(events, key=lambda e: e.occurred_at):
        for spec in rules:
            if spec.matches(event):
                incident = await _apply(session, spec, event, camera_names, contacts)
                if incident is not None:
                    created.append(incident)
    return created


async def _apply(session, spec: RuleSpec, event: Event, camera_names, contacts) -> Incident | None:
    """Create an incident, or add the event to the incident it belongs to. Returns a NEW incident only."""
    track_id = event.face_track_id or event.body_track_id
    if spec.dedupe_scope == DedupeScope.TRACK and track_id is not None:
        existing = (await session.exec(
            select(Incident.id).where(
                Incident.rule_id == spec.id, Incident.camera_id == event.camera_id,
                Incident.track_id == track_id, Incident.occurred_at >= event.occurred_at - TRACK_REUSE,
            ).order_by(col(Incident.id).desc()).limit(1)
        )).first()
        if existing is not None:
            await _attach(session, existing, event)
            return None
        incident = await _create(session, spec, event, track_id, camera_names, contacts)
        await _remember(session, spec.id, event.camera_id, event.occurred_at, incident.id, only_if_cooled=None)
        return incident

    # Camera scope: at most one incident per rule + camera per cooldown. The upsert only succeeds
    # for the event that is allowed to fire, even when several arrive at once.
    fired = await _remember(session, spec.id, event.camera_id, event.occurred_at, None,
                            only_if_cooled=timedelta(seconds=spec.cooldown_seconds))
    if not fired:
        last = (await session.exec(
            select(AlarmRuleState.last_incident_id).where(
                AlarmRuleState.rule_id == spec.id, AlarmRuleState.camera_id == event.camera_id)
        )).first()
        if last is not None:
            await _attach(session, last, event)
        return None
    incident = await _create(session, spec, event, track_id, camera_names, contacts)
    await session.exec(
        update(AlarmRuleState)
        .where(col(AlarmRuleState.rule_id) == spec.id, col(AlarmRuleState.camera_id) == event.camera_id)
        .values(last_incident_id=incident.id)
    )
    return incident


async def _remember(session, rule_id: int, camera_id: int, at: datetime, incident_id: int | None,
                    only_if_cooled: timedelta | None) -> bool:
    """Record that the rule fired on this camera at `at`. With only_if_cooled, the row is only
    updated (and True returned) when the previous firing is at least that long before `at`."""
    table = AlarmRuleState.__table__
    stmt = pg_insert(table).values(rule_id=rule_id, camera_id=camera_id, last_fired_at=at,
                                   last_incident_id=incident_id)
    set_ = {"last_fired_at": func.greatest(table.c.last_fired_at, stmt.excluded.last_fired_at)}
    if incident_id is not None:
        set_["last_incident_id"] = stmt.excluded.last_incident_id
    where = None
    if only_if_cooled is not None:
        set_["last_fired_at"] = stmt.excluded.last_fired_at
        where = table.c.last_fired_at <= stmt.excluded.last_fired_at - only_if_cooled
    stmt = stmt.on_conflict_do_update(index_elements=[table.c.rule_id, table.c.camera_id], set_=set_, where=where)
    result = await session.exec(stmt.returning(table.c.rule_id))
    return result.first() is not None


async def _create(session, spec: RuleSpec, event: Event, track_id, camera_names, contacts) -> Incident:
    received = event.received_at or datetime.now(timezone.utc)
    delay = max(0, int((received - event.occurred_at).total_seconds()))
    delayed = delay > spec.max_delay_seconds
    incident = Incident(
        rule_id=spec.id, rule_name=spec.name, rule_snapshot=spec.snapshot, severity=spec.severity,
        camera_id=event.camera_id, trigger_event_id=event.id, sighting_id=event.sighting_id, track_id=track_id,
        person_uuid=event.person_uuid, person_name=event.person_name,
        is_stranger=plain(event.kind) == EventKind.STRANGER.value,
        occurred_at=event.occurred_at, delay_seconds=delay, is_delayed=delayed,
        event_count=1, last_event_at=event.occurred_at,
        snapshot_path=event.face_image_path or event.body_image_path or event.panorama_path,
    )
    session.add(incident)
    await session.flush()
    session.add(IncidentEvent(incident_id=incident.id, event_id=event.id))

    # A delayed alarm (e.g. caught up after downtime) is saved, but only emailed if the rule says so.
    if not delayed or spec.email_delayed:
        subject = subject_for(incident, camera_names.get(event.camera_id, f"Camera {event.camera_id}"), spec.tz)
        for contact_id in spec.recipient_ids:
            contact = contacts.get(contact_id)
            if contact is not None:
                session.add(Notification(incident_id=incident.id, contact_id=contact.id,
                                         to_address=contact.email, subject=subject))
    await session.flush()
    return incident


async def _attach(session, incident_id: int, event: Event) -> None:
    await session.exec(
        pg_insert(IncidentEvent.__table__).values(incident_id=incident_id, event_id=event.id).on_conflict_do_nothing()
    )
    table = Incident.__table__
    await session.exec(
        update(table).where(table.c.id == incident_id).values(
            event_count=table.c.event_count + 1,
            last_event_at=func.greatest(table.c.last_event_at, event.occurred_at),
        )
    )
