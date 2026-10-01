"""Alarms against a real PostgreSQL (TEST_DATABASE_URL; skipped without it).

The box is the FakeBox from conftest: alarm_history answers from a list of records filtered by the
requested time window, like the real box.
"""
import asyncio
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlmodel import select

from alarms import ingest, mailer
from models import (AlarmRule, AlarmRuleCamera, AlarmRuleRecipient, AlarmRuleWindow, Camera, Contact, Event,
                    Incident, IncidentEvent, IngestCursor, IngestStream, Notification)
from tests.conftest import DEVICE_CONFIG

# Monday 2026-09-28 23:05 in Dhaka (UTC+6).
NOW = datetime(2026, 9, 28, 17, 5, tzinfo=timezone.utc)
D3 = 2          # box device_id of IPCAM-D3
OTHER = 1


@pytest.fixture
def anyio_backend():
    return "asyncio"


def box_record(alarm_id, minor="stranger", device_id=D3, at=NOW - timedelta(seconds=30), track=100):
    face = {"track_id": track, "image_data": {"value": f"./record_CHN0/{alarm_id}_face.jpg"},
            "recognition_info": [{"person_uuid": "17", "person_name": "Ada", "face_score": 95}]
            if minor == "face_comparison_successful" else []}
    return {
        "additional": {"alarm_id": alarm_id, "alarm_minor": minor, "device_id": device_id},
        "global_info": {"time_ms": str(int(at.timestamp() * 1000))},
        "faces": [face] if minor != "body_capture" else [],
        "pedestrians": [{"track_id": track + 1, "image_data": {"value": f"./record_CHN0/{alarm_id}_body.jpg"}}]
        if minor == "body_capture" else [],
        "full_images": [{"image_data": {"value": f"./record_CHN0/{alarm_id}_full.jpg"}}],
    }


class BoxHistory:
    """alarm_history on the FakeBox: returns the stored records of the requested kinds and window."""

    def __init__(self, fake_box):
        self.records: list[dict] = []
        fake_box.replies[("POST", "/device_access/device_config")] = DEVICE_CONFIG
        fake_box.replies[("POST", "/device_alarm/alarm_history")] = self.answer

    def answer(self, body):
        cond = body["query_condition"]
        minors = {m for t in cond["alarm_type"] for m in t["minor_type"]}
        start, end = int(cond["start_time"]), int(cond["end_time"])
        hits = [r for r in self.records if r["additional"]["alarm_minor"] in minors
                and start <= int(r["global_info"]["time_ms"]) <= end]
        hits.sort(key=lambda r: -int(r["global_info"]["time_ms"]))      # newest first, like the box
        page = hits[body["offset"]:body["offset"] + body["size"]]
        return {"total_count": len(hits), "return_count": len(page), "list": page}


async def setup_box(sessions) -> tuple[int, dict[int, int]]:
    async with sessions() as s:
        async with s.begin():
            box_id = await ingest.ensure_box(s)
            await ingest.sync_cameras(s, box_id)
        cameras = {c.device_id: c.id for c in (await s.exec(select(Camera))).all()}
    return box_id, cameras


async def add_rule(sessions, box_id, camera_id, *, kinds=("stranger", "matched"), recipients=2, **fields) -> int:
    async with sessions() as s:
        async with s.begin():
            contacts = [Contact(name=f"Admin {i}", email=f"admin{i}@example.org") for i in range(recipients)]
            s.add_all(contacts)
            rule = AlarmRule(box_id=box_id, name=fields.pop("name", "Night watch D3"), event_kinds=list(kinds),
                             **fields)
            s.add(rule)
            await s.flush()
            s.add(AlarmRuleCamera(rule_id=rule.id, camera_id=camera_id))
            s.add_all([AlarmRuleWindow(rule_id=rule.id, iso_dow=d, start_time=time(22), end_time=time(6))
                       for d in range(1, 8)])
            s.add_all([AlarmRuleRecipient(rule_id=rule.id, contact_id=c.id) for c in contacts])
        return rule.id


async def rows(sessions, model):
    async with sessions() as s:
        return list((await s.exec(select(model).order_by(model.id if hasattr(model, "id") else None))).all())


# ---------- ingest + rules ----------

