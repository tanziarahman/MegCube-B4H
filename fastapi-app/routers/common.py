import json
import mimetypes

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from core import box

router = APIRouter()

# Only image files under these box locations may be proxied (the backend holds the admin session).
_ALLOWED_PREFIXES = ("./record_", "record_", "./group/", "group/", "/home/appdata/")
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
_SESSION_LOST = 512


@router.get("/api/devices")
async def devices():
    """Camera id + name, used by the Recognition/Capture pages to show camera names.
    (Only id and name: the box's device_config also holds the RTSP passwords.)"""
    config = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100}) or []
    return [{"device_id": d.get("device_id"), "device_name": d.get("device_name")} for d in config]


def _looks_like_error(content: bytes) -> bool:
    s = content.lstrip()
    return not content or s.startswith(b"{") or s.startswith(b"<!") or s.startswith(b"<html")


def _session_lost(content: bytes) -> bool:
    try:
        return json.loads(content).get("code") == _SESSION_LOST
    except (ValueError, AttributeError):
        return False


@router.get("/api/image")
async def image(uri: str):
    """Proxy a record or face-library image from the box (the browser can't send the box session cookie)."""
    if ".." in uri or not uri.startswith(_ALLOWED_PREFIXES) or not uri.lower().endswith(_IMAGE_EXTS):
        raise HTTPException(400, "Not an image path")

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

            return Response(content, media_type=media_type, headers={"Cache-Control": "max-age=86400"})
        except httpx.HTTPStatusError:
            continue
    raise HTTPException(404, "Image not found on the box")