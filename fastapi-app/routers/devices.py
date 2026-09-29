"""Device management page: camera list with connection status, adding and deleting cameras."""
import asyncio
from typing import Literal
from urllib.parse import quote, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from core import box

router = APIRouter()

# Adding a camera = read the used ids, then create with a free one. Two adds at the same moment
# could pick the same id, so adds run one at a time.
_add_lock = asyncio.Lock()

# channel_type values. The box has two device types: Video and Picture.
# 1 = Video is confirmed from device_config; 2 = Picture is assumed (not yet seen in a response).
_CHANNEL_TYPES = {1: "Video", 2: "Picture"}

# device_state.state values. Only 0 is confirmed (the box UI shows it as "Online").
# Anything else is reported as offline together with its code, so nothing is silently mislabelled.
_ONLINE_STATE = 0


def _mask_url(url: str) -> str:
    """rtsp://user:secret@host/... -> rtsp://user:****@host/... (the password never leaves the backend)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    if parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"{parts.username}:****@{host}" if parts.username else host
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@router.get("/api/devices/detail")
async def devices_detail():
    """Every camera configured on the box with its type, protocol, masked address and status.

    Combines /device_access/device_config (settings) and /device_access/device_state (status),
    the same two calls the box's own Device page makes. RTSP passwords are stripped here.
    """
    config = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100}) or []
    states = await box.call("POST", "/device_access/device_state", {"offset": 0, "size": 100}) or []
    state_by_id = {s.get("device_id"): s for s in states}

    out = []
    for d in config:
        rtsp = d.get("rtsp_param") or {}
        st = state_by_id.get(d.get("device_id")) or {}
        state = st.get("state")
        channels = st.get("channels") or []
        out.append({
            "device_id": d.get("device_id"),
            "device_name": d.get("device_name"),
            "device_type": _CHANNEL_TYPES.get(d.get("channel_type"), f"Type {d.get('channel_type')}"),
            "protocol": d.get("proto"),
            "manufacturer": d.get("manufacturer"),
            "address": _mask_url(rtsp.get("url") or ""),
            "online": state == _ONLINE_STATE,
            "state_code": state,  # raw code, so unknown states can be identified later
            "pulling_stream": any(c.get("pull_stream") for c in channels),
        })
    return out


# ---------- add a camera ----------

class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: Literal["video", "picture"] = "video"
    protocol: Literal["rtsp"] = "rtsp"
    url: str = Field(min_length=8, max_length=512)        # rtsp://host:port/path (credentials optional)
    user: str = Field("", max_length=64)
    password: str = Field("", max_length=128)


def _rtsp_url(url: str, user: str, password: str) -> tuple[str, str, str]:
    """Build the URL the box stores: rtsp://user:password@host:port/path.

    Credentials may come from the fields or already be inside the pasted URL; the fields win.
    Returns (url_with_credentials, user, password).
    """
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "rtsp" or not parts.hostname:
        raise HTTPException(422, "RTSP address must look like rtsp://host:port/path")
    user = user or (parts.username or "")
    password = password or (parts.password or "")
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}" if user else host
    return urlunsplit(("rtsp", netloc, parts.path, parts.query, parts.fragment)), user, password


@router.post("/api/devices", status_code=201)
async def create_device(body: DeviceIn):
    """Add a camera to the box.

    Same request the box's own "New device" dialog sends (copied from its devtools payload):
    POST /device_access/device {device_id, device_name, proto, rtsp_param: {user, password, url}}.
    Like the box UI, the new camera gets the lowest device_id that isn't in use.
    """
    if body.type != "video":
        # Only the Video "New device" request has been captured; a Picture device's payload is unknown.
        raise HTTPException(501, "Adding Picture devices isn't supported yet")

    url, user, password = _rtsp_url(body.url, body.user, body.password)
    async with _add_lock:
        config = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100}) or []
        used = {d.get("device_id") for d in config}
        if any((d.get("device_name") or "").strip().lower() == body.name.strip().lower() for d in config):
            raise HTTPException(409, f"A device named '{body.name}' already exists")
        device_id = next(i for i in range(1, len(used) + 2) if i not in used)

        await box.call("POST", "/device_access/device", {
            "device_id": device_id,
            "device_name": body.name.strip(),
            "proto": body.protocol,
            "rtsp_param": {"user": user, "password": password, "url": url},
        })
    return {"device_id": device_id}


# ---------- delete a camera ----------

@router.delete("/api/devices/{device_id}")
async def delete_device(device_id: int = Path(..., ge=1)):
    """Remove a camera from the box.

    Same request the box's own Device page sends (copied from its devtools payload):
    DELETE /device_access/device {device_id}. Checks the id exists first, so a stale page
    can't send the box a delete for something that isn't there.
    """
    config = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100}) or []
    if not any(d.get("device_id") == device_id for d in config):
        raise HTTPException(404, f"Device #{device_id} is not configured on the box")
    await box.call("DELETE", "/device_access/device", {"device_id": device_id})
    return {"deleted": device_id}