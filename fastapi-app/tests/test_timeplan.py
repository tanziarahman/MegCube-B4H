"""Time plans: box clock, plan list/create/update/delete, stream-subscription cleanup."""
from conftest import box_error

QUERY = ("POST", "/device_rules/schedule_plan/query")
PLAN = "/device_rules/schedule_plan"
SYSTEM_TIME = ("POST", "/system/get_system_time")
TIME_INFO = ("POST", "/system/get_time_info")
MEDIA_UNSUB = ("DELETE", "/media_video/subscribe_stream")
ALARM_UNSUB = ("DELETE", "/device_alarm/subscribe_stream")

WEEK = {"1": ["09:00:00-17:00:00"], "2": [], "3": [], "4": [], "5": [], "6": [], "7": []}


# ---------- stream subscriptions (must not be shadowed by DELETE /api/timeplans/{plan_id}) ----------

def test_unsubscribe_reaches_the_box_not_the_plan_delete(client, fake_box):
    fake_box.replies[MEDIA_UNSUB] = None
    fake_box.replies[ALARM_UNSUB] = None
    r = client.request("DELETE", "/api/timeplans/stream-subscriptions",
                       json={"handles": [12, 13], "device_alarm_handles": [7]})
    assert r.status_code == 200
    assert r.json() == {"media_video_handles": [12, 13], "device_alarm_handles": [7]}
    assert fake_box.sent(*MEDIA_UNSUB) == [{"handle": 12}, {"handle": 13}]
    assert fake_box.sent(*ALARM_UNSUB) == [{"handle": 7}]
    assert fake_box.sent("DELETE", PLAN) == []


def test_unsubscribe_needs_a_handle(client, fake_box):
    r = client.request("DELETE", "/api/timeplans/stream-subscriptions", json={})
    assert r.status_code == 422
    assert fake_box.calls == []


# ---------- clock ----------

def test_time_from_the_box(client, fake_box):
    fake_box.replies[SYSTEM_TIME] = {"time_zone": "UTC+6"}
    fake_box.replies[TIME_INFO] = {"time": "2026-09-29 14:07:00"}
    data = client.get("/api/timeplans/time").json()
    assert data["clock_source"] == "box"
    assert data["current_time"] == {"time": "2026-09-29 14:07:00"}


def test_time_falls_back_when_firmware_lacks_the_endpoints(client, fake_box):
    fake_box.replies[SYSTEM_TIME] = box_error(404, "not found", "/system/get_system_time")
    fake_box.replies[TIME_INFO] = box_error(404, "not found", "/system/get_time_info")
    data = client.get("/api/timeplans/time").json()
    assert data["clock_source"] == "backend_fallback"
    assert data["system_time"] == {}
    assert data["current_time"]["source"] == "backend_fallback"


def test_time_other_box_errors_are_reported(client, fake_box):
    fake_box.replies[SYSTEM_TIME] = box_error()
    assert client.get("/api/timeplans/time").status_code == 502


# ---------- plans ----------

def test_regular_and_festival_queries(client, fake_box):
    fake_box.replies[QUERY] = {"schedule_plans": []}
    assert client.get("/api/timeplans/regular").json() == {"schedule_plans": []}
    assert client.get("/api/timeplans/festival").status_code == 200
    assert fake_box.sent(*QUERY) == [
        {"offset": 0, "size": 100, "schedule_plan_type": 1},
        {"offset": 0, "size": 50, "schedule_plan_type": 2},
    ]


def test_create_sends_the_box_payload(client, fake_box):
    fake_box.replies[("POST", PLAN)] = None
    body = {"schedule_plan_name": "Office hours", "schedule_plan_type": 1, "week_schedule": WEEK}
    r = client.post("/api/timeplans", json=body)
    assert r.status_code == 201
    assert r.json() == {"data": {}, "schedule_plan_name": "Office hours"}
    assert fake_box.sent("POST", PLAN) == [{**body, "bind_schedule_plan": []}]


def test_create_refuses_unknown_type(client, fake_box):
    r = client.post("/api/timeplans", json={"schedule_plan_name": "X", "schedule_plan_type": 3, "week_schedule": WEEK})
    assert r.status_code == 422
    assert fake_box.calls == []


def test_update_sends_the_box_payload(client, fake_box):
    fake_box.replies[("PUT", PLAN)] = None
    body = {"schedule_plan_id": "3", "schedule_plan_name": "Night", "schedule_plan_type": 2, "week_schedule": WEEK}
    r = client.put("/api/timeplans/3", json=body)
    assert r.json() == {"schedule_plan_id": "3", "data": {}}
    assert fake_box.sent("PUT", PLAN) == [{**body, "bind_schedule_plan": []}]


def test_update_refuses_mismatched_id(client, fake_box):
    body = {"schedule_plan_id": "4", "schedule_plan_name": "Night", "schedule_plan_type": 1, "week_schedule": WEEK}
    assert client.put("/api/timeplans/3", json=body).status_code == 422
    assert fake_box.calls == []


def test_delete_sends_the_box_payload(client, fake_box):
    fake_box.replies[("DELETE", PLAN)] = None
    r = client.request("DELETE", "/api/timeplans/3", json={"schedule_plan_id": "3", "schedule_plan_type": 1})
    assert r.json() == {"deleted": "3", "data": {}}
    assert fake_box.sent("DELETE", PLAN) == [{"schedule_plan_id": "3", "schedule_plan_type": 1}]


def test_delete_refuses_mismatched_id(client, fake_box):
    r = client.request("DELETE", "/api/timeplans/3", json={"schedule_plan_id": "9", "schedule_plan_type": 1})
    assert r.status_code == 422
    assert fake_box.calls == []
