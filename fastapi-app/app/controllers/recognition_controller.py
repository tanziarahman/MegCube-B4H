"""
Recognition logic: query the box's alarm history, page/merge results, map records to RecognitionRecord.

Box limits (seen in DevTools): max 30 records per request, and ONE major + ONE minor type per query.
"""
from collections import OrderedDict
from datetime import datetime
from urllib.parse import quote

from fastapi import HTTPException

from app.core import config
from app.core.b4h import b4h, b4h_call
from app.models.recognition import RecognitionPage, RecognitionQuery, RecognitionRecord
from app.utils.json_extract import (
    collect_images, find, find_all, find_list, find_total, to_score, to_str,
)

RESULT_TO_MINOR = {"matched": config.RECOG_MINOR_MATCHED, "stranger": config.RECOG_MINOR_STRANGER}
MINOR_TO_RESULT = {v: k for k, v in RESULT_TO_MINOR.items()}

# Recently listed records, so the detail endpoint can return one by id (the box has no get-by-id).
_recent: "OrderedDict[str, RecognitionRecord]" = OrderedDict()
_RECENT_MAX = 2000


# ------------------------------------------------------------------ box access
async def query_box(minor: str, start_ms: int, end_ms: int, offset: int, size: int) -> tuple[list[dict], int]:
    """One call to /device_alarm/alarm_history for one minor type."""
    body = {
        "offset": offset,
        "size": min(size, config.BOX_MAX_PAGE_SIZE),
        "query_condition": {
            "start_time": str(start_ms),
            "end_time": str(end_ms),
            "alarm_type": [{"major_type": config.RECOG_MAJOR, "minor_type": [minor]}],
        },
    }
    resp = await b4h_call("POST", "/device_alarm/alarm_history", body)
    rows = find_list(resp)
    return rows, find_total(resp, len(rows))


async def _fetch_first(minor: str, start_ms: int, end_ms: int, count: int) -> tuple[list[dict], int]:
    """The newest `count` records of one minor type, 30 per request."""
    rows: list[dict] = []
    total, offset = 0, 0
    while offset < count:
        chunk, total = await query_box(minor, start_ms, end_ms, offset, config.BOX_MAX_PAGE_SIZE)
        rows.extend(chunk)
        if len(chunk) < config.BOX_MAX_PAGE_SIZE:
            break
        offset += config.BOX_MAX_PAGE_SIZE
    return rows[:count], total


# ------------------------------------------------------------------ mapping
def image_url(uri: str | None) -> str | None:
    """Box image URI -> URL the frontend can load through our image proxy."""
    if not uri:
        return None
    if uri.startswith(("data:", "http://", "https://")):
        return uri
    return f"/api/recognition/image?uri={quote(uri, safe='')}"


def _pick_images(images: list[dict]) -> tuple[str | None, str | None, str | None]:
    """Decide which image is the face crop, the panorama and the library (base) photo."""
    face = scene = library = None
    for img in images:
        t = img["type"]
        if library is None and any(w in t for w in ("library", "base", "register", "person", "db")):
            library = img["uri"]
        elif scene is None and any(w in t for w in ("scene", "panor", "background", "full", "bg")):
            scene = img["uri"]
        elif face is None and any(w in t for w in ("face", "crop", "snap", "target", "small")):
            face = img["uri"]
    # Unlabelled images: assume order face crop, panorama, library photo.
    rest = [i["uri"] for i in images if i["uri"] not in (face, scene, library)]
    face = face or (rest.pop(0) if rest else None)
    scene = scene or (rest.pop(0) if rest else None)
    library = library or (rest.pop(0) if rest else None)
    return face, scene, library


