"""Recognition records and the face-library person list."""
from typing import Literal

from fastapi import APIRouter, Query

from core import BOX_MAX_PAGE_SIZE, RECOG_MAJOR, box, to_ms

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
    return await box.call("POST", "/device_alarm/alarm_history", {
        "offset": (page - 1) * size,
        "size": size,
        "query_condition": {
            "start_time": str(to_ms(start)),
            "end_time": str(to_ms(end)),
            "alarm_type": [{"major_type": RECOG_MAJOR, "minor_type": [minor]}],
        },
    })


@router.get("/api/people")
async def people():
    """Everyone currently in the box's face library (id + name only).

    The frontend uses this to drop recognition records of people who have been deleted:
    the box keeps its alarm history even after a person is removed from the library.
    Pages through /face_manager/person/query in chunks the box accepts.
    """
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
    return {"total_count": len(out), "person_list": out}
