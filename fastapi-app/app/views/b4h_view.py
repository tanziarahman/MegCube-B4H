"""Direct box endpoints you already had (device info, cameras, groups, persons, raw passthrough)."""
from fastapi import APIRouter, File, Form, UploadFile

from app.controllers import device_controller, person_controller
from app.core.b4h import b4h_call

router = APIRouter(prefix="/api/b4h", tags=["b4h"])


@router.get("/video-cap")
async def video_cap():
    return await b4h_call("GET", "/media_video/cap")


@router.get("/device-info")
async def device_info():
    return await b4h_call("GET", "/device_maintenance/device_info")


@router.get("/cameras")
async def cameras():
    return await device_controller.raw_cameras()


@router.post("/groups")
async def person_groups():
    return await b4h_call("POST", "/face_manager/groups/query", {})


@router.post("/persons")
async def create_person(
    name: str = Form(...),
    photo: UploadFile = File(...),
    group_id: str | None = Form(None),
    remarks: str | None = Form(None),
):
    return await person_controller.create_person(name, photo, group_id, remarks)


@router.post("/raw")
async def raw(body: dict):
    """Explore any box endpoint: {"method":"GET","path":"/device_alarm/alarm_cap"}"""
    return await b4h_call(body.get("method", "GET"), body["path"], body.get("body"))
