"""Recognition records and the face-library person list."""
import time
from typing import Literal, get_args

from fastapi import APIRouter, Path, Query

from core import (BOX_MAX_PAGE_SIZE, PEOPLE_CACHE_SECONDS, RECOG_MAJOR, alarm_history_page, box,
                  people_cache, time_range)

router = APIRouter()

# Only minor types the box lists in GET /device_alarm/alarm_cap. An unknown one crashes the box's web server.
RecognitionMinor = Literal["face_comparison_successful", "stranger"]


@router.get("/api/recognition")
async def recognition(
    start: str,
    end: str,
    minor: RecognitionMinor = "face_comparison_successful",
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=BOX_MAX_PAGE_SIZE),
):
    """One page of recognition records, as the box returns them (the frontend maps the fields)."""
    start_ms, end_ms = time_range(start, end)
    return await alarm_history_page({
        "offset": (page - 1) * size,
        "size": size,
        "query_condition": {
            "start_time": start_ms,
            "end_time": end_ms,
            "alarm_type": [{"major_type": RECOG_MAJOR, "minor_type": [minor]}],
            # Sent by the box's own Records page (copied from its devtools payload). Without it the
            # box may return a trimmed record; with de_dup 0 every record comes back, un-merged.
            "ext": {"query_type": 0, "de_dup": 0},
        },
    })


@router.delete("/api/recognition/{alarm_id}")
async def delete_recognition(alarm_id: int = Path(..., ge=1)):
    """Permanently delete one recognition record on the box.

    Same request the box's own Records page sends (copied from its devtools payload):
    DELETE /device_alarm/alarm_history with the record's alarm_id in id_list.
    """
    await box.call("DELETE", "/device_alarm/alarm_history", {
        "condition": {
            "type": "alarm_id",
            "id_list": [alarm_id],
            "alarm_type": [{"major_type": RECOG_MAJOR, "minor_type": list(get_args(RecognitionMinor))}],
        },
    })
    return {"deleted": alarm_id}


@router.get("/api/people")
async def people():
    """Everyone currently in the box's face library (id + name only).

    The frontend uses this to drop recognition records of people who have been deleted:
    the box keeps its alarm history even after a person is removed from the library.
    Pages through /face_manager/person/query in chunks the box accepts.
    Kept for PEOPLE_CACHE_SECONDS (default 60 s) because a big library takes many box requests;
    adding/editing/deleting a person through this backend clears the copy immediately.
    """
    if people_cache["data"] is not None and time.monotonic() - people_cache["at"] < PEOPLE_CACHE_SECONDS:
        return people_cache["data"]

    out: list[dict] = []
    offset = 0
    while True:
        data = await box.call("POST", "/face_manager/person/query", {
            "offset": offset,
            "size": BOX_MAX_PAGE_SIZE,
            "get_feature": False,  # features are large and not needed here
        }) or {}
        batch = data.get("person_list") or []
        out += [
            {
                "person_id": str(p.get("person_id", "")),
                "name": (p.get("person_info") or {}).get("name", ""),
            }
            for p in batch
        ]
        offset += len(batch)
        if not batch or offset >= int(data.get("total_count") or 0):
            break
    result = {"total_count": len(out), "person_list": out}
    people_cache.update(at=time.monotonic(), data=result)
    return result