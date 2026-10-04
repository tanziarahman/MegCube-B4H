"""Database tables (PostgreSQL on Neon, via SQLModel) for alarms and people counting.

Where the data comes from:
  - The box's records (POST /device_alarm/alarm_history, or the box's own HTTP push) are cleaned up
    into `events`: one row per box record (recognition, stranger, face capture, body capture).
  - Events that belong to the same walk-past on one camera are grouped into `sightings`
    (face track + body track of one person). Counting is built on sightings.
  - Strangers have no id on the box, so we group their faces ourselves into `stranger_profiles`
    by comparing face fingerprints (in Python; the database only stores them).
  - `alarm_rules` are checked against new events; a match creates an `incident` and one
    `notification` (email) per recipient.

Conventions:
  - Every timestamp is timestamptz (UTC). The box-local date/hour/weekday is stored next to it where
    we filter on it, because Postgres can't compute time-zone conversions in a generated column.
  - "Enums" are text + CHECK, not native Postgres enums (native ones are painful to change in Alembic).
  - Rows that point at box data also copy its label (person_name, rule_name, to_address): the box
    deletes people and rotates records, and our history must still read correctly.
  - No secrets here: SMTP / box passwords stay in .env.

Modules:
  base       naming convention and column helpers
  enums      value lists for the text columns
  reference  boxes, cameras, contacts
  ingest     push_inbox, ingest_cursors, events
  counting   stranger_profiles, sightings, count_buckets
  alarms     alarm_rules (+ cameras, windows, targets, recipients, state), incidents, notifications
  admin      app_settings, audit_log

Importing this package registers every table on SQLModel.metadata (what Alembic needs), so import
from here: `from models import Event, EventKind`.
"""
from .admin import AppSetting, AuditLog
from .alarms import (AlarmRule, AlarmRuleCamera, AlarmRuleRecipient, AlarmRuleState, AlarmRuleTarget,
                     AlarmRuleWindow, Incident, IncidentEvent, Notification)
from .base import TIMESTAMPTZ, utcnow
from .counting import CountBucket, Sighting, StrangerProfile
from .enums import (Channel, CountBasis, DedupeScope, EventKind, EventSource, InboxStatus,
                    IncidentStatus, IngestStream, MatchMode, NotificationStatus, PersonSource, RecognitionResult,
                    Severity, TargetType)
from .ingest import Event, IngestCursor, PushInbox
from .reference import Box, Camera, Contact

__all__ = [
    # reference
    "Box", "Camera", "Contact",
    # ingest
    "PushInbox", "IngestCursor", "Event",
    # counting
    "StrangerProfile", "Sighting", "CountBucket",
    # alarms
    "AlarmRule", "AlarmRuleCamera", "AlarmRuleWindow", "AlarmRuleTarget", "AlarmRuleRecipient",
    "AlarmRuleState", "Incident", "IncidentEvent", "Notification",
    # admin
    "AppSetting", "AuditLog",
    # enums
    "EventKind", "EventSource", "IngestStream", "InboxStatus", "CountBasis", "PersonSource", "RecognitionResult",
    "Severity", "MatchMode", "DedupeScope", "TargetType", "IncidentStatus", "Channel",
    "NotificationStatus",
    # helpers
    "TIMESTAMPTZ", "utcnow",
]