@pytest.mark.anyio
async def test_a_stranger_on_d3_after_hours_raises_one_alarm_and_queues_emails(database, fake_box):
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await add_rule(database, box_id, cameras[D3])
    history.records = [
        box_record(1, "stranger"),
        box_record(2, "stranger", device_id=OTHER, track=300),    # other camera: saved, no alarm
        box_record(3, "face_capture"),                            # kind the rule doesn't watch
    ]

    assert await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW) == 2
    assert await ingest.poll_stream(database, box_id, IngestStream.CAPTURE, NOW) == 1

    [incident] = await rows(database, Incident)
    assert incident.camera_id == cameras[D3] and incident.is_stranger and incident.track_id == 100
    assert incident.snapshot_path == "./record_CHN0/1_face.jpg"
    assert incident.delay_seconds == 30 and not incident.is_delayed
    assert incident.rule_snapshot["name"] == "Night watch D3"
    notifications = await rows(database, Notification)
    assert sorted(n.to_address for n in notifications) == ["admin0@example.org", "admin1@example.org"]
    assert notifications[0].subject == "[WARNING] Night watch D3: A stranger on IPCAM-D3 at 23:04 (2026-09-28)"

    # The first poll looks back 5 minutes, in epoch ms, with the box UI's ext block.
    sent = fake_box.sent("POST", "/device_alarm/alarm_history")[0]["query_condition"]
    assert sent["start_time"] == str(int((NOW - timedelta(minutes=5)).timestamp() * 1000))
    assert sent["ext"] == {"query_type": 0, "de_dup": 0}

    # Polling the same window again saves nothing and fires nothing.
    assert await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW + timedelta(seconds=5)) == 0
    assert len(await rows(database, Incident)) == 1
    assert len(await rows(database, Event)) == 3
    [cursor, _] = sorted(await rows(database, IngestCursor), key=lambda c: c.stream != "recognition")
    assert cursor.last_occurred_at == NOW + timedelta(seconds=5) and cursor.consecutive_failures == 0


@pytest.mark.anyio
async def test_a_box_clock_running_ahead_doesnt_hold_alarms_back(database, fake_box):
    # This PC says 15:38; the box stamped the walk-past 15:40 (its clock is ~3 minutes ahead).
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await add_rule(database, box_id, cameras[D3])
    history.records = [box_record(1, at=NOW + timedelta(minutes=2, seconds=20))]

    assert await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW) == 1
    [incident] = await rows(database, Incident)
    assert incident.delay_seconds == 0 and not incident.is_delayed
    assert len(await rows(database, Notification)) == 2

    async with database() as s:
        cursor = await s.get(IngestCursor, (box_id, "recognition"))
    assert cursor.last_occurred_at == NOW                 # the cursor stays at this PC's time
    # Later polls read it again, but it isn't saved or alarmed twice.
    assert await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW + timedelta(minutes=3)) == 0
    assert len(await rows(database, Incident)) == 1


@pytest.mark.anyio
async def test_during_the_cooldown_events_join_the_open_alarm(database, fake_box):
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await add_rule(database, box_id, cameras[D3], cooldown_seconds=300)
    history.records = [box_record(1, at=NOW - timedelta(seconds=60), track=100),
                       box_record(2, at=NOW - timedelta(seconds=30), track=200)]
    await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW)

    [incident] = await rows(database, Incident)
    assert incident.event_count == 2 and incident.last_event_at == NOW - timedelta(seconds=30)
    assert len(await rows(database, IncidentEvent)) == 2
    assert len(await rows(database, Notification)) == 2           # one email per recipient, not per event

    later = NOW + timedelta(minutes=6)
    history.records.append(box_record(3, at=later - timedelta(seconds=10), track=300))
    await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, later)
    assert len(await rows(database, Incident)) == 2


@pytest.mark.anyio
async def test_track_scope_gives_each_person_track_its_own_alarm(database, fake_box):
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await add_rule(database, box_id, cameras[D3], dedupe_scope="track", recipients=0)
    history.records = [box_record(1, track=100, at=NOW - timedelta(seconds=50)),
                       box_record(2, track=200, at=NOW - timedelta(seconds=40)),
                       box_record(3, track=100, at=NOW - timedelta(seconds=30))]
    await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW)

    incidents = await rows(database, Incident)
    assert sorted((i.track_id, i.event_count) for i in incidents) == [(100, 2), (200, 1)]


@pytest.mark.anyio
async def test_events_outside_the_window_or_for_other_people_are_ignored(database, fake_box):
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await add_rule(database, box_id, cameras[D3], match_mode="strangers", kinds=("stranger",))
    noon = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)           # 12:00 in Dhaka
    history.records = [box_record(1, "face_comparison_successful"), box_record(2, at=noon - timedelta(seconds=30))]
    await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW)
    await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, noon)
    assert await rows(database, Incident) == []


