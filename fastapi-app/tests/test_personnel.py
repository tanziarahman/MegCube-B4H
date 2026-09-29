"""/api/personnel/groups, /api/personnel (list, add, edit, delete)"""
import json

import pytest

from conftest import box_error

GROUPS = ("POST", "/face_manager/groups/query")
QUERY = ("POST", "/face_manager/person/query")
PERSON_POST = ("POST", "/face_manager/person")
PERSON_PUT = ("PUT", "/face_manager/person")
BIND = ("PUT", "/face_manager/person_bind")
PERSON_DELETE = ("DELETE", "/face_manager/person")

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100 + b"\xff\xd9"


def photo(content=JPEG, name="face.jpg", ctype="image/jpeg"):
    return {"photo": (name, content, ctype)}


def person_info(files):
    """The JSON the backend put in the multipart 'person_info' part."""
    return json.loads(files["person_info"][1])


# ---------- groups ----------

def test_groups(client, fake_box):
    fake_box.replies[GROUPS] = {"groups": [{"group_id": "g1", "name": "Staff"}]}
    assert client.get("/api/personnel/groups").json() == {"groups": [{"group_id": "g1", "name": "Staff"}]}


@pytest.mark.parametrize("reply", [None, {}, {"groups": None}])
def test_groups_empty(client, fake_box, reply):
    fake_box.replies[GROUPS] = reply
    assert client.get("/api/personnel/groups").json() == {"groups": []}


# ---------- list ----------

def test_list_paging(client, fake_box):
    fake_box.replies[QUERY] = {"total_count": 45, "person_list": []}
    r = client.get("/api/personnel", params={"page": 2, "size": 20})
    assert r.json()["total_count"] == 45
    assert fake_box.sent(*QUERY)[0] == {"offset": 20, "size": 20, "get_feature": True}


def test_list_total_count_fallback(client, fake_box):
    fake_box.replies[QUERY] = {"count": 3, "person_list": []}
    assert client.get("/api/personnel").json()["total_count"] == 3


@pytest.mark.parametrize("params", [{"size": 31}, {"size": 0}, {"page": 0}, {"get_feature": "maybe"}])
def test_list_bad_input(client, fake_box, params):
    assert client.get("/api/personnel", params=params).status_code == 422
    assert fake_box.calls == []


@pytest.mark.parametrize("person,expected", [
    ({"face_image1": "/home/appdata/a.jpg"}, "/home/appdata/a.jpg"),
    ({"face_image1": {"image_uri": "/home/appdata/b.jpg"}}, "/home/appdata/b.jpg"),
    ({"face_images": [{"uri": "/home/appdata/c.jpg"}]}, "/home/appdata/c.jpg"),
    ({"face_data": {"value": "/home/appdata/d.jpg"}}, "/home/appdata/d.jpg"),
    ({"person_info": {"face_image1": "/home/appdata/e.jpg"}}, "/home/appdata/e.jpg"),
    ({"face_images": []}, None),
    ({}, None),
])
def test_list_face_image_is_normalized(client, fake_box, person, expected):
    fake_box.replies[QUERY] = {"total_count": 1, "person_list": [{"person_id": "1", **person}]}
    row = client.get("/api/personnel").json()["person_list"][0]
    assert row.get("face_image1") == expected


def test_list_box_returns_none(client, fake_box):
    fake_box.replies[QUERY] = None
    assert client.get("/api/personnel").json()["person_list"] == []


# ---------- add ----------

def test_add(client, fake_box):
    fake_box.replies[PERSON_POST] = {"person_id": "p9"}
    r = client.post("/api/personnel", data={"name": "Tanzia", "group_ids": '["g1", 2]', "gender": "2",
                                            "code": "E-01", "remarks": "night shift"}, files=photo())
    assert r.status_code == 201 and r.json() == {"person_id": "p9"}
    method, path, files = fake_box.uploads[0]
    assert files["face1"] == ("face.jpg", JPEG, "image/jpeg")
    info = person_info(files)
    assert info["person_info"]["name"] == "Tanzia" and info["person_info"]["gender"] == 2
    assert info["groups"] == [{"group_id": "g1"}, {"group_id": "2"}]     # ids sent as strings
    assert info["face_data"]["data"][0]["data_size"] == len(JPEG)


def test_add_without_groups_sends_no_groups_key(client, fake_box):
    fake_box.replies[PERSON_POST] = None
    r = client.post("/api/personnel", data={"name": "A"}, files=photo())
    assert r.status_code == 201 and r.json() == {"message": "created"}
    assert "groups" not in person_info(fake_box.uploads[0][2])


def test_add_bangla_name(client, fake_box):
    fake_box.replies[PERSON_POST] = None
    client.post("/api/personnel", data={"name": "তানজিয়া"}, files=photo())
    assert person_info(fake_box.uploads[0][2])["person_info"]["name"] == "তানজিয়া"


