"""Value lists for the text columns. Stored as text + CHECK (see base.one_of), not native Postgres enums."""
from enum import Enum


class EventKind(str, Enum):
    MATCHED = "matched"              # face_basic_business / face_comparison_successful
    STRANGER = "stranger"            # face_basic_business / stranger
    FACE_CAPTURE = "face_capture"
    BODY_CAPTURE = "body_capture"


class EventSource(str, Enum):
    POLL = "poll"                    # we read it from alarm_history
    PUSH = "push"                    # the box sent it to us (Data Docking -> Alarm Push)


class IngestStream(str, Enum):
    # Two polling streams: the box needs different alarm_history queries for these.
    RECOGNITION = "recognition"      # matched + stranger
    CAPTURE = "capture"              # face_capture + body_capture (needs the "structure" entry)


class InboxStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"


class CountBasis(str, Enum):
    # Which sightings count as people on a camera.
    MERGED = "merged"                # every sighting (face + body track of one person merged into one)
    FACE = "face"                    # only sightings with a face track (identity known or comparable)
    BODY = "body"                    # only sightings with a body track (catches people facing away)


class PersonSource(str, Enum):
    RECOGNIZED = "recognized"        # matched a face-library person: person_key = "p:<person_uuid>"
    STRANGER = "stranger"            # grouped by face comparison: person_key = "s:<stranger_profile_id>"
    UNIDENTIFIED = "unidentified"    # nobody identified: person_key = "t:<camera_id>:<local_date>:b<body_track_id>",
                                     # or "...:f<face_track_id>" when the sighting has no body track


class RecognitionResult(str, Enum):
    # What the box's face comparison said about a sighting (NULL = no comparison record arrived).
    MATCHED = "matched"              # a face-library person (sets person_source = recognized)
    STRANGER = "stranger"            # compared, nobody matched; NOT grouped, so not a separate person


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MatchMode(str, Enum):
    ANYONE = "anyone"
    STRANGERS = "strangers"
    KNOWN = "known"                  # anyone in the face library
    TARGETS = "targets"              # only the people / groups in alarm_rule_targets


class DedupeScope(str, Enum):
    TRACK = "track"                  # at most one incident per track
    CAMERA = "camera"                # at most one incident per camera per cooldown (face + body of one
                                     # person have different track ids, so this avoids double alarms)


class TargetType(str, Enum):
    PERSON = "person"                # target_value = box person_id
    GROUP = "group"                  # target_value = box group_id


class IncidentStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_ALARM = "false_alarm"


class Channel(str, Enum):
    EMAIL = "email"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"                # gave up after max_attempts
    CANCELLED = "cancelled"
