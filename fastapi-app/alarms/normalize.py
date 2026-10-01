"""One box alarm_history record -> one `events` row (as a dict). Pure: no box or database calls.

Record shape: docs/box-api.md section 4.4.
"""
from datetime import datetime, timezone
from typing import Any

from models import EventKind

KIND_BY_MINOR = {
    "face_comparison_successful": EventKind.MATCHED,
    "stranger": EventKind.STRANGER,
    "face_capture": EventKind.FACE_CAPTURE,
    "body_capture": EventKind.BODY_CAPTURE,
}

# Keys on faces[0] / pedestrians[0] that are bookkeeping, not attributes.
_NOT_ATTRIBUTES = {"image_data", "link_info", "alarm_linkage", "track_id", "track_id_times", "recognition_info"}
_LIVENESS_KEYS = ("liveness_score", "living_score", "liveness", "live_score", "living_fraction")


def _first(items: Any) -> dict:
    return items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else {}


def _image(item: dict) -> str | None:
    return ((item.get("image_data") or {}).get("value") or "") or None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _score(value: Any) -> float | None:
    """0-1 or 0-100 -> 0-100."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return round(score * 100, 2) if 0 < score <= 1 else score


def _best_candidate(face: dict) -> dict:
    """recognition_info is best match first, padded with empty entries."""
    for candidate in face.get("recognition_info") or []:
        if isinstance(candidate, dict) and (candidate.get("person_uuid") or candidate.get("person_name")
                                             or candidate.get("name")):
            return candidate
    return {}


def _liveness(*sources: dict) -> float | None:
    for source in sources:
        for key in _LIVENESS_KEYS:
            if source.get(key) not in (None, ""):
                return _score(source[key])
    return None


def normalize(record: dict) -> dict | None:
    """Return the events columns for one record, or None when it isn't a record we keep
    (structure detections, missing id/camera/time)."""
    additional = record.get("additional") or {}
    kind = KIND_BY_MINOR.get(additional.get("alarm_minor"))
    alarm_id = _int(additional.get("alarm_id"))
    device_id = _int(additional.get("device_id"))
    time_ms = _int((record.get("global_info") or {}).get("time_ms"))
    if kind is None or alarm_id is None or device_id is None or time_ms is None:
        return None

    face = _first(record.get("faces"))
    body = _first(record.get("pedestrians"))
    candidate = _best_candidate(face)

    # A stranger's recognition_info holds the closest library face, which is NOT this person:
    # only a successful comparison names someone.
    person: dict = {"person_uuid": None, "person_name": None, "group_ids": None, "group_names": None}
    if kind == EventKind.MATCHED and candidate:
        groups = [g for g in candidate.get("group_info") or [] if isinstance(g, dict)]
        person = {
            "person_uuid": str(candidate.get("person_uuid") or "") or None,
            "person_name": str(candidate.get("person_name") or candidate.get("name") or "") or None,
            "group_ids": [str(g["group_id"]) for g in groups if g.get("group_id") not in (None, "")] or None,
            "group_names": [str(g["group_name"]) for g in groups if g.get("group_name")] or None,
        }

    attributes = {k: v for k, v in face.items() if k not in _NOT_ATTRIBUTES}
    body_attributes = {k: v for k, v in body.items() if k not in _NOT_ATTRIBUTES}
    if body_attributes:
        attributes["body"] = body_attributes

    return {
        **person,
        "alarm_id": alarm_id,
        "device_id": device_id,
        "kind": kind,
        "occurred_at": datetime.fromtimestamp(time_ms / 1000, timezone.utc),
        "face_track_id": _int(face.get("track_id")),
        "body_track_id": _int(body.get("track_id")),
        "match_score": _score(candidate.get("face_score")),
        "liveness_score": _liveness(face, candidate, record),
        "face_image_path": _image(face),
        "body_image_path": _image(body),
        "panorama_path": _image(_first(record.get("full_images"))),
        "attributes": attributes or None,
    }
