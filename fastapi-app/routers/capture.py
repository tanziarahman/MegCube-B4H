"""Capture records (face_capture / body_capture)."""
from typing import Literal

from fastapi import APIRouter, Query

from core import BOX_MAX_PAGE_SIZE, RECOG_MAJOR, box, to_ms

router = APIRouter()

CaptureTargetType = Literal["all", "face", "body"]

# UI "Target Type" -> minor_type(s) sent to the box for the face_basic_business
# entry. Confirmed from the devtools payload for "all types".
_CAPTURE_MINORS: dict[CaptureTargetType, list[str]] = {
    "all": ["face_capture", "body_capture"],
    "face": ["face_capture"],
    "body": ["body_capture"],
}

# The box rejects the request (code 1073741831 "not_support") unless a second
# alarm_type entry for "structure" is also present, alongside face_basic_business.
# Confirmed via "View source" on the raw request payload. We don't have a payload
# showing this entry changing when target_type != "all", so it's kept constant.
_STRUCTURE_ALARM_TYPE = {
    "major_type": "structure",
    "minor_type": ["face", "pedestrian", "vehicle", "non_motor", "plate"],
}

# Attribute keys on faces[0] / pedestrians[0] that are just bookkeeping, not
# display attributes -- stripped out of the "attributes" dict we return.
_DETAIL_NOISE = {"image_data", "link_info", "alarm_linkage", "track_id", "track_id_times"}


def _normalize_capture(alarm: dict) -> dict:
    """Flatten one box alarm record (face_capture or body_capture) into one
    row for the Capture Record table: target image, panoramic, device,
    time, track id, type, and the type-specific attributes.
    """
    additional = alarm.get("additional") or {}
    global_info = alarm.get("global_info") or {}
    minor = additional.get("alarm_minor")  # "face_capture" | "body_capture"

    if minor == "face_capture":
        target_type = "face"
        targets = alarm.get("faces") or [{}]
    else:
        target_type = "body"
        targets = alarm.get("pedestrians") or [{}]
    target = targets[0] if targets else {}

    target_image = ((target.get("image_data") or {}).get("value") or "") or None

    full_images = alarm.get("full_images") or [{}]
    panoramic_value = ((full_images[0].get("image_data") or {}).get("value") or "")
    panoramic_image = panoramic_value or None  # box sends "" when there's no panoramic shot

    attributes = {k: v for k, v in target.items() if k not in _DETAIL_NOISE}

    return {
        "alarm_id": additional.get("alarm_id"),
        "track_id": target.get("track_id"),
        "target_type": target_type,
        "device_id": additional.get("device_id"),
        "capture_time_ms": global_info.get("time_ms"),
        "target_image": target_image,
        "panoramic_image": panoramic_image,
        "attributes": attributes,
    }


@router.get("/api/capture")
async def capture(
    start: str,
    end: str,
    target_type: CaptureTargetType = "all",
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=BOX_MAX_PAGE_SIZE),
):
    """One page of capture records (face_capture / body_capture), flattened
    for the frontend. Capture Device filtering isn't done server-side yet --
    unconfirmed whether the box accepts a device_id filter in
    query_condition, so the frontend joins device_id -> device_name via /api/devices.
    """
    data = await box.call("POST", "/device_alarm/alarm_history", {
        "offset": (page - 1) * size,
        "size": size,
        "query_condition": {
            "start_time": str(to_ms(start)),
            "end_time": str(to_ms(end)),
            "alarm_type": [
                {"major_type": RECOG_MAJOR, "minor_type": _CAPTURE_MINORS[target_type]},
                _STRUCTURE_ALARM_TYPE,
            ],
        },
    })
    return {
        "total_count": data.get("total_count", 0),
        "return_count": data.get("return_count", 0),
        "list": [_normalize_capture(a) for a in data.get("list", [])],
    }
