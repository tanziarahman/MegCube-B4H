"""Live events pushed by the box (HTTP push / websocket) and forwarded to the frontend."""
from typing import Any

from pydantic import BaseModel


class LiveEvent(BaseModel):
    id: str
    source: str                  # "push" or "ws"
    device_sn: str | None = None
    time_ms: int = 0
    major: str | None = None     # e.g. face_basic_business
    minor: str | None = None     # e.g. face_comparison_successful
    images: list[str] = []       # file names served from /media/<name>
    raw: dict[str, Any] = {}