@pytest.mark.parametrize("data,files,status", [
    ({"name": "A"}, None, 422),                                            # no photo
    ({"name": "A"}, photo(content=b""), 422),                              # empty file
    ({"name": "A"}, photo(name=""), 422),                                  # empty file input from a browser
    ({"name": "A"}, photo(name="cv.pdf", ctype="application/pdf"), 415),   # not an image
    ({"name": ""}, photo(), 422),
    ({}, photo(), 422),
    ({"name": "A", "group_ids": "g1"}, photo(), 422),                      # not JSON
    ({"name": "A", "group_ids": '{"id": 1}'}, photo(), 422),               # JSON but not a list
    ({"name": "A", "group_ids": '[{"id": 1}]'}, photo(), 422),             # list of objects
    ({"name": "A", "gender": "female"}, photo(), 422),
])
def test_add_bad_input(client, fake_box, data, files, status):
    r = client.post("/api/personnel", data=data, files=files or {})
    assert r.status_code == status, r.text
    assert fake_box.uploads == []


def test_add_box_rejects_photo(client, fake_box):
    """e.g. no face found in the picture."""
    fake_box.replies[PERSON_POST] = box_error(3, "no face detected", "/face_manager/person")
    r = client.post("/api/personnel", data={"name": "A"}, files=photo())
    assert r.status_code == 502 and "no face detected" in r.json()["detail"]


# ---------- edit ----------

def test_edit_without_photo(client, fake_box):
    fake_box.replies[PERSON_PUT] = None
    r = client.put("/api/personnel/p1", data={"name": "New name"})
    assert r.status_code == 200 and r.json() == {"message": "updated"}
    method, path, files = fake_box.uploads[0]
    assert method == "PUT" and "face1" not in files
    info = person_info(files)
    assert info["person_id"] == "p1" and info["person_info"]["name"] == "New name" and "face_data" not in info
    assert fake_box.sent(*BIND) == []           # empty group selection = keep current groups


def test_edit_with_photo_and_groups(client, fake_box):
    fake_box.replies[PERSON_PUT] = None
    fake_box.replies[BIND] = None
    r = client.put("/api/personnel/p1", data={"name": "A", "group_ids": '["g1","g2"]'},
                   files=photo(name="x.png", ctype="image/png"))
    assert r.status_code == 200
    files = fake_box.uploads[0][2]
    assert files["face1"][2] == "image/png"
    assert person_info(files)["face_data"]["data"][0]["image_type"] == "png"
    assert fake_box.sent(*BIND) == [{"person_id": "p1", "face_groups": [{"group_id": "g1"}, {"group_id": "g2"}]}]


def test_edit_empty_file_input_is_treated_as_no_photo(client, fake_box):
    fake_box.replies[PERSON_PUT] = None
    r = client.put("/api/personnel/p1", data={"name": "A"}, files={"photo": ("", b"", "application/octet-stream")})
    assert r.status_code == 200
    assert "face1" not in fake_box.uploads[0][2]


@pytest.mark.parametrize("data,files,status", [
    ({"name": ""}, None, 422),
    ({"name": "A", "group_ids": "nope"}, None, 422),
    ({"name": "A"}, photo(name="a.txt", ctype="text/plain"), 415),
])
def test_edit_bad_input(client, fake_box, data, files, status):
    assert client.put("/api/personnel/p1", data=data, files=files or {}).status_code == status
    assert fake_box.uploads == []


def test_edit_bind_fails_after_person_updated(client, fake_box):
    """Person is saved but the group change fails: the API must report an error, not success."""
    fake_box.replies[PERSON_PUT] = None
    fake_box.replies[BIND] = box_error(4, "group not found")
    assert client.put("/api/personnel/p1", data={"name": "A", "group_ids": '["gone"]'}).status_code == 502


# ---------- delete ----------

def test_delete(client, fake_box):
    fake_box.replies[PERSON_DELETE] = None
    assert client.delete("/api/personnel/p1").status_code == 200
    assert fake_box.sent(*PERSON_DELETE) == [{"force": True, "all": False, "person_id_list": ["p1"]}]


def test_delete_never_sends_delete_all(client, fake_box):
    fake_box.replies[PERSON_DELETE] = None
    for pid in ["p1", "all", "*", "0"]:
        client.delete(f"/api/personnel/{pid}")
    assert all(b["all"] is False and len(b["person_id_list"]) == 1 for b in fake_box.sent(*PERSON_DELETE))


def test_delete_unknown_person(client, fake_box):
    fake_box.replies[PERSON_DELETE] = box_error(5, "person not exist")
    assert client.delete("/api/personnel/nope").status_code == 502
