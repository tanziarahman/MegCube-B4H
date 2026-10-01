"""Alarm logic that needs no database: box record -> event, time windows, rule matching, email content."""
from datetime import datetime, time, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from alarms import mailer
from alarms.normalize import normalize
from alarms.rules import RuleSpec, Window
from models import EventKind

DHAKA = ZoneInfo("Asia/Dhaka")


def record(minor="face_comparison_successful", **extra):
    face = {
        "track_id": 5727190, "age": 31, "gender": 2,
        "image_data": {"image_data_format": 2, "value": "./record_CHN0/face.jpg"},
        "recognition_info": [
            {"person_uuid": "17", "person_name": "Ada Lovelace", "face_score": 0.96,
             "group_info": [{"group_id": "1", "group_name": "Staff"}]},
            {},
        ],
    }
    base = {
        "additional": {"alarm_id": 12345, "alarm_minor": minor, "device_id": 2},
        "global_info": {"time_ms": "1727600000000"},
        "faces": [face],
        "pedestrians": [{"track_id": 5727189, "coat_color": 3,
                         "image_data": {"value": "./record_CHN0/body.jpg"}}],
        "full_images": [{"image_data": {"value": "./record_CHN0/full.jpg"}}],
    }
    base.update(extra)
    return base


# ---------- normalize ----------

def test_a_recognition_record_names_the_person():
    row = normalize(record())
    assert row["kind"] == EventKind.MATCHED
    assert (row["alarm_id"], row["device_id"]) == (12345, 2)
    assert row["occurred_at"] == datetime.fromtimestamp(1727600000, timezone.utc)
    assert (row["face_track_id"], row["body_track_id"]) == (5727190, 5727189)
    assert (row["person_uuid"], row["person_name"]) == ("17", "Ada Lovelace")
    assert (row["group_ids"], row["group_names"]) == (["1"], ["Staff"])
    assert row["match_score"] == 96                      # 0-1 scores become 0-100
    assert row["face_image_path"] == "./record_CHN0/face.jpg"
    assert row["panorama_path"] == "./record_CHN0/full.jpg"
    assert row["attributes"] == {"age": 31, "gender": 2, "body": {"coat_color": 3}}


def test_a_stranger_is_not_named_after_its_closest_library_face():
    row = normalize(record("stranger"))
    assert row["kind"] == EventKind.STRANGER
    assert row["person_uuid"] is None and row["person_name"] is None and row["group_names"] is None


def test_records_we_dont_keep_are_skipped():
    assert normalize(record("pedestrian")) is None                    # a structure detection
    assert normalize({**record(), "global_info": {}}) is None          # no time
    assert normalize({**record(), "additional": {"alarm_minor": "stranger"}}) is None   # no id / camera


# ---------- time windows ----------

def local(day: int, hh: int, mm: int = 0) -> datetime:
    """2026-09-28 is a Monday."""
    return datetime(2026, 9, 28 + day, hh, mm, tzinfo=DHAKA)


def test_an_overnight_window_belongs_to_the_day_it_starts():
    monday_night = Window(1, time(22), time(6))
    assert monday_night.contains(local(0, 23))         # Mon 23:00
    assert monday_night.contains(local(1, 5, 59))      # Tue 05:59
    assert not monday_night.contains(local(1, 6))      # Tue 06:00: end is exclusive
    assert not monday_night.contains(local(0, 21, 59))
    assert not monday_night.contains(local(1, 23))     # Tue night isn't Mon night
    assert not monday_night.contains(local(0, 3))      # Mon early morning belongs to Sun night


def test_a_daytime_window():
    office = Window(3, time(9), time(17))
    assert office.contains(local(2, 9)) and office.contains(local(2, 16, 59))
    assert not office.contains(local(2, 17)) and not office.contains(local(1, 12))


# ---------- rule matching ----------

def spec(**overrides) -> RuleSpec:
    values = dict(
        id=1, name="Night watch", severity="warning", event_kinds=frozenset({"matched", "stranger", "face_capture"}),
        match_mode="anyone", min_match_score=None, min_liveness=None, tz=DHAKA, cooldown_seconds=300,
        dedupe_scope="camera", max_delay_seconds=300, email_delayed=False, attach_snapshot=True,
        camera_ids=frozenset({3}), windows=[Window(d, time(22), time(6)) for d in range(1, 8)],
    )
    values.update(overrides)
    return RuleSpec(**values)


