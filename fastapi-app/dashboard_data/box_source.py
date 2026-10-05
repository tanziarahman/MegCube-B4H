"""The original box-backed dashboard computation, retained as the fallback for uncovered dates."""
from collections import Counter
from datetime import date, datetime
from typing import Any

from b4h import B4HError
from core import BOX_MAX_PAGE_SIZE, BOX_TZ, RECOG_MAJOR, alarm_history_page, box, time_range

MATCHED = "face_comparison_successful"
STRANGER = "stranger"
MAX_ANALYSIS_RECORDS = 5000


def _find(value: Any, keys: set[str]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            if value.get(key) not in (None, ""):
                return value[key]
        for nested in value.values():
            found = _find(nested, keys)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find(nested, keys)
            if found not in (None, ""):
                return found
    return None


def _record_time(record: dict) -> int | None:
    value = _find(record, {"time_ms", "capture_time", "alarm_time", "timestamp", "time"})
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return timestamp * 1000 if timestamp < 10**12 else timestamp


def _device_id(record: dict) -> str:
    value = _find(record, {"device_id", "channel_id"})
    return str(value) if value is not None else ""


def _person_name(record: dict) -> str:
    value = _find(record, {"person_name", "name"})
    return str(value).strip() if value is not None else ""


def _score(record: dict, keys: set[str]) -> float | None:
    value = _find(record, keys)
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score * 100 if 0 < score <= 1 else score


def _history_body(start: str, end: str, minor: str, size: int = BOX_MAX_PAGE_SIZE) -> dict:
    start_ms, end_ms = time_range(start, end)
    return {
        "offset": 0, "size": size,
        "query_condition": {
            "start_time": start_ms, "end_time": end_ms,
            "alarm_type": [{"major_type": RECOG_MAJOR, "minor_type": [minor]}],
            "ext": {"query_type": 0, "de_dup": 0},
        },
    }


def _capture_body(start: str, end: str, size: int = BOX_MAX_PAGE_SIZE) -> dict:
    start_ms, end_ms = time_range(start, end)
    return {
        "offset": 0, "size": size,
        "query_condition": {
            "start_time": start_ms, "end_time": end_ms,
            "alarm_type": [
                {"major_type": RECOG_MAJOR, "minor_type": ["face_capture", "body_capture"]},
                {"major_type": "structure", "minor_type": ["face", "pedestrian", "vehicle", "non_motor", "plate"]},
            ],
        },
    }


async def _first_page(body: dict) -> dict:
    return await box.call("POST", "/device_alarm/alarm_history", body) or {}


async def _collect_history(body: dict) -> dict:
    first = await alarm_history_page(body)
    total = int(first.get("total_count") or 0)
    records = list(first.get("list") or [])
    target = min(total, MAX_ANALYSIS_RECORDS)
    while len(records) < target and records:
        page = await alarm_history_page({
            **body, "offset": len(records), "size": min(BOX_MAX_PAGE_SIZE, target - len(records)),
        })
        batch = list(page.get("list") or [])
        if not batch:
            break
        records.extend(batch)
    return {"records": records[:target], "total": total, "limited": len(records) < total}


async def _device_health() -> tuple[list[dict], list[dict], dict]:
    configs = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100}) or []
    states = await box.call("POST", "/device_access/device_state", {"offset": 0, "size": 100}) or []
    tasks = await box.call("POST", "/intelli_manager/task_list",
                           {"offset": 0, "size": 50, "condition": {}}) or {}
    return configs, states, tasks


async def _clock() -> dict:
    try:
        system = await box.call("POST", "/system/get_system_time") or {}
    except B4HError as exc:
        if exc.code != 404:
            raise
        system = {}
    try:
        current = await box.call("POST", "/system/get_time_info") or {}
    except B4HError as exc:
        if exc.code != 404:
            raise
        current = {}
    return {
        "time": current.get("time"), "time_zone": system.get("time_zone"),
        "source": "box" if system and current.get("time") else "unavailable",
    }


def _device_rows(configs: list[dict], states: list[dict], tasks: dict) -> list[dict]:
    state_by_id = {s.get("device_id"): s for s in states}
    task_by_id = {
        device.get("device_id"): task.get("task_name")
        for task in tasks.get("list", [])
        for device in task.get("device_list", [])
    }
    return [{
        "id": device_id,
        "name": config.get("device_name") or f"Device {device_id}",
        "online": (state_by_id.get(device_id) or {}).get("state") == 0,
        "state_code": (state_by_id.get(device_id) or {}).get("state"),
        "pulling_stream": any(channel.get("pull_stream")
                              for channel in (state_by_id.get(device_id) or {}).get("channels") or []),
        "task": task_by_id.get(device_id),
    } for config in configs for device_id in [config.get("device_id")]]


