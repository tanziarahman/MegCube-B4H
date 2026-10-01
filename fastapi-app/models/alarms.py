"""Alarms: rules and their cameras / time windows / targets / recipients, incidents, and the email queue."""
import uuid
from datetime import datetime, time

from sqlalchemy import (BigInteger, CheckConstraint, Index, SmallInteger, String, Text, Time,
                        UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from .base import TIMESTAMPTZ, bigint_pk, created_at_field, int_pk, one_of, updated_at_field, utcnow
from .enums import (Channel, DedupeScope, IncidentStatus, MatchMode, NotificationStatus, Severity,
                    TargetType)


class AlarmRule(SQLModel, table=True):
    """E.g. "On D3, 22:00-06:00 box time, any person -> email 5 admins".
    Cameras, time windows, targets and recipients are child tables, so the database checks them."""
    __tablename__ = "alarm_rules"
    __table_args__ = (
        UniqueConstraint("name"),
        one_of("severity", Severity),
        one_of("match_mode", MatchMode),
        one_of("dedupe_scope", DedupeScope),
        CheckConstraint("cardinality(event_kinds) > 0", name="event_kinds_not_empty"),
        CheckConstraint("event_kinds <@ ARRAY['matched','stranger','face_capture','body_capture']::varchar[]",
                        name="event_kinds_valid"),
        CheckConstraint("cooldown_seconds >= 0", name="cooldown_seconds"),
        CheckConstraint("max_delay_seconds >= 0", name="max_delay_seconds"),
        CheckConstraint("min_match_score IS NULL OR min_match_score BETWEEN 0 AND 100", name="min_match_score"),
        CheckConstraint("min_liveness IS NULL OR min_liveness BETWEEN 0 AND 100", name="min_liveness"),
    )

    id: int | None = int_pk()
    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE")
    name: str = Field(sa_type=String(100))
    description: str | None = Field(default=None, sa_type=Text)
    is_enabled: bool = True
    severity: Severity = Field(default=Severity.WARNING, sa_type=String(10))
    event_kinds: list[str] = Field(sa_type=ARRAY(String(12)))     # which EventKind values trigger it
    match_mode: MatchMode = Field(default=MatchMode.ANYONE, sa_type=String(10))
    min_match_score: float | None = None
    min_liveness: float | None = None                             # ignore photos held up to the camera
    timezone: str = Field(default="Asia/Dhaka", sa_type=String(64))   # time windows are in this zone
    cooldown_seconds: int = 300
    dedupe_scope: DedupeScope = Field(default=DedupeScope.CAMERA, sa_type=String(8))
    max_delay_seconds: int = 300                                  # older on arrival = "delayed"
    email_delayed: bool = False                                   # email delayed incidents too?
    attach_snapshot: bool = True
    version: int = 1                                              # optimistic locking for edits
    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()


class AlarmRuleCamera(SQLModel, table=True):
    __tablename__ = "alarm_rule_cameras"

    rule_id: int = Field(foreign_key="alarm_rules.id", ondelete="CASCADE", primary_key=True)
    camera_id: int = Field(foreign_key="cameras.id", ondelete="CASCADE", primary_key=True)


class AlarmRuleWindow(SQLModel, table=True):
    """When the rule is active, per weekday. end_time < start_time means it runs past midnight
    (22:00 -> 06:00 belongs to the weekday it starts on). A rule with no windows is always active."""
    __tablename__ = "alarm_rule_windows"
    __table_args__ = (
        CheckConstraint("iso_dow BETWEEN 1 AND 7", name="iso_dow"),
        CheckConstraint("start_time <> end_time", name="not_empty"),
        Index("ix_alarm_rule_windows_rule", "rule_id"),
    )

    id: int | None = int_pk()
    rule_id: int = Field(foreign_key="alarm_rules.id", ondelete="CASCADE")
    iso_dow: int = Field(sa_type=SmallInteger)                    # 1 = Monday
    start_time: time = Field(sa_type=Time)
    end_time: time = Field(sa_type=Time)


class AlarmRuleTarget(SQLModel, table=True):
    """Who the rule watches when match_mode = targets: box people and/or groups."""
    __tablename__ = "alarm_rule_targets"
    __table_args__ = (one_of("target_type", TargetType),)

    rule_id: int = Field(foreign_key="alarm_rules.id", ondelete="CASCADE", primary_key=True)
    target_type: TargetType = Field(sa_type=String(6), primary_key=True)
    target_value: str = Field(sa_type=String(64), primary_key=True)   # box person_id or group_id
    label: str | None = Field(default=None, sa_type=String(200))      # copied name for display


class AlarmRuleRecipient(SQLModel, table=True):
    __tablename__ = "alarm_rule_recipients"

    rule_id: int = Field(foreign_key="alarm_rules.id", ondelete="CASCADE", primary_key=True)
    contact_id: int = Field(foreign_key="contacts.id", ondelete="CASCADE", primary_key=True)


class AlarmRuleState(SQLModel, table=True):
    """Last time a rule fired on a camera. Makes the cooldown safe with events arriving together:
    INSERT ... ON CONFLICT DO UPDATE SET last_fired_at = :t WHERE last_fired_at < :t - cooldown
    RETURNING ... gives a row only to the event that is allowed to fire."""
    __tablename__ = "alarm_rule_state"

    rule_id: int = Field(foreign_key="alarm_rules.id", ondelete="CASCADE", primary_key=True)
    camera_id: int = Field(foreign_key="cameras.id", ondelete="CASCADE", primary_key=True)
    last_fired_at: datetime = Field(sa_type=TIMESTAMPTZ)
    last_incident_id: int | None = Field(default=None, foreign_key="incidents.id", ondelete="SET NULL",
                                         sa_type=BigInteger)


class Incident(SQLModel, table=True):
    """One alarm that fired. Keeps a snapshot of the rule, so editing or deleting the rule later
    doesn't rewrite history. More matching events during the cooldown raise event_count instead of
    creating new incidents."""
    __tablename__ = "incidents"
    __table_args__ = (
        one_of("status", IncidentStatus),
        one_of("severity", Severity),
        Index("ix_incidents_status_time", "status", "occurred_at"),
        Index("ix_incidents_rule_time", "rule_id", "occurred_at"),
        Index("ix_incidents_camera_time", "camera_id", "occurred_at"),
    )

    id: int | None = bigint_pk()
    public_id: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True,
                                 sa_column_kwargs={"server_default": text("gen_random_uuid()")})  # email links
    rule_id: int | None = Field(default=None, foreign_key="alarm_rules.id", ondelete="SET NULL")
    rule_name: str = Field(sa_type=String(100))
    rule_snapshot: dict = Field(sa_type=JSONB)
    severity: Severity = Field(sa_type=String(10))
    camera_id: int = Field(foreign_key="cameras.id")
    trigger_event_id: int | None = Field(default=None, foreign_key="events.id", ondelete="SET NULL",
                                         sa_type=BigInteger)   # events are deleted sooner than incidents
    sighting_id: int | None = Field(default=None, foreign_key="sightings.id", ondelete="SET NULL",
                                    sa_type=BigInteger)
    track_id: int | None = Field(default=None, sa_type=BigInteger)
    person_uuid: str | None = Field(default=None, sa_type=String(64))
    person_name: str | None = Field(default=None, sa_type=String(200))
    is_stranger: bool = False
    occurred_at: datetime = Field(sa_type=TIMESTAMPTZ)            # when the box saw the person
    detected_at: datetime = created_at_field()                         # when we processed it
    delay_seconds: int = 0
    is_delayed: bool = False
    event_count: int = 1
    last_event_at: datetime = Field(sa_type=TIMESTAMPTZ)
    status: IncidentStatus = Field(default=IncidentStatus.OPEN, sa_type=String(12))
    acknowledged_by: str | None = Field(default=None, sa_type=String(100))   # a user FK once auth exists
    acknowledged_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)
    note: str | None = Field(default=None, sa_type=Text)
    snapshot_path: str | None = Field(default=None, sa_type=Text)            # path on the box
    snapshot_key: str | None = Field(default=None, sa_type=String(255))      # our own stored copy
    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()


