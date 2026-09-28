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
    for path, params in (("/web/" + uri.lstrip("./"), None), ("/device_storage/get_image", {"image_uri": uri})):
        try:
            content, media_type = await box.get_bytes(path, params)
            if media_type == "application/octet-stream":  # the box doesn't label its JPEGs
                media_type = mimetypes.guess_type(uri)[0] or media_type
            return Response(content, media_type=media_type, headers={"Cache-Control": "max-age=86400"})
        except httpx.HTTPStatusError:
            continue
    raise HTTPException(404, "Image not found on the box")
