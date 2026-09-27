"""Face library: create a person the same way the box web page does."""
import json

from fastapi import HTTPException, UploadFile

from app.clients.b4h_client import B4HError
from app.core.b4h import b4h

ALLOWED_EXT = {"jpeg", "jpg", "png", "bmp", "jfif"}


async def create_person(name: str, photo: UploadFile, group_id: str | None, remarks: str | None):
    img = await photo.read()
    ext = (photo.filename or "face.jpg").rsplit(".", 1)[-1].lower()
    ext = ext if ext in ALLOWED_EXT else "jpg"

    # "1" = Default Group (the web page always includes it). group_id may be "2" or "2,3".
    ids = ["1"]
    if group_id and group_id.strip().lower() != "string":
        ids += [g.strip() for g in group_id.split(",") if g.strip() and g.strip() != "1"]

    # Copied from what the box web page sends (DevTools → Payload)
    person_info = {
        "person_info": {"name": name, "remarks": remarks or ""},
        "face_data": {"data_type": 0, "save_image": True, "feature_version": "",
                      "data": [{"data_size": len(img)}]},
        "groups": [{"group_id": g} for g in ids],
    }
    try:
        return await b4h.call_multipart(
            "/face_manager/person",
            fields={"person_info": json.dumps(person_info, ensure_ascii=False)},
            files={"face1": (photo.filename or f"face.{ext}", img, photo.content_type or "image/jpeg")},
        )
    except B4HError as e:
        raise HTTPException(status_code=502, detail={"b4h_code": e.code, "message": e.message, "path": e.path})
