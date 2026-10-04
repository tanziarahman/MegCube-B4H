from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from core import box, box_image, is_box_image_path

router = APIRouter()


@router.get("/api/devices")
async def devices():
    """Camera id + name, used by the Recognition/Capture pages to show camera names.
    (Only id and name: the box's device_config also holds the RTSP passwords.)"""
    config = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100}) or []
    return [{"device_id": d.get("device_id"), "device_name": d.get("device_name")} for d in config]


@router.get("/api/image")
async def image(uri: str):
    """Proxy a record or face-library image from the box (the browser can't send the box session cookie)."""
    if not is_box_image_path(uri):
        raise HTTPException(400, "Not an image path")
    found = await box_image(uri)
    if found is None:
        raise HTTPException(404, "Image not found on the box")
    content, media_type = found
    return Response(content, media_type=media_type, headers={"Cache-Control": "max-age=86400"})
