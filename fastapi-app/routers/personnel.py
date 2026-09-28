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


def _parse_group_ids(group_ids: str) -> list[str]:
    try:
        parsed = json.loads(group_ids)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "group_ids must be a JSON array") from exc
    if not isinstance(parsed, list) or not all(isinstance(value, (str, int)) for value in parsed):
        raise HTTPException(422, "group_ids must be a JSON array of ids")
    return [str(value) for value in parsed]


async def _read_photo(photo: UploadFile | None) -> tuple[bytes, UploadFile] | None:
    """Return the uploaded image, or None when the file input was left empty.

    Browsers submit an empty file input as a nameless application/octet-stream part,
    so "no photo" has to be detected by filename/size rather than by `photo is None`.
    """
    if photo is None or not photo.filename:
        return None
    image = await photo.read()
    if not image:
        return None
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(415, "photo must be an image")
    return image, photo


# The box's own web UI talks to /face_manager/person (POST add, PUT edit, DELETE remove):
# multipart with the image in "face1" and a JSON "person_info" field; groups are
# bound separately via /face_manager/person_bind on edit.

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
    upload = await _read_photo(photo)
    if not upload:
        raise HTTPException(422, "a reference photo is required")
    image, photo = upload
    groups = _parse_group_ids(group_ids)

    payload: dict[str, Any] = {
        "person_info": {
            "birthday": birthday,
            "code": code,
            "gender": gender,
            "id": person_id,
            "name": name,
            "remarks": remarks,
            "type": person_type,
        },
        "face_data": {"data_type": 0, "save_image": True, "feature_version": "", "data": [{"data_size": len(image)}]},
    }
    if groups:
        payload["groups"] = [{"group_id": g} for g in groups]
    result = await box.upload(
        "/face_manager/person",
        files={
            "face1": (photo.filename or "face.jpg", image, photo.content_type),
            "person_info": (None, json.dumps(payload)),
        },
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
):
    """Update a face-library person, optionally replacing the reference photo."""
    groups = _parse_group_ids(group_ids)
    upload = await _read_photo(photo)

    payload: dict[str, Any] = {
        "person_id": person_id,
        "person_info": {"birthday": birthday, "code": code, "gender": gender, "name": name, "remarks": remarks},
    }
    # person_info goes as a multipart field even without a photo, so the box always gets multipart.
    files: dict[str, tuple] = {}
    if upload:
        image, photo = upload
        payload["face_data"] = {
            "data_type": 0,
            "save_image": True,
            "data": [{"data_size": len(image), "image_type": photo.content_type.split("/")[1]}],
        }
        files["face1"] = (photo.filename or "face.jpg", image, photo.content_type)
    files["person_info"] = (None, json.dumps(payload))
    result = await box.upload("/face_manager/person", files=files, method="PUT")

    # Like the box UI, an empty selection leaves the current groups untouched.
    if groups:
        await box.call("PUT", "/face_manager/person_bind", {
            "person_id": person_id,
            "face_groups": [{"group_id": g} for g in groups],
        })
    return result or {"message": "updated"}


@router.delete("/api/personnel/{person_id}")
async def delete_personnel(person_id: str):
    """Delete a person from the box face library."""
    return await box.call("DELETE", "/face_manager/person", {
        "force": True,
        "all": False,
        "person_id_list": [person_id],
    })