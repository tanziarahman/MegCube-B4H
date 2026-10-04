"""Shared pieces: the box connection, config, access check, and small helpers used by every router."""
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, Request

from b4h import B4HClient, B4HError

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("b4h")

BOX_BASE_URL = os.getenv("B4H_BASE_URL", "https://192.168.90.200")
box = B4HClient(
    BOX_BASE_URL,
    os.getenv("B4H_USER", "admin"),
    os.getenv("B4H_PASS", ""),  # set B4H_PASS in .env
    timeout=float(os.getenv("B4H_TIMEOUT", "15")),
)

# Recognitions and captures are stored on the box as alarms of this major type.
RECOG_MAJOR = os.getenv("RECOG_MAJOR", "face_basic_business")
BOX_MAX_PAGE_SIZE = 30  # the box refuses more than 30 records per request
BOX_GENERAL_ERROR = 1073741825  # the box's catch-all error code


# ---------- time ----------

BOX_TIMEZONE_NAME = os.getenv("BOX_TIMEZONE", "Asia/Dhaka")


def _load_timezone():
    """Times typed in the portal are in the box's time zone, not the server's (a server or Docker
    container is often set to UTC). Windows needs the `tzdata` package for this (uv add tzdata)."""
    name = os.getenv("BOX_TIMEZONE", "Asia/Dhaka")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("Time zone '%s' not found (on Windows run: uv add tzdata). Using this PC's time zone.", name)
        return None


BOX_TZ = _load_timezone()


def to_ms(value: str) -> int:
    """'YYYY-MM-DD HH:mm:ss' in the box's time zone (BOX_TIMEZONE) -> epoch milliseconds."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(422, f"Bad time '{value}', expected YYYY-MM-DD HH:mm:ss")
    if BOX_TZ is not None:
        dt = dt.replace(tzinfo=BOX_TZ)
    return int(dt.timestamp() * 1000)


def time_range(start: str, end: str) -> tuple[str, str]:
    """Both times -> epoch ms strings (as the box expects). Refuses a start later than the end."""
    start_ms, end_ms = to_ms(start), to_ms(end)
    if start_ms > end_ms:
        raise HTTPException(422, "start must be before end")
    return str(start_ms), str(end_ms)


# ---------- box helpers ----------

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


# Only image files under these box locations may be fetched (the backend holds the admin session).
_IMAGE_PREFIXES = ("./record_", "record_", "./group/", "group/", "/home/appdata/")
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
_SESSION_LOST = 512


def is_box_image_path(uri: str) -> bool:
    return ".." not in uri and uri.startswith(_IMAGE_PREFIXES) and uri.lower().endswith(_IMAGE_EXTS)


def _looks_like_error(content: bytes) -> bool:
    s = content.lstrip()
    return not content or s.startswith(b"{") or s.startswith(b"<!") or s.startswith(b"<html")


def _session_lost(content: bytes) -> bool:
    try:
        return json.loads(content).get("code") == _SESSION_LOST
    except (ValueError, AttributeError):
        return False


async def box_image(uri: str) -> tuple[bytes, str] | None:
    """(content, media type) of a record or face-library image on the box, or None when the box no
    longer has it (it rotates old records out). Used by the image proxy and the face worker."""
    # The box serves both face-library (/home/appdata/...) and alarm (./record_...) images
    # via /device_storage/get_image?image_uri=...
    paths = [("/device_storage/get_image", {"image_uri": uri})]
    if uri.startswith("/"):
        paths.append((uri, None))
    paths.append(("/web/" + uri.removeprefix("./").lstrip("/"), None))

    relogged = False
    for path, params in paths:
        try:
            session = box.session_id
            content, media_type = await box.get_bytes(path, params)
            if _session_lost(content) and not relogged:
                # Box dropped the idle session: log in again (unless another request already did)
                # and retry this path once.
                await box.relogin(session)
                relogged = True
                content, media_type = await box.get_bytes(path, params)
            if _looks_like_error(content):
                continue
            if not media_type or not media_type.startswith("image/"):
                guessed = mimetypes.guess_type(uri)[0]
                media_type = guessed if guessed and guessed.startswith("image/") else "image/jpeg"
            return content, media_type
        except httpx.HTTPStatusError:
            continue
    return None


# Short-lived copy of the whole face library (id + name) for /api/people: with a big library,
# reading it takes many box requests, and the Recognition page asks for it on every load.
PEOPLE_CACHE_SECONDS = float(os.getenv("PEOPLE_CACHE_SECONDS", "60"))
people_cache: dict = {"at": 0.0, "data": None}


def invalidate_people_cache() -> None:
    """Call after adding, editing or deleting a person."""
    people_cache["data"] = None


# ---------- access check (API key) ----------
# With API_KEY set in .env, every /api request must carry the header  X-API-Key: <key>.
# The Next.js server adds it (src/middleware.ts); browsers never see the key.
# Live video is opened by an <img> tag, which can't send headers, so its URL carries a
# signature instead (exp + sig), handed out by /api/preview/cameras.

API_KEY = os.getenv("API_KEY", "")
STREAM_LINK_SECONDS = 12 * 3600

if not API_KEY:
    log.warning("API_KEY is not set in .env: the API is open to anyone who can reach this backend")


def sign_stream(device_id: int, exp: int | None = None) -> str:
    """Query string that lets an <img> open this camera's stream until `exp`."""
    exp = exp or int(time.time()) + STREAM_LINK_SECONDS
    sig = hmac.new(API_KEY.encode(), f"{device_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"exp={exp}&sig={sig}"


def _stream_sig_ok(request: Request) -> bool:
    parts = request.url.path.strip("/").split("/")  # api / preview / {id} / stream
    if len(parts) != 4 or parts[:2] != ["api", "preview"] or parts[3] != "stream" or not parts[2].isdigit():
        return False
    exp = request.query_params.get("exp", "")
    sig = request.query_params.get("sig", "")
    if not exp.isdigit() or int(exp) < time.time():
        return False
    expected = sign_stream(int(parts[2]), int(exp)).split("sig=")[1]
    return hmac.compare_digest(sig, expected)


async def check_access(request: Request) -> None:
    """FastAPI dependency on every /api route."""
    if not API_KEY:
        return
    if hmac.compare_digest(request.headers.get("x-api-key", ""), API_KEY):
        return
    if _stream_sig_ok(request):
        return
    raise HTTPException(401, "Missing or wrong API key")