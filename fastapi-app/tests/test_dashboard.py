"""GET /api/dashboard/summary"""
from conftest import DEVICE_CONFIG, DEVICE_STATE, TASK_LIST

CONFIG = ("POST", "/device_access/device_config")
STATE = ("POST", "/device_access/device_state")
TASKS = ("POST", "/intelli_manager/task_list")
SYSTEM_TIME = ("POST", "/system/get_system_time")
CURRENT_TIME = ("POST", "/system/get_time_info")
HISTORY = ("POST", "/device_alarm/alarm_history")


def _box_replies(fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    fake_box.replies[STATE] = DEVICE_STATE
    fake_box.replies[TASKS] = TASK_LIST
    fake_box.replies[SYSTEM_TIME] = {"time_zone": "Asia/Dhaka"}
    fake_box.replies[CURRENT_TIME] = {"time": "2026-09-29 14:30:00"}

    def history(body):
        minor = body["query_condition"]["alarm_type"][0]["minor_type"]
        offset = body["offset"]
        if minor == ["face_comparison_successful"]:
            return {"total_count": 3, "list": [{"additional": {"device_id": 1, "alarm_id": 12 + offset},
                                               "global_info": {"time_ms": 1760000000000 + offset},
                                               "person_id": "p1", "person_name": "Ada", "track_id": offset + 1,
                                               "face_score": 96, "liveness_score": 0.95}]}
        if minor == ["stranger"]:
            return {"total_count": 2, "list": [{"additional": {"device_id": 2, "alarm_id": 13 + offset},
                                               "global_info": {"time_ms": 1760000001000 + offset},
                                               "track_id": offset + 10, "face_score": 55,
                                               "liveness_score": 0.6}]}
        return {"total_count": 4, "list": [{"additional": {"alarm_minor": "face_capture", "device_id": 1},
                                           "global_info": {"time_ms": 1760000000000 + offset},
                                           "track_id": offset + 1}]}

    fake_box.replies[HISTORY] = history


CONFIG = ("POST", "/device_access/device_config")
STATE = ("POST", "/device_access/device_state")
TASKS = ("POST", "/intelli_manager/task_list")
SYSTEM_TIME = ("POST", "/system/get_system_time")
CURRENT_TIME = ("POST", "/system/get_time_info")
HISTORY = ("POST", "/device_alarm/alarm_history")


def test_dashboard_aggregates_health_activity_and_attention(client, fake_box):
    fake_box.replies[CONFIG] = DEVICE_CONFIG
    fake_box.replies[STATE] = DEVICE_STATE
    fake_box.replies[TASKS] = TASK_LIST
    fake_box.replies[SYSTEM_TIME] = {"time_zone": "Asia/Dhaka"}
    fake_box.replies[CURRENT_TIME] = {"time": "2026-09-29 14:30:00"}

    def history(body):
        minor = body["query_condition"]["alarm_type"][0]["minor_type"]
        offset = body["offset"]
        if minor == ["face_comparison_successful"]:
            return {"total_count": 3, "list": [{"additional": {"device_id": 1, "alarm_id": 12 + offset},
                                                   "global_info": {"time_ms": 1760000000000 + offset},
                                                   "person_id": "p1", "person_name": "Ada", "track_id": offset + 1,
                                                   "face_score": 96, "liveness_score": 0.95}]}
        if minor == ["stranger"]:
            return {"total_count": 2, "list": [{"additional": {"device_id": 2, "alarm_id": 13 + offset},
                                                  "global_info": {"time_ms": 1760000001000 + offset},
                                                  "track_id": offset + 10, "face_score": 55,
                                                  "liveness_score": 0.6}]}
        return {"total_count": 4, "list": [{"additional": {"alarm_minor": "face_capture", "device_id": 1},
                                               "global_info": {"time_ms": 1760000000000 + offset},
                                               "track_id": offset + 1}]}

    fake_box.replies[HISTORY] = history
    response = client.get("/api/dashboard/summary", params={"date": "2026-09-29"})

    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-09-29"
    assert data["health"] == {
        "devices_total": 3,
        "devices_online": 2,
        "devices_offline": 1,
        "streams_pulling": 1,
        "tasks_total": 1,
        "clock": {"time": "2026-09-29 14:30:00", "time_zone": "Asia/Dhaka", "source": "box"},
    }
    assert data["activity"]["matched"] == 3
    assert data["activity"]["strangers"] == 2
    assert data["activity"]["captures"] == 4
    assert data["insights"]["average_match_score"] == 79.6
    assert data["insights"]["low_confidence_count"] == 2
    assert data["insights"]["low_liveness_count"] == 2
    assert data["insights"]["tracked_encounters"] == 4
    assert data["insights"]["unique_recognized_people"] == 1
    assert data["insights"]["recognized_encounters"] == 3
    assert data["insights"]["stranger_encounters"] == 2
    assert data["insights"]["recognized_capture_tracks"] == 3
    assert data["insights"]["recognition_coverage_percent"] == 75.0
    assert any(item["type"] == "offline_camera" for item in data["attention"])
    assert any(item["type"] == "stream_not_pulling" for item in data["attention"])


def test_dashboard_rejects_bad_date_before_box_call(client, fake_box):
    response = client.get("/api/dashboard/summary", params={"date": "today"})
    assert response.status_code == 422
    assert fake_box.calls == []


def test_meta_says_box_without_a_database(client, fake_box):
    _box_replies(fake_box)
    data = client.get("/api/dashboard/summary", params={"date": "2026-09-29"}).json()
    assert data["meta"]["source"] == "box"
    assert data["meta"]["cache"] == {"health": "off", "activity": "off"}


def test_second_request_is_served_from_redis(client, fake_box, redis_cache):
    _box_replies(fake_box)
    first = client.get("/api/dashboard/summary", params={"date": "2026-09-29"}).json()
    assert first["meta"]["cache"] == {"health": "miss", "activity": "miss"}
    calls = len(fake_box.calls)
    second = client.get("/api/dashboard/summary", params={"date": "2026-09-29"}).json()
    assert second["meta"]["cache"] == {"health": "hit", "activity": "hit"}
    assert len(fake_box.calls) == calls
    first.pop("generated_at")
    second.pop("generated_at")
    first["meta"].pop("cache")
    second["meta"].pop("cache")
    assert second == first


def test_fresh_skips_the_cache(client, fake_box, redis_cache):
    _box_replies(fake_box)
    client.get("/api/dashboard/summary", params={"date": "2026-09-29"})
    calls = len(fake_box.calls)
    data = client.get("/api/dashboard/summary", params={"date": "2026-09-29", "fresh": "1"}).json()
    assert data["meta"]["cache"] == {"health": "bypass", "activity": "bypass"}
    assert len(fake_box.calls) > calls


def test_redis_down_still_answers(client, fake_box, redis_cache):
    _box_replies(fake_box)
    redis_cache.fail = True
    response = client.get("/api/dashboard/summary", params={"date": "2026-09-29"})
    assert response.status_code == 200
    assert response.json()["activity"]["matched"] == 3


def test_bad_date_touches_nothing(client, fake_box, redis_cache):
    response = client.get("/api/dashboard/summary", params={"date": "today"})
    assert response.status_code == 422
    assert fake_box.calls == []
    assert redis_cache.calls == 0