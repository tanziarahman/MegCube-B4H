"""/api/capture"""
import pytest

from conftest import box_error

HISTORY = ("POST", "/device_alarm/alarm_history")
OK = {"start": "2026-09-28 00:00:00", "end": "2026-09-28 23:59:59"}


def face_record(**over):
    rec = {
        "additional": {"alarm_minor": "face_capture", "alarm_id": 11, "device_id": 1},
        "global_info": {"time_ms": 1759000000000},
        "faces": [{"image_data": {"value": "./record_1/face.jpg"}, "track_id": 5, "track_id_times": 2,
                   "link_info": {}, "alarm_linkage": {}, "age": 30, "gender": "female"}],
        "full_images": [{"image_data": {"value": "./record_1/full.jpg"}}],
    }
    rec.update(over)
    return rec


def body_record():
    return {
        "additional": {"alarm_minor": "body_capture", "alarm_id": 12, "device_id": 2},
        "global_info": {"time_ms": 1759000001000},
        "pedestrians": [{"image_data": {"value": "./record_1/body.jpg"}, "track_id": 6, "upper_color": "red"}],
        "full_images": [{"image_data": {"value": ""}}],
    }


@pytest.mark.parametrize("target,minors", [
    ("all", ["face_capture", "body_capture"]), ("face", ["face_capture"]), ("body", ["body_capture"])])
def test_target_type_maps_to_minor_types(client, fake_box, target, minors):
    fake_box.replies[HISTORY] = {}
    assert client.get("/api/capture", params={**OK, "target_type": target}).status_code == 200
    types = fake_box.sent(*HISTORY)[0]["query_condition"]["alarm_type"]
    assert types[0] == {"major_type": "face_basic_business", "minor_type": minors}
    # the box answers not_support without this second entry
    assert types[1]["major_type"] == "structure"


def test_face_record_is_flattened(client, fake_box):
    fake_box.replies[HISTORY] = {"total_count": 1, "return_count": 1, "list": [face_record()]}
    row = client.get("/api/capture", params=OK).json()["list"][0]
    assert row == {
        "alarm_id": 11, "track_id": 5, "target_type": "face", "device_id": 1, "capture_time_ms": 1759000000000,
        "target_image": "./record_1/face.jpg", "panoramic_image": "./record_1/full.jpg",
        "attributes": {"age": 30, "gender": "female"},   # bookkeeping keys removed
    }


def test_body_record_uses_pedestrians_and_empty_panoramic_is_none(client, fake_box):
    fake_box.replies[HISTORY] = {"total_count": 1, "list": [body_record()]}
    row = client.get("/api/capture", params=OK).json()["list"][0]
    assert row["target_type"] == "body" and row["track_id"] == 6
    assert row["target_image"] == "./record_1/body.jpg"
    assert row["panoramic_image"] is None
    assert row["attributes"] == {"upper_color": "red"}


@pytest.mark.parametrize("change", [
    {"faces": []}, {"faces": None}, {"full_images": []}, {"full_images": None},
    {"faces": [{}]}, {"faces": [{"image_data": None}]}, {"full_images": [{"image_data": {"value": None}}]},
    {"additional": None}, {"global_info": None},
])
def test_missing_parts_of_a_record_do_not_crash(client, fake_box, change):
    fake_box.replies[HISTORY] = {"total_count": 1, "list": [face_record(**change)]}
    r = client.get("/api/capture", params=OK)
    assert r.status_code == 200, r.text


def test_unknown_minor_is_treated_as_body(client, fake_box):
    rec = body_record()
    rec["additional"]["alarm_minor"] = "something_new"
    fake_box.replies[HISTORY] = {"list": [rec]}
    assert client.get("/api/capture", params=OK).json()["list"][0]["target_type"] == "body"


def test_empty_result(client, fake_box):
    fake_box.replies[HISTORY] = {}
    assert client.get("/api/capture", params=OK).json() == {"total_count": 0, "return_count": 0, "list": []}


def test_box_returns_no_data(client, fake_box):
    """The box can answer code 0 with data: null. Should be an empty page, not a 500."""
    fake_box.replies[HISTORY] = None
    r = client.get("/api/capture", params=OK)
    assert r.status_code == 200
    assert r.json() == {"total_count": 0, "return_count": 0, "list": []}


@pytest.mark.parametrize("params", [
    {"target_type": "vehicle"}, {"size": 31}, {"size": 0}, {"page": 0}, {"start": "bad"}, {"end": "2026-09-28"}])
def test_bad_input(client, fake_box, params):
    assert client.get("/api/capture", params={**OK, **params}).status_code == 422
    assert fake_box.calls == []


def test_box_error(client, fake_box):
    fake_box.replies[HISTORY] = box_error(1073741831, "not_support")
    assert client.get("/api/capture", params=OK).status_code == 502


def test_page_past_the_end_is_an_empty_page(client, fake_box):
    def reply(body):
        if body["offset"] >= 5:
            raise box_error(1073741825, "general")
        return {"total_count": 5, "list": []}
    fake_box.replies[HISTORY] = reply
    r = client.get("/api/capture", params={**OK, "page": 50})
    assert r.status_code == 200 and r.json() == {"total_count": 5, "return_count": 0, "list": []}


def test_start_after_end(client, fake_box):
    r = client.get("/api/capture", params={"start": "2026-09-29 00:00:00", "end": "2026-09-28 00:00:00"})
    assert r.status_code == 422 and fake_box.calls == []