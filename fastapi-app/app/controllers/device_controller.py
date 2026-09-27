"""Cameras (capture devices) and person groups, used for filters."""
from app.core.b4h import b4h_call
from app.models.device import Camera, Group
from app.utils.json_extract import find, find_list, to_str

ONLINE_VALUES = {"1", "true", "online", "normal"}


async def list_cameras() -> list[Camera]:
    """Same two calls the box web page makes on Resource → Device."""
    config_resp = await b4h_call("POST", "/device_access/device_config", {"offset": 0, "size": 100})
    try:
        state_resp = await b4h_call("POST", "/device_access/device_state", {"offset": 0, "size": 100})
    except Exception:
        state_resp = {}

    online: dict[str, bool] = {}
    for s in find_list(state_resp):
        sid = to_str(find(s, ("device_id", "id", "channel_id")))
        if sid is not None:
            online[sid] = str(find(s, ("status", "state", "online", "device_status"))).lower() in ONLINE_VALUES

    cameras = []
    for d in find_list(config_resp):
        did = to_str(find(d, ("device_id", "id", "channel_id")))
        if did is not None:
            name = to_str(find(d, ("device_name", "name", "channel_name"))) or did
            cameras.append(Camera(id=did, name=name, online=online.get(did)))
    return cameras


async def list_groups() -> list[Group]:
    resp = await b4h_call("POST", "/face_manager/groups/query", {})
    return [Group(id=to_str(find(g, ("group_id", "id"))) or "", name=to_str(find(g, ("group_name", "name"))) or "")
            for g in find_list(resp)]


async def raw_cameras() -> dict:
    config_resp = await b4h_call("POST", "/device_access/device_config", {"offset": 0, "size": 100})
    state_resp = await b4h_call("POST", "/device_access/device_state", {"offset": 0, "size": 100})
    return {"cameras": config_resp, "status": state_resp}
