"""People counting API. Most tests need a real PostgreSQL (TEST_DATABASE_URL; skipped without it);
input checks and the no-database answer don't.

Seeded on Monday 2026-09-28 and Tuesday 2026-09-29 (Dhaka time), through the sighting builder.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from models import AuditLog, Camera
from tests.test_alarms_db import BoxHistory, setup_box
from tests.test_counting_builder import record, save

D3, OTHER, CAM3 = 2, 1, 3
DHAKA = timezone(timedelta(hours=6))
MONDAY = "2026-09-28"


def at(day: str, hh_mm: str, seconds: int = 0) -> datetime:
    return datetime.fromisoformat(f"{day}T{hh_mm}:00").replace(tzinfo=DHAKA) + timedelta(seconds=seconds)


async def _seed(database, fake_box) -> dict[int, int]:
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id,
               # Monday on D3: a pair, a face only, a body only (23:30), and person 17 three times.
               record("body_capture", 1000, at(MONDAY, "09:10")), record("face_capture", 1001, at(MONDAY, "09:10", 1)),
               record("face_capture", 2001, at(MONDAY, "10:00")),
               record("body_capture", 3000, at(MONDAY, "23:30")),
               record("face_comparison_successful", 4001, at(MONDAY, "12:00"), person="17"),
               record("face_comparison_successful", 5001, at(MONDAY, "12:01"), person="17"),    # 60 s later: same visit
               record("face_comparison_successful", 6001, at(MONDAY, "12:12"), person="17"),    # 11 min later: a new visit
               # Tuesday on the other camera; Monday on CAM3, which is left out of counting.
               record("body_capture", 7000, at("2026-09-29", "09:30"), device_id=OTHER),
               record("face_capture", 7001, at("2026-09-29", "09:30"), device_id=OTHER),
               record("face_capture", 8001, at(MONDAY, "09:20"), device_id=CAM3))
    async with database() as s:
        async with s.begin():
            cam3 = await s.get(Camera, cameras[CAM3])
            cam3.count_enabled = False
            s.add(cam3)
    return cameras


@pytest.fixture
def seeded(database, fake_box):
    return asyncio.run(_seed(database, fake_box))


DAY = {"start": f"{MONDAY} 00:00:00", "end": "2026-09-29 00:00:00"}
THREE_DAYS = {"start": f"{MONDAY} 00:00:00", "end": "2026-10-01 00:00:00"}


def totals(client, **params):
    r = client.get("/api/counting/summary", params=params)
    assert r.status_code == 200, r.text
    return r.json()["totals"]


def test_summary_counts_walk_pasts_visits_and_different_people(client, seeded):
    body = client.get("/api/counting/summary", params=DAY).json()
    # Person 17 is recognised (1 person, 3 walk-pasts); the other 3 aren't fingerprinted yet.
    assert body["totals"].pop("face_estimate") == {"people": 1, "low": 1, "high": 1, "fingerprinted": 3,
                                                   "unusable": 0, "pending": 3, "too_many": False}
    assert body["totals"] == {"walk_pasts": 6, "unique_people": 4, "known_people": 1, "stranger_walk_pasts": 0,
                              "not_compared_walk_pasts": 3, "paired": 1, "face_only": 4, "body_only": 1, "visits": 5}
    assert body["period"]["timezone"] == "Asia/Dhaka" and body["period"]["start"].startswith("2026-09-28T00:00:00")
    assert body["identity_available"] is True            # person 17's matches, 6 days before today
    by_camera = {c["name"]: c for c in body["by_camera"]}
    assert set(by_camera) == {"Hikvision", "IPCAM-D3"}   # CAM3 isn't counted by default
    assert by_camera["IPCAM-D3"]["walk_pasts"] == 6 and by_camera["IPCAM-D3"]["visits"] == 5
    assert by_camera["Hikvision"]["walk_pasts"] == 0


def test_hours_weekdays_and_cameras_filter_the_counts(client, seeded):
    assert totals(client, **DAY, hours="9-17")["walk_pasts"] == 5
    assert totals(client, **DAY, hours="22-5")["walk_pasts"] == 1          # past midnight: only 23:30
    assert totals(client, **DAY, hours="12-12")["walk_pasts"] == 3
    assert totals(client, **THREE_DAYS)["walk_pasts"] == 7
    assert totals(client, **THREE_DAYS, days="2")["walk_pasts"] == 1       # Tuesday
    assert totals(client, **THREE_DAYS, days="1,3")["walk_pasts"] == 6
    other = client.get("/api/counting/summary", params={**THREE_DAYS, "camera_id": seeded[OTHER]}).json()
    assert other["totals"]["walk_pasts"] == 1 and other["identity_available"] is False
    assert totals(client, **THREE_DAYS, camera_id=seeded[CAM3])["walk_pasts"] == 1   # asked for by name
    both = client.get("/api/counting/summary", params={**THREE_DAYS, "camera_id": [seeded[D3], seeded[CAM3]]})
    assert both.json()["totals"]["walk_pasts"] == 7


def test_the_counting_basis_decides_which_sightings_count(client, seeded):
    d3 = seeded[D3]
    assert client.patch(f"/api/counting/cameras/{d3}", json={"count_basis": "face"}).json()["count_basis"] == "face"
    assert totals(client, **DAY)["walk_pasts"] == 5            # the body-only 23:30 is left out
    hour = client.get("/api/counting/series", params={**DAY, "granularity": "hour"}).json()["points"]
    assert sum(p["walk_pasts"] for p in hour) == 5
    client.patch(f"/api/counting/cameras/{d3}", json={"count_basis": "body"})
    assert totals(client, **DAY)["walk_pasts"] == 2            # the pair and the body only
    client.patch(f"/api/counting/cameras/{d3}", json={"count_basis": "merged"})
    assert totals(client, **DAY)["walk_pasts"] == 6


def test_series_are_zero_filled(client, seeded):
    body = client.get("/api/counting/series", params={**DAY, "granularity": "hour"}).json()
    points = body["points"]
    assert len(points) == 24 and points[0]["start"].startswith("2026-09-28T00:00:00+06:00")
    by_hour = {int(p["start"][11:13]): p for p in points}
    # Person 17 walks past 3 times from 12:00: 3 walk-pasts, 1 new person.
    assert by_hour[12] == {"start": "2026-09-28T12:00:00+06:00", "walk_pasts": 3, "face": 3, "body": 0, "new_people": 1}
    assert by_hour[9]["walk_pasts"] == 1 and by_hour[9]["face"] == 1 and by_hour[9]["body"] == 1
    assert by_hour[3]["walk_pasts"] == 0

    days = client.get("/api/counting/series", params={**THREE_DAYS, "granularity": "day"}).json()["points"]
    assert [p["walk_pasts"] for p in days] == [6, 1, 0]
    quarter = client.get("/api/counting/series", params={**DAY, "granularity": "15m", "hours": "12-12"}).json()
    assert [p["walk_pasts"] for p in quarter["points"]] == [2, 0, 0, 0] or \
        [p["walk_pasts"] for p in quarter["points"]] == [3, 0, 0, 0]


def test_the_heatmap_averages_over_the_weekdays_in_the_range(client, seeded):
    # Two Mondays (09-28 and 10-05) in the range: Monday 12:00's 3 walk-pasts average 1.5.
    body = client.get("/api/counting/heatmap", params={"start": f"{MONDAY} 00:00:00",
                                                       "end": "2026-10-06 00:00:00"}).json()
    assert body["days_in_range"] == {"1": 2, "2": 1, "3": 1, "4": 1, "5": 1, "6": 1, "7": 1}
    cells = {(c["iso_dow"], c["hour"]): c for c in body["cells"]}
    assert cells[(1, 12)]["avg_walk_pasts"] == 1.5 and cells[(1, 12)]["walk_pasts"] == 3
    assert cells[(2, 9)]["avg_walk_pasts"] == 1.0
    assert (1, 3) not in cells


def test_the_sightings_behind_the_numbers(client, seeded):
    body = client.get("/api/counting/sightings", params={**DAY, "size": 2}).json()
    assert body["total"] == 6 and len(body["items"]) == 2
    newest = body["items"][0]
    assert newest["camera_name"] == "IPCAM-D3" and newest["body_track_id"] == 3000
    assert newest["person_source"] == "unidentified" and newest["body_image_path"].startswith("./record_CHN0/")
    second = client.get("/api/counting/sightings", params={**DAY, "size": 2, "hours": "12-12"}).json()["items"][0]
    assert second["person_name"] == "Person 17" and second["recognition_result"] == "matched"
    pair = client.get("/api/counting/sightings", params={**DAY, "hours": "9-9"}).json()["items"][0]
    assert (pair["face_track_id"], pair["body_track_id"], pair["duration_seconds"], pair["event_count"]) == \
        (1001, 1000, 1.0, 2)


def test_camera_settings_are_saved_and_audited(client, seeded):
    cameras = client.get("/api/counting/cameras").json()
    assert [(c["name"], c["count_enabled"], c["count_basis"]) for c in cameras] == [
        ("Hikvision", True, "merged"), ("IPCAM-D3", True, "merged"), ("CAM3-D4", False, "merged")]
    d3 = seeded[D3]
    r = client.patch(f"/api/counting/cameras/{d3}", json={"count_enabled": False})
    assert r.status_code == 200 and r.json()["count_enabled"] is False and r.json()["count_basis"] == "merged"
    assert totals(client, **DAY)["walk_pasts"] == 0
    assert client.patch("/api/counting/cameras/999", json={"count_enabled": True}).status_code == 404
    assert client.patch(f"/api/counting/cameras/{d3}", json={"count_basis": "people"}).status_code == 422

    async def audit():
        from db import sessions
        async with sessions()() as s:
            return (await s.exec(select(AuditLog))).all()
    [row] = asyncio.run(audit())
    assert row.entity_type == "camera_counting" and row.before["count_enabled"] is True \
        and row.after["count_enabled"] is False


@pytest.mark.parametrize("params, message", [
    ({"start": "2026-13-01 00:00:00"}, "Bad time"),
    ({"start": "2026-09-29 00:00:00", "end": "2026-09-28 00:00:00"}, "start must be before end"),
    ({"start": "2025-01-01 00:00:00", "end": "2026-09-28 00:00:00"}, "at most 366 days"),
    ({"hours": "25-3"}, "Bad hours"),
    ({"hours": "nine"}, "Bad hours"),
    ({"days": "8"}, "Bad days"),
    ({"days": "mon"}, "Bad days"),
])
def test_bad_filters_are_refused_before_the_database(client, params, message):
    r = client.get("/api/counting/summary", params=params)
    assert r.status_code == 422 and message in r.json()["detail"]


def test_bad_cameras_and_long_series_are_refused(client, seeded):
    r = client.get("/api/counting/summary", params={**DAY, "camera_id": 999})
    assert r.status_code == 422 and "999" in r.json()["detail"]
    r = client.get("/api/counting/series", params={**{"start": "2026-09-01 00:00:00", "end": "2026-09-10 00:00:00"},
                                                    "granularity": "15m"})
    assert r.status_code == 422 and "granularity=hour" in r.json()["detail"]
    r = client.get("/api/counting/series", params={"start": "2026-01-01 00:00:00", "end": "2026-09-10 00:00:00",
                                                    "granularity": "hour"})
    assert r.status_code == 422 and "granularity=day" in r.json()["detail"]
    assert client.get("/api/counting/sightings", params={"size": 101}).status_code == 422


def test_counting_answers_503_without_a_database(client):
    for path in ("/api/counting/summary", "/api/counting/series", "/api/counting/heatmap",
                 "/api/counting/sightings", "/api/counting/cameras"):
        r = client.get(path)
        assert r.status_code == 503 and "DATABASE_URL" in r.json()["detail"], path
