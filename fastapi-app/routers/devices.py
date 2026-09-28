"""Device management page: camera list with connection status."""
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter

from core import box

router = APIRouter()

# channel_type values seen on the box. Only 1 is confirmed (the box UI shows it as "Video").
_CHANNEL_TYPES = {1: "Video"}

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
