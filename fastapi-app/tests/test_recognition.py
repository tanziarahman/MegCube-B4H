"""/api/recognition, DELETE /api/recognition/{id}, /api/people"""
from datetime import datetime

import httpx
import pytest

from conftest import box_error

HISTORY = ("POST", "/device_alarm/alarm_history")
OK = {"start": "2026-09-28 00:00:00", "end": "2026-09-28 23:59:59"}


def ms(s):
    return str(int(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp() * 1000))


# ---------- happy path ----------

def test_recognition_sends_the_box_payload(client, fake_box):
    fake_box.replies[HISTORY] = {"total_count": 1, "return_count": 1, "list": [{"a": 1}]}
    r = client.get("/api/recognition", params=OK)
    assert r.status_code == 200
    assert r.json() == {"total_count": 1, "return_count": 1, "list": [{"a": 1}]}
    body = fake_box.sent(*HISTORY)[0]
    assert body["offset"] == 0 and body["size"] == 10
    q = body["query_condition"]
    assert q["start_time"] == ms(OK["start"]) and q["end_time"] == ms(OK["end"])
    assert q["alarm_type"] == [{"major_type": "face_basic_business", "minor_type": ["face_comparison_successful"]}]
    assert q["ext"] == {"query_type": 0, "de_dup": 0}


def test_recognition_times_are_sent_as_strings(client, fake_box):
    fake_box.replies[HISTORY] = {}
    client.get("/api/recognition", params=OK)
    q = fake_box.sent(*HISTORY)[0]["query_condition"]
    assert isinstance(q["start_time"], str) and isinstance(q["end_time"], str)


def test_strangers(client, fake_box):
    fake_box.replies[HISTORY] = {}
    assert client.get("/api/recognition", params={**OK, "minor": "stranger"}).status_code == 200
    assert fake_box.sent(*HISTORY)[0]["query_condition"]["alarm_type"][0]["minor_type"] == ["stranger"]


@pytest.mark.parametrize("page,size,offset", [(1, 10, 0), (2, 10, 10), (3, 30, 60), (1, 1, 0), (1, 30, 0)])
def test_paging_offset(client, fake_box, page, size, offset):
    fake_box.replies[HISTORY] = {}
    assert client.get("/api/recognition", params={**OK, "page": page, "size": size}).status_code == 200
    body = fake_box.sent(*HISTORY)[0]
    assert (body["offset"], body["size"]) == (offset, size)


def test_box_returns_no_data(client, fake_box):
    fake_box.replies[HISTORY] = None
    r = client.get("/api/recognition", params=OK)
    assert r.status_code == 200 and r.json() == {}


# ---------- bad input: rejected BEFORE the box is called ----------

@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": -1}, {"page": "abc"},
    {"size": 0}, {"size": 31}, {"size": 1000}, {"size": "ten"},
    {"minor": "fire_alarm"},      # unknown minor types crash the box's web server
    {"minor": ""},
    {"start": "2026-09-28"},       # missing time
    {"start": "28-09-2026 00:00:00"},
    {"start": "2026-13-01 00:00:00"},  # month 13
    {"start": "2026-02-30 00:00:00"},  # 30 Feb
    {"end": "yesterday"},
    {"start": ""},
])
def test_bad_input_is_rejected(client, fake_box, params):
    r = client.get("/api/recognition", params={**OK, **params})
    assert r.status_code == 422
    assert fake_box.calls == [], "the box must not be called with bad input"


@pytest.mark.parametrize("missing", ["start", "end"])
def test_missing_time(client, fake_box, missing):
    params = dict(OK)
    params.pop(missing)
    assert client.get("/api/recognition", params=params).status_code == 422
    assert fake_box.calls == []


def test_start_after_end_is_rejected(client, fake_box):
    r = client.get("/api/recognition", params={"start": "2026-09-28 23:00:00", "end": "2026-09-28 01:00:00"})
    assert r.status_code == 422
    assert fake_box.calls == []


def test_start_equals_end_is_allowed(client, fake_box):
    fake_box.replies[HISTORY] = {}
    same = "2026-09-28 10:00:00"
    assert client.get("/api/recognition", params={"start": same, "end": same}).status_code == 200


# ---------- page past the last record (found by live_check: the box answers "general" error) ----------

def box_with_total(total):
    """Box that fails with 'general' when the offset is past the end, like the real one."""
    def reply(body):
        if body["offset"] >= total and body["offset"] > 0:
            raise box_error(1073741825, "general", "/device_alarm/alarm_history")
        return {"total_count": total, "return_count": min(body["size"], total - body["offset"]), "list": []}
    return reply


def test_page_past_the_end_is_an_empty_page(client, fake_box):
    fake_box.replies[HISTORY] = box_with_total(25)
    r = client.get("/api/recognition", params={**OK, "page": 9999})
    assert r.status_code == 200
    assert r.json() == {"total_count": 25, "return_count": 0, "list": []}


def test_page_right_after_the_last_record(client, fake_box):
    fake_box.replies[HISTORY] = box_with_total(30)
    r = client.get("/api/recognition", params={**OK, "page": 2, "size": 30})
    assert r.status_code == 200 and r.json()["list"] == []