def to_record(row: dict, minor: str, include_raw: bool = False) -> RecognitionRecord:
    time_ms = find(row, ("time_ms", "capture_time", "alarm_time", "timestamp", "time"))
    try:
        time_ms = int(time_ms)
        if time_ms < 10**12:                         # seconds -> milliseconds
            time_ms *= 1000
    except (TypeError, ValueError):
        time_ms = None

    minor_found = to_str(find(row, ("alarm_minor", "minor_type"))) or minor
    face, scene, library = _pick_images(collect_images(row))
    groups = [str(g) for g in find_all(row, ("group_name", "group_names", "groups_name"))]
    rec_id = to_str(find(row, ("data_uuid", "alarm_id", "record_id", "uuid", "id"))) \
        or f"{find(row, ('device_id',), 'box')}-{time_ms}"

    return RecognitionRecord(
        id=rec_id,
        time_ms=time_ms,
        time=datetime.fromtimestamp(time_ms / 1000, config.TIMEZONE).isoformat() if time_ms else None,
        result=MINOR_TO_RESULT.get(minor_found, "unknown"),  # type: ignore[arg-type]
        camera_id=to_str(find(row, ("channel_id", "camera_id", "device_channel_id", "source_id"))),
        camera_name=to_str(find(row, ("channel_name", "camera_name", "device_name", "source_name"))),
        person_id=to_str(find(row, ("person_id", "face_id", "person_uuid"))),
        person_name=to_str(find(row, ("person_name", "name"))),
        group_names=list(dict.fromkeys(groups)),     # de-duplicate, keep order
        similarity=to_score(find(row, ("similarity", "score", "compare_score", "match_score"))),
        liveness=to_score(find(row, ("living_score", "liveness", "live_score", "living_fraction"))),
        track_id=to_str(find(row, ("track_id", "trackid", "trace_id"))),
        face_image=image_url(face),
        scene_image=image_url(scene),
        library_image=image_url(library),
        raw=row if include_raw else None,
    )


def _remember(records: list[RecognitionRecord]) -> None:
    for r in records:
        _recent[r.id] = r
        _recent.move_to_end(r.id)
    while len(_recent) > _RECENT_MAX:
        _recent.popitem(last=False)


# ------------------------------------------------------------------ actions
async def list_records(q: RecognitionQuery) -> RecognitionPage:
    size = max(1, min(q.size, config.BOX_MAX_PAGE_SIZE))
    offset = (q.page - 1) * size

    if q.result in RESULT_TO_MINOR:
        minor = RESULT_TO_MINOR[q.result]
        rows, total = await query_box(minor, q.start_ms, q.end_ms, offset, size)
        records = [to_record(r, minor, q.include_raw) for r in rows]
    else:
        # "All": one minor type per box query, so fetch both and merge newest-first.
        need = offset + size
        if need > config.MERGE_MAX_DEPTH:
            raise HTTPException(400, "Page too deep for 'all'. Narrow the time range or choose matched/stranger.")
        records, total = [], 0
        for minor in RESULT_TO_MINOR.values():
            rows, t = await _fetch_first(minor, q.start_ms, q.end_ms, need)
            records += [to_record(r, minor, q.include_raw) for r in rows]
            total += t
        records.sort(key=lambda r: r.time_ms or 0, reverse=True)
        records = records[offset:offset + size]

    # No confirmed box filter for camera/name yet, so these narrow the current page only.
    note = None
    if q.camera_id or q.name:
        before = len(records)
        if q.camera_id:
            records = [r for r in records if r.camera_id == q.camera_id]
        if q.name:
            n = q.name.lower()
            records = [r for r in records if n in (r.person_name or "").lower() or n in (r.person_id or "").lower()]
        note = f"Camera/name filter applied to this page only ({len(records)} of {before})."

    _remember(records)
    return RecognitionPage(items=records, total=total, page=q.page, size=size,
                           has_more=offset + size < total, note=note)


def get_record(record_id: str) -> RecognitionRecord:
    rec = _recent.get(record_id)
    if rec is None:
        raise HTTPException(404, "Record not in recent results. Load it from the list first.")
    return rec


async def get_image(uri: str) -> tuple[bytes, str]:
    """Record images live under /web/<uri>; older firmware serves them via /device_storage/get_image."""
    try:
        return await b4h.get_bytes("/web/" + uri.lstrip("./"))
    except Exception:
        try:
            return await b4h.get_bytes("/device_storage/get_image", {"image_uri": uri})
        except Exception:
            raise HTTPException(404, "Image not found on the box")


async def alarm_types() -> dict:
    cap = await b4h_call("GET", "/device_alarm/alarm_cap")
    return {"configured": RESULT_TO_MINOR, "box_alarm_cap": cap}


async def raw_sample(result: str, start_ms: int, end_ms: int) -> dict:
    rows, total = await query_box(RESULT_TO_MINOR[result], start_ms, end_ms, 0, 1)
    return {"total": total, "record": rows[0] if rows else None}