def _sample_metrics(records: list[dict], device_names: dict[str, str]) -> dict:
    hours, devices, people = Counter(), Counter(), Counter()
    scores, events = [], []
    low_confidence = low_liveness = 0
    for record in records:
        timestamp = _record_time(record)
        device_id = _device_id(record)
        if timestamp:
            hours[datetime.fromtimestamp(timestamp / 1000, BOX_TZ).hour] += 1
        devices[device_id] += 1
        name = _person_name(record)
        if name:
            people[name] += 1
        match_score = _score(record, {"face_score", "similarity", "score", "compare_score", "match_score"})
        liveness = _score(record, {"liveness_score", "living_score", "liveness", "live_score"})
        if match_score is not None:
            scores.append(match_score)
            low_confidence += match_score < 70
        if liveness is not None:
            low_liveness += liveness < 80
        minor = _find(record, {"alarm_minor"}) or "recognition"
        events.append({
            "id": str(_find(record, {"alarm_id", "data_uuid", "record_id", "uuid", "id"}) or len(events)),
            "type": "stranger" if minor == STRANGER else "matched" if minor == MATCHED else str(minor),
            "person": name or None, "device_id": device_id,
            "device": device_names.get(device_id, f"Device {device_id}"),
            "time_ms": timestamp, "score": round(match_score, 1) if match_score is not None else None,
        })
    events.sort(key=lambda event: event["time_ms"] or 0, reverse=True)
    return {
        "peak_hour": hours.most_common(1)[0][0] if hours else None,
        "busiest_device_id": devices.most_common(1)[0][0] if devices else None,
        "busiest_device": device_names.get(devices.most_common(1)[0][0], "") if devices else None,
        "average_match_score": round(sum(scores) / len(scores), 1) if scores else None,
        "low_confidence_count": low_confidence, "low_liveness_count": low_liveness,
        "top_people": [{"name": name, "count": count} for name, count in people.most_common(5)],
        "hourly_activity": [{"hour": hour, "count": hours.get(hour, 0)} for hour in range(24)],
        "events": events[:8],
    }


def _encounter_key(record: dict, fallback_prefix: str) -> str:
    device_id = _device_id(record)
    track_id = _find(record, {"track_id"})
    if track_id not in (None, ""):
        return f"{device_id}:{track_id}"
    alarm_id = _find(record, {"alarm_id", "data_uuid", "record_id", "uuid", "id"})
    return f"{fallback_prefix}:{device_id}:{alarm_id or id(record)}"


def _person_key(record: dict) -> str | None:
    value = _find(record, {"person_id", "person_uuid"})
    if value not in (None, ""):
        return str(value)
    name = _person_name(record).lower()
    return name or None


def _encounter_metrics(capture_records, matched_records, stranger_records, device_names) -> dict:
    capture_keys = {_encounter_key(record, "capture") for record in capture_records}
    face_records = [r for r in capture_records if _find(r, {"alarm_minor"}) == "face_capture"]
    body_records = [r for r in capture_records if _find(r, {"alarm_minor"}) == "body_capture"]
    face_keys = {_encounter_key(record, "face") for record in face_records}
    body_keys = {_encounter_key(record, "body") for record in body_records}
    matched_keys = {_encounter_key(record, "matched") for record in matched_records}
    stranger_keys = {_encounter_key(record, "stranger") for record in stranger_records}
    recognized_people = {_person_key(record) for record in matched_records} - {None}
    by_device = Counter(_device_id(record) for record in capture_records)
    busiest_id = by_device.most_common(1)[0][0] if by_device else None
    return {
        "tracked_encounters": len(capture_keys), "face_encounters": len(face_keys),
        "body_encounters": len(body_keys), "unique_recognized_people": len(recognized_people),
        "recognized_encounters": len(matched_keys), "stranger_encounters": len(stranger_keys),
        "recognized_capture_tracks": len(matched_keys & face_keys),
        "recognition_coverage_percent": round(len(matched_keys & face_keys) / len(face_keys) * 100, 1)
        if face_keys else None,
        "busiest_capture_device": device_names.get(busiest_id, f"Device {busiest_id}") if busiest_id else None,
    }


async def load_health() -> dict:
    """Load live device health and box clock in the established box call order."""
    configs, states, tasks = await _device_health()
    return {"devices": _device_rows(configs, states, tasks), "tasks_total": len(tasks.get("list") or []),
            "clock": await _clock()}


async def previous_totals(day: date) -> dict:
    start, end = day.strftime("%Y-%m-%d 00:00:00"), day.strftime("%Y-%m-%d 23:59:59")
    matched = await _first_page(_history_body(start, end, MATCHED, 1))
    strangers = await _first_page(_history_body(start, end, STRANGER, 1))
    captures = await _first_page(_capture_body(start, end, 1))
    return {"previous_matched": int(matched.get("total_count") or 0),
            "previous_strangers": int(strangers.get("total_count") or 0),
            "previous_captures": int(captures.get("total_count") or 0)}


async def load_activity(day: date, device_names: dict[str, str]) -> dict:
    """Load one day's activity and insights using the original paged box computation."""
    current_start, current_end = day.strftime("%Y-%m-%d 00:00:00"), day.strftime("%Y-%m-%d 23:59:59")
    current_matched = await _collect_history(_history_body(current_start, current_end, MATCHED))
    current_strangers = await _collect_history(_history_body(current_start, current_end, STRANGER))
    current_captures = await _collect_history(_capture_body(current_start, current_end))
    previous_day = day.fromordinal(day.toordinal() - 1)
    previous = await previous_totals(previous_day)
    matched_records, stranger_records, capture_records = (
        current_matched["records"], current_strangers["records"], current_captures["records"])
    sample_records = [
        *[{**record, "additional": {**(record.get("additional") or {}), "alarm_minor": MATCHED}}
          for record in matched_records],
        *[{**record, "additional": {**(record.get("additional") or {}), "alarm_minor": STRANGER}}
          for record in stranger_records],
    ]
    insights = _sample_metrics(sample_records, device_names)
    insights.update(_encounter_metrics(capture_records, matched_records, stranger_records, device_names))
    insights["analysis_sampled"] = len(sample_records) + len(capture_records)
    insights["analysis_limited"] = (
        current_matched["limited"] or current_strangers["limited"] or current_captures["limited"])
    return {
        "activity": {
            "matched": current_matched["total"], "strangers": current_strangers["total"],
            "captures": current_captures["total"],
            "face_captures": sum(1 for r in capture_records if _find(r, {"alarm_minor"}) == "face_capture"),
            "body_captures": sum(1 for r in capture_records if _find(r, {"alarm_minor"}) == "body_capture"),
            "capture_breakdown_limited": current_captures["limited"], **previous,
        },
        "insights": insights,
    }