def test_general_error_on_first_page_is_still_an_error(client, fake_box):
    fake_box.replies[HISTORY] = box_error(1073741825, "general")
    assert client.get("/api/recognition", params=OK).status_code == 502


def test_general_error_inside_the_records_is_still_an_error(client, fake_box):
    def reply(body):
        if body["size"] == 1:
            return {"total_count": 100}
        raise box_error(1073741825, "general")
    fake_box.replies[HISTORY] = reply
    assert client.get("/api/recognition", params={**OK, "page": 2}).status_code == 502


# ---------- box problems ----------

def test_box_error_becomes_502(client, fake_box):
    fake_box.replies[HISTORY] = box_error(1073741831, "not_support", "/device_alarm/alarm_history")
    r = client.get("/api/recognition", params=OK)
    assert r.status_code == 502
    assert "not_support" in r.json()["detail"] and "1073741831" in r.json()["detail"]


@pytest.mark.parametrize("exc", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), httpx.ConnectTimeout("x")])
def test_box_unreachable_becomes_503(client, fake_box, exc):
    fake_box.replies[HISTORY] = exc
    r = client.get("/api/recognition", params=OK)
    assert r.status_code == 503
    assert "unreachable" in r.json()["detail"]


# ---------- delete ----------

def test_delete_recognition(client, fake_box):
    fake_box.replies[("DELETE", "/device_alarm/alarm_history")] = None
    r = client.delete("/api/recognition/1234")
    assert r.status_code == 200 and r.json() == {"deleted": 1234}
    cond = fake_box.sent("DELETE", "/device_alarm/alarm_history")[0]["condition"]
    assert cond["type"] == "alarm_id" and cond["id_list"] == [1234]
    assert set(cond["alarm_type"][0]["minor_type"]) == {"face_comparison_successful", "stranger"}


@pytest.mark.parametrize("bad", ["0", "-5", "abc", "1.5"])
def test_delete_bad_id(client, fake_box, bad):
    assert client.delete(f"/api/recognition/{bad}").status_code == 422
    assert fake_box.calls == []


def test_delete_box_refuses(client, fake_box):
    fake_box.replies[("DELETE", "/device_alarm/alarm_history")] = box_error(5, "not_found")
    assert client.delete("/api/recognition/99").status_code == 502


# ---------- /api/people ----------

PERSON_QUERY = ("POST", "/face_manager/person/query")


def _people(n):
    return [{"person_id": i, "person_info": {"name": f"P{i}"}} for i in range(n)]


def test_people_single_page(client, fake_box):
    fake_box.replies[PERSON_QUERY] = {"total_count": 2, "person_list": _people(2)}
    r = client.get("/api/people")
    assert r.json() == {"total_count": 2, "person_list": [{"person_id": "0", "name": "P0"}, {"person_id": "1", "name": "P1"}]}
    assert fake_box.sent(*PERSON_QUERY)[0]["get_feature"] is False


def test_people_pages_through_everyone(client, fake_box):
    everyone = _people(65)
    fake_box.replies[PERSON_QUERY] = lambda b: {
        "total_count": 65, "person_list": everyone[b["offset"]:b["offset"] + b["size"]]}
    r = client.get("/api/people")
    assert r.json()["total_count"] == 65
    assert [b["offset"] for b in fake_box.sent(*PERSON_QUERY)] == [0, 30, 60]
    assert all(b["size"] == 30 for b in fake_box.sent(*PERSON_QUERY))


def test_people_exactly_one_full_page(client, fake_box):
    fake_box.replies[PERSON_QUERY] = lambda b: {"total_count": 30, "person_list": _people(30) if b["offset"] == 0 else []}
    assert client.get("/api/people").json()["total_count"] == 30
    assert len(fake_box.sent(*PERSON_QUERY)) == 1


def test_people_empty_library(client, fake_box):
    fake_box.replies[PERSON_QUERY] = {"total_count": 0, "person_list": []}
    assert client.get("/api/people").json() == {"total_count": 0, "person_list": []}


def test_people_box_returns_none(client, fake_box):
    fake_box.replies[PERSON_QUERY] = None
    assert client.get("/api/people").json() == {"total_count": 0, "person_list": []}


def test_people_total_count_wrong_does_not_loop_forever(client, fake_box):
    # Box claims 100 people but stops returning any after 30.
    fake_box.replies[PERSON_QUERY] = lambda b: {"total_count": 100, "person_list": _people(30) if b["offset"] == 0 else []}
    assert client.get("/api/people").json()["total_count"] == 30
    assert len(fake_box.sent(*PERSON_QUERY)) == 2


def test_people_missing_name(client, fake_box):
    fake_box.replies[PERSON_QUERY] = {"total_count": 1, "person_list": [{"person_id": 7}]}
    assert client.get("/api/people").json()["person_list"] == [{"person_id": "7", "name": ""}]


def test_people_bangla_name(client, fake_box):
    fake_box.replies[PERSON_QUERY] = {"total_count": 1, "person_list": [{"person_id": 1, "person_info": {"name": "তানজিয়া"}}]}
    assert client.get("/api/people").json()["person_list"][0]["name"] == "তানজিয়া"