def event(**overrides):
    values = dict(camera_id=3, kind="stranger", occurred_at=local(0, 23).astimezone(timezone.utc),
                  person_uuid=None, group_ids=None, group_names=None, match_score=40.0, liveness_score=None)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_someone_on_the_watched_camera_after_hours_matches():
    assert spec().matches(event())


def test_wrong_camera_kind_or_time_doesnt_match():
    assert not spec().matches(event(camera_id=4))
    assert not spec().matches(event(kind="body_capture"))
    assert not spec().matches(event(occurred_at=local(0, 12).astimezone(timezone.utc)))


def test_times_are_compared_in_the_rules_time_zone():
    # 16:30 UTC is 22:30 in Dhaka: inside the 22:00-06:00 window.
    assert spec().matches(event(occurred_at=datetime(2026, 9, 28, 16, 30, tzinfo=timezone.utc)))
    assert not spec(tz=ZoneInfo("UTC")).matches(event(occurred_at=datetime(2026, 9, 28, 16, 30, tzinfo=timezone.utc)))


def test_a_rule_without_windows_is_always_active():
    assert spec(windows=[]).matches(event(occurred_at=local(0, 12).astimezone(timezone.utc)))


def test_who_the_rule_watches():
    known = event(kind="matched", person_uuid="17", group_ids=["1"], group_names=["Staff"], match_score=95)
    assert spec(match_mode="strangers").matches(event())
    assert not spec(match_mode="strangers").matches(known)
    assert spec(match_mode="known").matches(known)
    assert not spec(match_mode="known").matches(event())
    assert spec(match_mode="targets", person_ids=frozenset({"17"})).matches(known)
    assert not spec(match_mode="targets", person_ids=frozenset({"18"})).matches(known)
    assert spec(match_mode="targets", group_ids=frozenset({"1"})).matches(known)
    # Records may carry only group names: matched by the label, ignoring case.
    by_name = event(kind="matched", person_uuid="17", group_names=["Staff"], match_score=95)
    assert spec(match_mode="targets", group_ids=frozenset({"9"}), group_labels=frozenset({"staff"})).matches(by_name)


def test_score_and_liveness_thresholds():
    known = event(kind="matched", person_uuid="17", match_score=70)
    assert not spec(min_match_score=80).matches(known)
    assert spec(min_match_score=80).matches(event())           # a stranger's score is a non-match: ignored
    assert not spec(min_liveness=60).matches(event(liveness_score=20))
    assert spec(min_liveness=60).matches(event(liveness_score=None))   # liveness off on the box: passes


def test_enum_kinds_match_like_plain_strings():
    assert spec().matches(event(kind=EventKind.STRANGER))


# ---------- email ----------

def incident(**overrides):
    values = dict(rule_name="Night watch", severity="critical", person_name=None, is_stranger=True,
                  occurred_at=datetime(2026, 9, 28, 17, 5, tzinfo=timezone.utc), track_id=5727190,
                  is_delayed=False, delay_seconds=4, public_id="0b5c6c1e-0000-4000-8000-000000000001",
                  rule_snapshot={"timezone": "Asia/Dhaka"})
    values.update(overrides)
    return SimpleNamespace(**values)


def test_subject_and_message():
    cfg = mailer.SmtpConfig(host="smtp.x", port=587, user="", password="", sender="alarms@x.org",
                            sender_name="B4H Portal", security="starttls", portal_url="http://portal:3000")
    subject = mailer.subject_for(incident(), "IPCAM-D3", DHAKA)
    assert subject == "[CRITICAL] Night watch: A stranger on IPCAM-D3 at 23:05 (2026-09-28)"
    msg = mailer.build_message(cfg, "guard@x.org", subject, incident(), "IPCAM-D3",
                               [("snapshot.jpg", b"\xff\xd8\xffdata", "image/jpeg")])
    assert msg["To"] == "guard@x.org" and "B4H Portal" in msg["From"]
    text = msg.get_body(("plain",)).get_content()
    assert "Camera: IPCAM-D3" in text and "2026-09-28 23:05:00 (Asia/Dhaka)" in text
    assert "http://portal:3000/alarms/0b5c6c1e-0000-4000-8000-000000000001" in text
    assert [a.get_filename() for a in msg.iter_attachments()] == ["snapshot.jpg"]


def test_retry_gaps_grow_and_cap():
    assert [mailer.retry_gap(n).total_seconds() for n in (1, 2, 3)] == [30, 60, 120]
    assert mailer.retry_gap(20).total_seconds() == 1800
