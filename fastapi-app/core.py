"""Shared pieces: the box connection, config, and small helpers used by every router."""
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import HTTPException

from b4h import B4HClient, B4HError

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("b4h")

box = B4HClient(
    os.getenv("B4H_BASE_URL", "https://192.168.90.200"),
    os.getenv("B4H_USER", "admin"),
    os.getenv("B4H_PASS", ""),  # set B4H_PASS in .env
)

# Recognitions and captures are stored on the box as alarms of this major type.
RECOG_MAJOR = os.getenv("RECOG_MAJOR", "face_basic_business")
BOX_MAX_PAGE_SIZE = 30  # the box refuses more than 30 records per request
BOX_GENERAL_ERROR = 1073741825  # the box's catch-all error code


def to_ms(value: str) -> int:
    """'YYYY-MM-DD HH:mm:ss' in this PC's local time -> epoch milliseconds."""
    try:
        return int(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    except ValueError:
        raise HTTPException(422, f"Bad time '{value}', expected YYYY-MM-DD HH:mm:ss")


def time_range(start: str, end: str) -> tuple[str, str]:
    """Both times -> epoch ms strings (as the box expects). Refuses a start later than the end."""
    start_ms, end_ms = to_ms(start), to_ms(end)
    if start_ms > end_ms:
        raise HTTPException(422, "start must be before end")
    return str(start_ms), str(end_ms)


async def alarm_history_page(body: dict) -> dict:
    """POST /device_alarm/alarm_history, but asking for a page past the last record returns an
    empty page instead of the box's 'general' error (the box answers that error in this case)."""
    try:
        return await box.call("POST", "/device_alarm/alarm_history", body) or {}
    except B4HError as e:
        if e.code != BOX_GENERAL_ERROR or not body.get("offset"):
            raise
        # Is the page really past the end? Ask for the total with the same filter.
        first = await box.call("POST", "/device_alarm/alarm_history", {**body, "offset": 0, "size": 1}) or {}
        total = int(first.get("total_count") or 0)
        if body["offset"] < total:
            raise  # a real error, not just an empty page
        return {"total_count": total, "return_count": 0, "list": []}