"""Recognition data as the frontend receives it. Stays stable even if the box's JSON changes."""
from typing import Any, Literal

from pydantic import BaseModel

RecognitionResult = Literal["matched", "stranger", "unknown"]


class RecognitionRecord(BaseModel):
    id: str
    time_ms: int | None = None
    time: str | None = None                  # ISO string in the portal time zone
    result: RecognitionResult = "unknown"
    camera_id: str | None = None
    camera_name: str | None = None           # "Capture Device" on the box page
    person_id: str | None = None
    person_name: str | None = None
    group_names: list[str] = []              # a person can be in several groups
    similarity: float | None = None          # 0–100
    liveness: float | None = None            # "living fraction", 0–100
    track_id: str | None = None
    face_image: str | None = None            # capture: face crop (URL)
    scene_image: str | None = None           # capture: panoramic (URL)
    library_image: str | None = None         # person: base image (URL)
    raw: dict[str, Any] | None = None        # original box record, only when include_raw=true


class RecognitionPage(BaseModel):
    items: list[RecognitionRecord]
    total: int
    page: int
    size: int
    has_more: bool
    note: str | None = None                  # e.g. "filter applied to this page only"


class RecognitionQuery(BaseModel):
    start_ms: int
    end_ms: int
    result: Literal["all", "matched", "stranger"] = "all"
    camera_id: str | None = None
    name: str | None = None
    page: int = 1
    size: int = 20
    include_raw: bool = False