@pytest.mark.anyio
async def test_a_late_event_is_saved_as_delayed_and_not_emailed(database, fake_box):
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    rule_id = await add_rule(database, box_id, cameras[D3], max_delay_seconds=300)
    async with database() as s:
        async with s.begin():      # the portal was down: the cursor is 20 minutes behind
            s.add(IngestCursor(box_id=box_id, stream="recognition", last_occurred_at=NOW - timedelta(minutes=20)))
    history.records = [box_record(1, at=NOW - timedelta(minutes=10))]
    await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW)

    [incident] = await rows(database, Incident)
    assert incident.is_delayed and incident.delay_seconds == 600
    assert await rows(database, Notification) == []
    async with database() as s:
        cursor = await s.get(IngestCursor, (box_id, "recognition"))
    assert cursor.last_occurred_at == NOW - timedelta(minutes=6)       # caught up one 15-minute slice
    assert rule_id


@pytest.mark.anyio
async def test_box_errors_are_recorded_on_the_cursor(database, fake_box):
    from tests.conftest import box_error
    fake_box.replies[("POST", "/device_access/device_config")] = DEVICE_CONFIG
    box_id, _ = await setup_box(database)
    fake_box.replies[("POST", "/device_alarm/alarm_history")] = box_error(5, "busy")
    with pytest.raises(Exception):
        await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW)
    async with database() as s:
        cursor = await s.get(IngestCursor, (box_id, "recognition"))
    assert cursor.consecutive_failures == 1 and "busy" in cursor.last_error and cursor.last_occurred_at is None


# ---------- email queue ----------

CFG = mailer.SmtpConfig(host="smtp.example.org", port=587, user="", password="", sender="alarms@example.org",
                        sender_name="B4H Portal", security="starttls", portal_url="http://portal")


async def queued_alarm(database, fake_box) -> None:
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await add_rule(database, box_id, cameras[D3])
    history.records = [box_record(1)]
    await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW)


@pytest.mark.anyio
async def test_queued_emails_are_sent_with_the_snapshot(database, fake_box, monkeypatch):
    await queued_alarm(database, fake_box)
    fake_box.images["/device_storage/get_image"] = (b"\xff\xd8\xffJPEG", "image/jpeg")
    sent = []

    async def fake_send(cfg, msg):
        sent.append(msg)
    monkeypatch.setattr(mailer, "send", fake_send)

    assert await mailer.run_once(database, fake_box, CFG) == 2
    assert {m["To"] for m in sent} == {"admin0@example.org", "admin1@example.org"}
    assert [a.get_filename() for a in sent[0].iter_attachments()] == ["snapshot.jpg", "panorama.jpg"]
    assert all(n.status == "sent" and n.sent_at for n in await rows(database, Notification))
    assert await mailer.run_once(database, fake_box, CFG) == 0         # nothing sent twice


@pytest.mark.anyio
async def test_failed_emails_are_retried_then_given_up(database, fake_box, monkeypatch):
    await queued_alarm(database, fake_box)

    async def refuse(cfg, msg):
        raise ConnectionRefusedError("smtp down")
    monkeypatch.setattr(mailer, "send", refuse)

    assert await mailer.run_once(database, fake_box, CFG) == 0
    for n in await rows(database, Notification):
        assert n.status == "pending" and n.attempts == 1 and "smtp down" in n.last_error
        assert n.next_attempt_at > datetime.now(timezone.utc)          # waits before the next try

    async with database() as s:
        async with s.begin():
            for n in (await s.exec(select(Notification))).all():
                n.next_attempt_at, n.max_attempts = datetime.now(timezone.utc) - timedelta(seconds=1), 2
                s.add(n)
    await mailer.run_once(database, fake_box, CFG)
    assert {n.status for n in await rows(database, Notification)} == {"failed"}


# ---------- API ----------

def rule_body(camera_id, **overrides):
    body = {
        "name": "Night watch D3", "severity": "critical", "event_kinds": ["stranger", "matched"],
        "match_mode": "anyone", "camera_ids": [camera_id],
        "windows": [{"iso_dow": d, "start": "22:00", "end": "06:00"} for d in range(1, 8)],
        "recipient_ids": [],
    }
    body.update(overrides)
    return body


def test_status_without_a_database(client):
    body = client.get("/api/alarms/status").json()
    assert body["database"] is False and body["open_incidents"] == 0


