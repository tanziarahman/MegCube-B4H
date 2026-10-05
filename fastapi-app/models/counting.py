"""People counting: walk-pasts (sightings), strangers grouped by face, and 15-minute totals."""
from datetime import date, datetime

from sqlalchemy import REAL, BigInteger, CheckConstraint, Date, Index, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from .base import TIMESTAMPTZ, bigint_pk, created_at_field, one_of, updated_at_field
from .enums import PersonSource, RecognitionResult


class StrangerProfile(SQLModel, table=True):
    """One stranger, as recognised by comparing face fingerprints across their sightings.
    `embedding` is the running average of their faces; new stranger faces are compared against it.

    Fingerprints are plain float arrays and the comparison runs in Python on the strangers seen in the
    chosen camera/period (a few thousand at most, ~1 ms). If matching ever has to span months of data,
    switch these columns to pgvector and add a nearest-neighbour index; that's a migration, not a redesign.
    """
    __tablename__ = "stranger_profiles"
    __table_args__ = (Index("ix_stranger_profiles_seen", "box_id", "last_seen_at"),)

    id: int | None = bigint_pk()
    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE")
    embedding: list[float] = Field(sa_type=ARRAY(REAL))
    embedding_model: str = Field(sa_type=String(64))              # never compare across models
    first_seen_at: datetime = Field(sa_type=TIMESTAMPTZ)
    last_seen_at: datetime = Field(sa_type=TIMESTAMPTZ)
    sighting_count: int = 1
    representative_image_path: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = created_at_field()


class Sighting(SQLModel, table=True):
    """One walk-past of one person in front of one camera: the box's repeated captures of a track
    collapse into it, and the face track and body track of the same person merge into one row.

    Unique people = COUNT(DISTINCT person_key) over the chosen cameras and period. person_key can
    change after insert (a recognition arrives after the capture, or a stranger gets grouped), which
    is why unique counts are computed from this table at query time, not pre-totalled.
    A track id belongs to one local day (track ids may restart when the box reboots).
    """
    __tablename__ = "sightings"
    __table_args__ = (
        CheckConstraint("face_track_id IS NOT NULL OR body_track_id IS NOT NULL", name="has_track"),
        CheckConstraint("local_hour BETWEEN 0 AND 23", name="local_hour"),
        CheckConstraint("iso_dow BETWEEN 1 AND 7", name="iso_dow"),
        one_of("person_source", PersonSource),
        one_of("recognition_result", RecognitionResult),
        Index("uq_sightings_face_track", "camera_id", "local_date", "face_track_id", unique=True,
              postgresql_where=text("face_track_id IS NOT NULL")),
        Index("uq_sightings_body_track", "camera_id", "local_date", "body_track_id", unique=True,
              postgresql_where=text("body_track_id IS NOT NULL")),
        # Counting queries: camera + time range, read person_key without touching the table.
        Index("ix_sightings_camera_time", "camera_id", "first_seen_at",
              postgresql_include=["person_key", "person_source"]),
        Index("ix_sightings_camera_hour", "camera_id", "local_date", "local_hour"),
        # Site-wide counts (all cameras).
        Index("ix_sightings_time", "first_seen_at", postgresql_include=["person_key"]),
        # "Was this person on this camera a moment ago?" (visit merging, alarm context).
        Index("ix_sightings_person", "camera_id", "person_key", "last_seen_at"),
    )

    id: int | None = bigint_pk()
    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE")
    camera_id: int = Field(foreign_key="cameras.id")
    local_date: date = Field(sa_type=Date)                        # box-local, of first_seen_at
    local_hour: int = Field(sa_type=SmallInteger)                 # for "09:00-17:00 only" filters
    iso_dow: int = Field(sa_type=SmallInteger)                    # 1 = Monday, for weekday filters
    face_track_id: int | None = Field(default=None, sa_type=BigInteger)
    body_track_id: int | None = Field(default=None, sa_type=BigInteger)
    first_seen_at: datetime = Field(sa_type=TIMESTAMPTZ)
    last_seen_at: datetime = Field(sa_type=TIMESTAMPTZ)
    event_count: int = 1
    person_key: str = Field(sa_type=String(100))                  # see PersonSource for the formats
    person_source: PersonSource = Field(default=PersonSource.UNIDENTIFIED, sa_type=String(12))
    person_uuid: str | None = Field(default=None, sa_type=String(64))
    person_name: str | None = Field(default=None, sa_type=String(200))
    # Split of walk-pasts into recognised / stranger / not compared, even without stranger grouping.
    recognition_result: RecognitionResult | None = Field(default=None, sa_type=String(10))
    stranger_profile_id: int | None = Field(default=None, foreign_key="stranger_profiles.id",
                                            ondelete="SET NULL", sa_type=BigInteger)
    best_match_score: float | None = None
    best_face_image_path: str | None = Field(default=None, sa_type=Text)
    best_body_image_path: str | None = Field(default=None, sa_type=Text)
    # The best face's fingerprint; kept so stranger grouping can be redone with a new threshold.
    face_embedding: list[float] | None = Field(default=None, sa_type=ARRAY(REAL))
    embedding_model: str | None = Field(default=None, sa_type=String(64))
    # Whole-body (clothing) fingerprint: tells people apart within a day when faces are unclear.
    body_embedding: list[float] | None = Field(default=None, sa_type=ARRAY(REAL))
    body_embedding_model: str | None = Field(default=None, sa_type=String(64))


class CountBucket(SQLModel, table=True):
    """Sightings per camera per 15 minutes: fast footfall charts over any range, kept forever
    (16 cameras x 96 buckets/day is ~560k rows a year). Only add-up-able numbers live here; unique
    people can't be added across buckets, so they come from `sightings`. The writer never adds or
    subtracts: after each batch it recounts the touched buckets from `sightings` and `events`
    (counting/builder.py), so merges and late records can't make the totals drift. Dashboard
    per-kind and score totals are recounted here as additive columns."""
    __tablename__ = "count_buckets"
    __table_args__ = (
        CheckConstraint("local_hour BETWEEN 0 AND 23", name="local_hour"),
        CheckConstraint("local_minute IN (0, 15, 30, 45)", name="local_minute"),
        CheckConstraint("iso_dow BETWEEN 1 AND 7", name="iso_dow"),
        Index("ix_count_buckets_camera_day", "camera_id", "local_date", "local_hour"),
        Index("ix_count_buckets_day", "local_date"),
    )

    camera_id: int = Field(foreign_key="cameras.id", primary_key=True)
    bucket_start: datetime = Field(sa_type=TIMESTAMPTZ, primary_key=True)   # UTC, aligned to 15 min
    local_date: date = Field(sa_type=Date)
    local_hour: int = Field(sa_type=SmallInteger)
    local_minute: int = Field(sa_type=SmallInteger)
    iso_dow: int = Field(sa_type=SmallInteger)
    sightings: int = 0                                            # merged walk-pasts
    face_sightings: int = 0                                       # ... that have a face track
    body_sightings: int = 0                                       # ... that have a body track
    events: int = 0                                               # raw box records (activity level)
    # Dashboard numbers, recounted with the others. "identity" = matched + stranger records.
    matched_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    stranger_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    face_capture_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    body_capture_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    low_confidence_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    low_liveness_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    identity_score_sum: float = Field(default=0, sa_column_kwargs={"server_default": "0"})
    identity_score_count: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    updated_at: datetime = updated_at_field()
