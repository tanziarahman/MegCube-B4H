"""Shared pieces: the box connection, config, and small helpers used by every router."""
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import HTTPException

from b4h import B4HClient

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("b4h")

box = B4HClient(
    os.getenv("B4H_BASE_URL", "https://192.168.90.200"),
    os.getenv("B4H_USER", "admin"),
    os.getenv("B4H_PASS", "Shohan@98"),
)

# Recognitions and captures are stored on the box as alarms of this major type.
RECOG_MAJOR = os.getenv("RECOG_MAJOR", "face_basic_business")
BOX_MAX_PAGE_SIZE = 30  # the box refuses more than 30 records per request


def to_ms(value: str) -> int:
    """'YYYY-MM-DD HH:mm:ss' in this PC's local time -> epoch milliseconds."""
    try:
        return int(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    except ValueError:
        raise HTTPException(422, f"Bad time '{value}', expected YYYY-MM-DD HH:mm:ss")