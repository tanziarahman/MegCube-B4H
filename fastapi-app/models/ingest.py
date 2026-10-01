"""Taking in box data: raw pushed messages, polling progress, and the cleaned-up box records."""
from datetime import datetime

from sqlalchemy import BigInteger, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from .base import TIMESTAMPTZ, bigint_pk, created_at_field, one_of
from .enums import EventKind, EventSource, InboxStatus, IngestStream


class PushInbox(SQLModel, table=True):
    """Raw messages the box pushes to us, saved before processing: a debug trail while the push format
    is still unknown, and a way to reprocess after a parser fix. Kept ~7 days."""
    __tablename__ = "push_inbox"
    __table_args__ = (
        one_of("status", InboxStatus),
        Index("ix_push_inbox_pending", "received_at", postgresql_where=text("status = 'pending'")),
    )

    id: int | None = bigint_pk()
    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE")
    received_at: datetime = created_at_field()
    remote_addr: str | None = Field(default=None, sa_type=String(64))
    headers: dict | None = Field(default=None, sa_type=JSONB)
    payload: dict = Field(sa_type=JSONB)
    status: InboxStatus = Field(default=InboxStatus.PENDING, sa_type=String(10))
    error: str | None = Field(default=None, sa_type=Text)
    processed_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)


class IngestCursor(SQLModel, table=True):
    """Where polling alarm_history left off, per stream. Each poll goes back overlap_seconds and skips
    duplicates (events' unique key), so a late-arriving record isn't missed."""
    __tablename__ = "ingest_cursors"
    __table_args__ = (one_of("stream", IngestStream),)

    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE", primary_key=True)
    stream: IngestStream = Field(sa_type=String(12), primary_key=True)
    last_occurred_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)
    overlap_seconds: int = 60
    last_run_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)
    last_success_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)   # shown as "ingest lag"
    consecutive_failures: int = 0
    last_error: str | None = Field(default=None, sa_type=Text)
    events_ingested: int = Field(default=0, sa_type=BigInteger)


class Event(SQLModel, table=True):
    """One box record, cleaned up. The largest table (kept ~90 days).

    The unique key makes every replay harmless: INSERT ... ON CONFLICT DO NOTHING RETURNING id gives
    only the events we haven't seen, and only those go on to sightings, counts and alarm rules.
    """
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("box_id", "kind", "alarm_id"),
        one_of("kind", EventKind),
        one_of("source", EventSource),
        Index("ix_events_camera_time", "camera_id", "occurred_at"),
        Index("ix_events_occurred_brin", "occurred_at", postgresql_using="brin"),
        Index("ix_events_person_time", "person_uuid", "occurred_at",
              postgresql_where=text("person_uuid IS NOT NULL")),
        Index("ix_events_sighting", "sighting_id"),
    )

    id: int | None = bigint_pk()
    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE")
    camera_id: int = Field(foreign_key="cameras.id")
    alarm_id: int = Field(sa_type=BigInteger)                     # additional.alarm_id
    kind: EventKind = Field(sa_type=String(12))                   # from additional.alarm_minor
    source: EventSource = Field(sa_type=String(4))
    occurred_at: datetime = Field(sa_type=TIMESTAMPTZ)            # global_info.time_ms: when the box saw it
    received_at: datetime = created_at_field()                         # received_at - occurred_at = delay
    face_track_id: int | None = Field(default=None, sa_type=BigInteger)   # faces[0].track_id
    body_track_id: int | None = Field(default=None, sa_type=BigInteger)   # pedestrians[0].track_id
    sighting_id: int | None = Field(default=None, foreign_key="sightings.id", ondelete="SET NULL",
                                    sa_type=BigInteger)
    # Best library match (faces[0].recognition_info[0]); no FK, the person lives on the box.
    person_uuid: str | None = Field(default=None, sa_type=String(64))
    person_name: str | None = Field(default=None, sa_type=String(200))
    group_ids: list[str] | None = Field(default=None, sa_type=ARRAY(String(64)))
    group_names: list[str] | None = Field(default=None, sa_type=ARRAY(String(200)))
    match_score: float | None = None                              # normalised to 0-100
    liveness_score: float | None = None                           # normalised to 0-100
    # Paths on the box (fetch with /device_storage/get_image). They break once the box rotates them out.
    face_image_path: str | None = Field(default=None, sa_type=Text)
    body_image_path: str | None = Field(default=None, sa_type=Text)
    panorama_path: str | None = Field(default=None, sa_type=Text)
    attributes: dict | None = Field(default=None, sa_type=JSONB)  # age, gender, hat, glasses, ... (raw codes)
