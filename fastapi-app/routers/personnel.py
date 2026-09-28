"""Face-library groups and personnel management."""
import json

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from core import BOX_MAX_PAGE_SIZE, box

router = APIRouter()


def _extract_image_uri(val: Any) -> str | None:
    """Extract a string image URI from various potential box data formats."""
    if not val:
        return None
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return (
            val.get("image_uri")
            or val.get("uri")
            or val.get("url")
            or val.get("value")
            or val.get("image_data")
        )
    if isinstance(val, list) and val:
        return _extract_image_uri(val[0])
    return None


def _normalize_person(person: dict) -> dict:
    """Ensure face_image1 is extracted as a string URI if present in any common box field format."""
    if not isinstance(person, dict):
        return person

    res = dict(person)
    img = (
        _extract_image_uri(person.get("face_image1"))
        or _extract_image_uri(person.get("face_image"))
        or _extract_image_uri(person.get("face_images"))
        or _extract_image_uri(person.get("face_data"))
        or _extract_image_uri(person.get("image_data"))
    )

    if not img:
        for k in ("person_info", "face_info", "face_spec"):
            nested = person.get(k)
            if isinstance(nested, dict):
                img = (
                    _extract_image_uri(nested.get("face_image1"))
                    or _extract_image_uri(nested.get("image_uri"))
                    or _extract_image_uri(nested.get("face_data"))
                )
                if img:
                    break

    if img:
        res["face_image1"] = img
    return res


@router.get("/api/personnel/groups")
async def personnel_groups():
    """Return the face-library groups available for personnel assignment."""
    data = await box.call("POST", "/face_manager/groups/query") or {}
    return {"groups": data.get("groups") or []}


@router.get("/api/personnel")
async def personnel(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=BOX_MAX_PAGE_SIZE),
    get_feature: bool = True,
):
    """Return one page of people with their profile and face-image metadata."""
    data = await box.call("POST", "/face_manager/person/query", {
        "offset": (page - 1) * size,
        "size": size,
        "get_feature": get_feature,
    }) or {}
    person_list = data.get("person_list") or []
    return {
        "page": page,
        "size": size,
        "total_count": data.get("total_count", data.get("count", 0)),
        "person_list": [_normalize_person(p) for p in person_list],
    }


@router.post("/api/personnel", status_code=201)
async def add_personnel(
    name: str = Form(..., min_length=1),
    photo: UploadFile = File(...),
    group_ids: str = Form("[]"),
    birthday: str = Form(""),
    gender: int = Form(0),
    code: str = Form(""),
    person_id: str = Form(""),
    remarks: str = Form(""),
    person_type: str = Form(""),
):
    """Create a face-library person and upload the reference photo."""
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(415, "photo must be an image")
    try:
        parsed_group_ids = json.loads(group_ids)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "group_ids must be a JSON array") from exc
    if not isinstance(parsed_group_ids, list) or not all(isinstance(value, (str, int)) for value in parsed_group_ids):
        raise HTTPException(422, "group_ids must be a JSON array of ids")

    image = await photo.read()
    info = {
        "birthday": birthday,
        "code": code,
        "gender": gender,
        "id": person_id,
        "name": name,
        "remarks": remarks,
        "type": person_type,
    }
    data = {
        "person_info": json.dumps(info),
        "group_ids": json.dumps([str(value) for value in parsed_group_ids]),
    }
    result = await box.upload(
        "/face_manager/person/add",
        files={"face_image1": (photo.filename or "face.jpg", image, photo.content_type)},
        data=data,
    )
    return result or {"message": "created"}


@router.put("/api/personnel/{person_id}")
async def update_personnel(
    person_id: str,
    name: str = Form(..., min_length=1),
    photo: UploadFile | None = File(None),
    group_ids: str = Form("[]"),
    birthday: str = Form(""),
    gender: int = Form(0),
    code: str = Form(""),
    remarks: str = Form(""),
    person_type: str = Form(""),
):
    """Update a face-library person, optionally replacing the reference photo."""
    try:
        parsed_group_ids = json.loads(group_ids)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "group_ids must be a JSON array") from exc
    if not isinstance(parsed_group_ids, list) or not all(isinstance(value, (str, int)) for value in parsed_group_ids):
        raise HTTPException(422, "group_ids must be a JSON array of ids")

    info = {
        "birthday": birthday,
        "code": code,
        "gender": gender,
        "id": person_id,
        "name": name,
        "remarks": remarks,
        "type": person_type,
    }
    files = {}
    if photo:
        if not photo.content_type or not photo.content_type.startswith("image/"):
            raise HTTPException(415, "photo must be an image")
        files["face_image1"] = (photo.filename or "face.jpg", await photo.read(), photo.content_type)
    return await box.upload(
        "/face_manager/person/modify",
        files=files,
        data={"person_info": json.dumps(info), "group_ids": json.dumps([str(value) for value in parsed_group_ids])},
        method="PUT",
    )


@router.delete("/api/personnel/{person_id}")
async def delete_personnel(person_id: str):
    """Delete a person from the box face library."""
    return await box.call("POST", "/face_manager/person/delete", {"person_id": person_id})