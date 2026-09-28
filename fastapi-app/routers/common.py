"""Device list and image proxy, used by both the Recognition and Capture pages."""
import mimetypes

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from core import box

router = APIRouter()


@router.get("/api/devices")
async def devices():
    """Cameras configured on the box, used for the device filter (id + name only: the raw config holds RTSP passwords)."""
    data = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100})
    return [{"device_id": d.get("device_id"), "device_name": d.get("device_name")} for d in data or []]


@router.get("/api/image")
async def image(uri: str):
    """Proxy a record image from the box (the browser can't send the box session cookie)."""
    # The box serves both face-library (/home/appdata/...) and alarm (./record_...) images
    # via /device_storage/get_image?image_uri=...
    paths = [
        ("/device_storage/get_image", {"image_uri": uri}),
    ]
    if uri.startswith("/"):
        paths.append((uri, None))
    paths.append(("/web/" + uri.lstrip("./"), None))

    for path, params in paths:
        try:
            content, media_type = await box.get_bytes(path, params)
            # Check if response is empty or a JSON/HTML error payload instead of an image
            stripped = content.lstrip()
            if not content or stripped.startswith(b"{") or stripped.startswith(b"<!") or stripped.startswith(b"<html"):
                continue

            if media_type in ("application/octet-stream", None, "") or not media_type.startswith("image/"):
                guessed = mimetypes.guess_type(uri)[0]
                media_type = guessed if guessed and guessed.startswith("image/") else "image/jpeg"

            return Response(content, media_type=media_type, headers={"Cache-Control": "max-age=86400"})
        except httpx.HTTPStatusError:
            continue
    raise HTTPException(404, "Image not found on the box")