def test_api_manages_recipients_rules_and_incidents(client, database, fake_box):
    history = BoxHistory(fake_box)
    cameras = client.get("/api/alarms/cameras").json()
    assert [c["name"] for c in cameras] == ["Hikvision", "IPCAM-D3", "CAM3-D4"]
    d3 = next(c["id"] for c in cameras if c["device_id"] == D3)

    # recipients
    r = client.post("/api/alarms/contacts", json={"name": "Guard", "email": "Guard@Example.org"})
    assert r.status_code == 201 and r.json()["email"] == "guard@example.org"
    guard = r.json()["id"]
    assert client.post("/api/alarms/contacts", json={"name": "Again", "email": "guard@example.org"}).status_code == 409
    assert client.post("/api/alarms/contacts", json={"name": "Bad", "email": "not-an-email"}).status_code == 422

    # rules: validation
    assert client.post("/api/alarms/rules", json=rule_body(d3, match_mode="strangers",
                                                           event_kinds=["matched"])).status_code == 422
    assert client.post("/api/alarms/rules", json=rule_body(9999)).status_code == 422
    assert client.post("/api/alarms/rules", json=rule_body(d3, recipient_ids=list(range(1, 7)))).status_code == 422
    assert client.post("/api/alarms/rules", json=rule_body(d3, windows=[
        {"iso_dow": 1, "start": "10:00", "end": "10:00"}])).status_code == 422

    r = client.post("/api/alarms/rules", json=rule_body(d3, recipient_ids=[guard]))
    assert r.status_code == 201, r.text
    rule = r.json()
    assert rule["camera_ids"] == [d3] and rule["recipient_ids"] == [guard] and rule["version"] == 1
    assert rule["windows"][0] == {"iso_dow": 1, "start": "22:00", "end": "06:00"}
    assert client.post("/api/alarms/rules", json=rule_body(d3)).status_code == 409       # same name

    # editing: a stale version is refused
    edited = {**rule_body(d3, recipient_ids=[guard], cooldown_seconds=60), "version": 1}
    assert client.put(f"/api/alarms/rules/{rule['id']}", json=edited).json()["version"] == 2
    assert client.put(f"/api/alarms/rules/{rule['id']}", json=edited).status_code == 409
    assert client.patch(f"/api/alarms/rules/{rule['id']}/enabled", json={"is_enabled": False}).json()["is_enabled"] is False
    client.patch(f"/api/alarms/rules/{rule['id']}/enabled", json={"is_enabled": True})

    # an alarm fires
    history.records = [box_record(1)]
    asyncio.run(ingest.poll_stream(database, 1, IngestStream.RECOGNITION, NOW))
    status = client.get("/api/alarms/status").json()
    assert status["database"] is True and status["open_incidents"] == 1 and status["notifications"]["pending"] == 1

    page = client.get("/api/alarms/incidents", params={"status": ["open"], "camera_id": d3}).json()
    assert page["total"] == 1
    item = page["items"][0]
    assert item["camera_name"] == "IPCAM-D3" and item["severity"] == "critical" and item["is_stranger"]
    assert client.get("/api/alarms/incidents", params={"start": "2026-09-29 00:00:00"}).json()["total"] == 0

    detail = client.get(f"/api/alarms/incidents/{item['public_id']}").json()      # the email link
    assert detail["id"] == item["id"] and len(detail["events"]) == 1
    assert detail["notifications"][0]["to_address"] == "guard@example.org"
    assert client.get("/api/alarms/incidents/not-a-ref").status_code == 404

    r = client.patch(f"/api/alarms/incidents/{item['id']}", json={"status": "acknowledged", "by": "Nishat",
                                                                   "note": "Checked the camera"})
    assert r.json()["status"] == "acknowledged" and r.json()["acknowledged_by"] == "Nishat"
    assert client.get("/api/alarms/status").json()["open_incidents"] == 0

    # deleting the rule keeps its incidents
    assert client.delete(f"/api/alarms/rules/{rule['id']}").status_code == 200
    kept = client.get(f"/api/alarms/incidents/{item['id']}").json()
    assert kept["rule_id"] is None and kept["rule_name"] == "Night watch D3"
    assert client.delete(f"/api/alarms/contacts/{guard}").status_code == 200


def test_api_answers_503_without_a_database(client):
    r = client.get("/api/alarms/rules")
    assert r.status_code == 503 and "DATABASE_URL" in r.json()["detail"]