class IncidentEvent(SQLModel, table=True):
    """Every event grouped into an incident."""
    __tablename__ = "incident_events"

    incident_id: int = Field(foreign_key="incidents.id", ondelete="CASCADE", primary_key=True,
                             sa_type=BigInteger)
    event_id: int = Field(foreign_key="events.id", ondelete="CASCADE", primary_key=True, sa_type=BigInteger)


class Notification(SQLModel, table=True):
    """Email queue: one row per recipient per incident, so one bad address doesn't block the others.

    The sender claims rows in a short transaction (FOR UPDATE SKIP LOCKED, status = sending,
    locked_until = now + 2 min), commits, then talks to SMTP. A row whose lease ran out can be
    claimed again; the unique key stops an incident from queueing the same email twice."""
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("incident_id", "contact_id", "channel"),
        one_of("channel", Channel),
        one_of("status", NotificationStatus),
        CheckConstraint("attempts >= 0 AND attempts <= max_attempts", name="attempts"),
        Index("ix_notifications_due", "next_attempt_at",
              postgresql_where=text("status IN ('pending', 'sending')")),
    )

    id: int | None = bigint_pk()
    incident_id: int = Field(foreign_key="incidents.id", ondelete="CASCADE", sa_type=BigInteger)
    contact_id: int | None = Field(default=None, foreign_key="contacts.id", ondelete="SET NULL")
    channel: Channel = Field(default=Channel.EMAIL, sa_type=String(10))
    to_address: str = Field(sa_type=String(254))                  # copied
    subject: str | None = Field(default=None, sa_type=String(255))
    status: NotificationStatus = Field(default=NotificationStatus.PENDING, sa_type=String(10))
    attempts: int = Field(default=0, sa_type=SmallInteger)
    max_attempts: int = Field(default=5, sa_type=SmallInteger)
    next_attempt_at: datetime = Field(default_factory=utcnow, sa_type=TIMESTAMPTZ)
    locked_until: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)
    last_error: str | None = Field(default=None, sa_type=Text)
    provider_message_id: str | None = Field(default=None, sa_type=String(255))
    created_at: datetime = created_at_field()
    sent_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)
