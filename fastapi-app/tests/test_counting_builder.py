"""Sighting builder against a real PostgreSQL (TEST_DATABASE_URL; skipped without it).

Records are made like the box's: a face capture carries faces[0].track_id = F, a body capture
pedestrians[0].track_id = F - 1 for the same person. They go through normalize + save_events +
counting.attach, the same path as a poll; a few tests drive poll_stream end to end.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

import counting
from alarms import ingest
from alarms.normalize import normalize
from counting import backfill
from models import CountBucket, Event, EventSource, Incident, IngestStream, Sighting
from tests.test_alarms_db import BoxHistory, add_rule, rows, setup_box

# Monday 2026-09-28 23:05 in Dhaka (UTC+6).
NOW = datetime(2026, 9, 28, 17, 5, tzinfo=timezone.utc)
D3, OTHER = 2, 1
F = 5000           # a face track; its body track is F - 1


@pytest.fixture
def anyio_backend():
    return "asyncio"


_ids = iter(range(1, 100000))


def record(minor, track, at, device_id=D3, person=None, score=95):
    """One box record: face_capture / body_capture / face_comparison_successful / stranger."""
    alarm_id = next(_ids)
    image = {"value": f"./record_CHN0/{alarm_id}.jpg"}
    out = {
        "additional": {"alarm_id": alarm_id, "alarm_minor": minor, "device_id": device_id},
        "global_info": {"time_ms": str(int(at.timestamp() * 1000))},
        "faces": [], "pedestrians": [], "full_images": [],
    }
    if minor == "body_capture":
        out["pedestrians"] = [{"track_id": track, "image_data": image}]
    else:
        info = [{"person_uuid": person, "person_name": f"Person {person}", "face_score": score}] if person else []
        out["faces"] = [{"track_id": track, "image_data": image, "recognition_info": info}]
    return out


async def save(database, box_id, *records, attach=True) -> list[Event]:
    """What one poll does with these records (without the box)."""
    async with database() as s:
        async with s.begin():
            events = await ingest.save_events(s, box_id, [normalize(r) for r in records], EventSource.POLL, NOW)
            if attach:
                await counting.attach(s, events, box_id)
    return events


async def sightings(database) -> list[Sighting]:
    return await rows(database, Sighting)


async def buckets(database) -> dict:
    async with database() as s:
        found = (await s.exec(select(CountBucket))).all()
    return {(b.camera_id, b.bucket_start): (b.sightings, b.face_sightings, b.body_sightings, b.events) for b in found}


T = NOW - timedelta(minutes=3)       # 23:02 local


@pytest.mark.anyio
async def test_a_face_and_its_body_in_one_batch_are_one_sighting(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("body_capture", F - 1, T), record("face_capture", F, T + timedelta(seconds=1)))

    [s] = await sightings(database)
    assert (s.face_track_id, s.body_track_id, s.event_count, s.box_id) == (F, F - 1, 2, box_id)
    assert s.first_seen_at == T and s.last_seen_at == T + timedelta(seconds=1)
    assert (str(s.local_date), s.local_hour, s.iso_dow) == ("2026-09-28", 23, 1)
    assert s.person_source == "unidentified" and s.person_key == f"t:{cameras[D3]}:2026-09-28:b{F - 1}"
    assert s.recognition_result is None
    assert s.best_face_image_path and s.best_body_image_path
    assert {e.sighting_id for e in await rows(database, Event)} == {s.id}
    assert await buckets(database) == {(cameras[D3], datetime(2026, 9, 28, 17, 0, tzinfo=timezone.utc)): (1, 1, 1, 2)}


@pytest.mark.anyio
async def test_a_body_then_its_face_in_a_later_poll_is_still_one_sighting(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("body_capture", F - 1, T))
    [s] = await sightings(database)
    assert s.person_key.endswith(f":b{F - 1}") and s.face_track_id is None
    await save(database, box_id, record("face_capture", F, T + timedelta(seconds=30)))

    [s] = await sightings(database)
    assert (s.face_track_id, s.body_track_id, s.event_count) == (F, F - 1, 2)


@pytest.mark.anyio
async def test_a_face_first_then_its_body_keeps_one_sighting_and_moves_the_key(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("face_capture", F, T))
    [s] = await sightings(database)
    assert s.person_key.endswith(f":f{F}")
    await save(database, box_id, record("body_capture", F - 1, T + timedelta(seconds=50)))
    [s] = await sightings(database)
    assert s.person_key.endswith(f":b{F - 1}") and s.event_count == 2


@pytest.mark.anyio
async def test_two_halves_saved_apart_are_merged_when_an_earlier_record_arrives(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    # Face at 23:02:00, body first seen 23:16:00: too far apart, so two sightings in two buckets...
    await save(database, box_id, record("face_capture", F, T))
    await save(database, box_id, record("body_capture", F - 1, T + timedelta(minutes=14)))
    assert len(await sightings(database)) == 2
    b1 = (cameras[D3], datetime(2026, 9, 28, 17, 0, tzinfo=timezone.utc))
    b2 = (cameras[D3], datetime(2026, 9, 28, 17, 15, tzinfo=timezone.utc))
    assert await buckets(database) == {b1: (1, 1, 0, 1), b2: (1, 0, 1, 1)}

    # ...until a late body record shows the body was there at 23:02:10.
    await save(database, box_id, record("body_capture", F - 1, T + timedelta(seconds=10)))
    [s] = await sightings(database)
    assert (s.face_track_id, s.body_track_id, s.event_count) == (F, F - 1, 3)
    assert s.first_seen_at == T and s.last_seen_at == T + timedelta(minutes=14)
    assert {e.sighting_id for e in await rows(database, Event)} == {s.id}
    # The second bucket keeps its raw record but no longer has a sighting.
    assert await buckets(database) == {b1: (1, 1, 1, 2), b2: (0, 0, 0, 1)}


@pytest.mark.anyio
async def test_a_bucket_left_with_nothing_is_removed(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    late = T + timedelta(minutes=14)        # 23:16, the next bucket
    async with database() as s:
        async with s.begin():
            [e] = await ingest.save_events(s, box_id, [normalize(record("face_capture", F, late))],
                                           EventSource.POLL, NOW)
            await counting.attach(s, [e], box_id)
            # The record is gone (e.g. a test cleanup); recounting empties the bucket.
            await s.delete(e)
            [sighting] = (await s.exec(select(Sighting))).all()
            await s.delete(sighting)
            await s.flush()
            await counting.builder.rebuild_buckets(s, {(cameras[D3], counting.builder.bucket_start(late))})
    assert await buckets(database) == {}


@pytest.mark.anyio
async def test_a_body_and_face_more_than_two_minutes_apart_are_two_sightings(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("body_capture", F - 1, T), record("face_capture", F, T + timedelta(seconds=121)))
    found = {(s.face_track_id, s.body_track_id) for s in await sightings(database)}
    assert found == {(None, F - 1), (F, None)}


@pytest.mark.anyio
async def test_many_records_of_one_track_are_one_sighting(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, *[record("body_capture", F - 1, T + timedelta(seconds=i * 20)) for i in range(4)])
    await save(database, box_id, record("body_capture", F - 1, T + timedelta(seconds=300)))
    [s] = await sightings(database)
    assert s.event_count == 5 and s.last_seen_at == T + timedelta(seconds=300) and s.first_seen_at == T


@pytest.mark.anyio
async def test_the_same_track_ids_on_another_camera_are_separate(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("body_capture", F - 1, T), record("face_capture", F, T, device_id=OTHER))
    assert sorted(s.camera_id for s in await sightings(database)) == sorted([cameras[D3], cameras[OTHER]])


@pytest.mark.anyio
@pytest.mark.parametrize("first, second", [("face_capture", "body_capture"), ("body_capture", "face_capture")])
async def test_a_pass_across_midnight_is_one_sighting(database, fake_box, first, second):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    before = datetime(2026, 9, 28, 17, 59, 59, tzinfo=timezone.utc)        # 23:59:59 in Dhaka
    tracks = {"face_capture": F, "body_capture": F - 1}
    await save(database, box_id, record(first, tracks[first], before))
    await save(database, box_id, record(second, tracks[second], before + timedelta(seconds=2)))
    [s] = await sightings(database)
    assert (s.face_track_id, s.body_track_id) == (F, F - 1)
    assert str(s.local_date) == "2026-09-28" and s.local_hour == 23


@pytest.mark.anyio
async def test_a_recognition_names_the_sighting_and_a_stranger_record_doesnt_undo_it(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("body_capture", F - 1, T), record("face_capture", F, T))
    await save(database, box_id, record("face_comparison_successful", F, T + timedelta(seconds=1), person="17", score=80))
    await save(database, box_id, record("stranger", F, T + timedelta(seconds=2)))
    await save(database, box_id, record("face_comparison_successful", F, T + timedelta(seconds=3), person="18", score=70))

    [s] = await sightings(database)
    assert (s.person_source, s.person_key, s.recognition_result) == ("recognized", "p:17", "matched")
    assert (s.person_name, s.best_match_score, s.event_count) == ("Person 17", 80, 5)


@pytest.mark.anyio
async def test_a_stranger_record_marks_the_sighting_but_doesnt_identify_it(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("stranger", F, T))
    [s] = await sightings(database)
    assert (s.person_source, s.recognition_result) == ("unidentified", "stranger")


@pytest.mark.anyio
async def test_polling_the_same_window_again_changes_nothing(database, fake_box):
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    history.records = [record("body_capture", F - 1, NOW - timedelta(seconds=40)),
                       record("face_capture", F, NOW - timedelta(seconds=39)),
                       record("face_capture", F + 10, NOW - timedelta(seconds=20))]
    assert await ingest.poll_stream(database, box_id, IngestStream.CAPTURE, NOW) == 3
    before = (await sightings(database), await buckets(database))
    assert len(before[0]) == 2

    assert await ingest.poll_stream(database, box_id, IngestStream.CAPTURE, NOW + timedelta(seconds=5)) == 0
    after = (await sightings(database), await buckets(database))
    assert [(s.id, s.event_count) for s in after[0]] == [(s.id, s.event_count) for s in before[0]]
    assert after[1] == before[1]


@pytest.mark.anyio
async def test_backfill_counts_old_events_once(database, fake_box):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await save(database, box_id, record("body_capture", F - 1, T), record("face_capture", F, T + timedelta(seconds=1)),
               record("face_capture", F + 10, T + timedelta(seconds=5), device_id=OTHER), attach=False)
    # Halves split across batches still pair up.
    assert await backfill.run(database, batch_size=1, quiet=True) == 3
    found = await sightings(database)
    assert {(s.face_track_id, s.body_track_id) for s in found} == {(F, F - 1), (F + 10, None)}
    assert all(e.sighting_id for e in await rows(database, Event))
    assert await backfill.run(database, quiet=True) == 0
    assert len(await sightings(database)) == 2


@pytest.mark.anyio
async def test_alarms_still_fire_in_a_batch_that_builds_sightings(database, fake_box):
    history = BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    await add_rule(database, box_id, cameras[D3])
    history.records = [record("stranger", F, NOW - timedelta(seconds=30))]
    assert await ingest.poll_stream(database, box_id, IngestStream.RECOGNITION, NOW) == 1

    [incident] = await rows(database, Incident)
    [s] = await sightings(database)
    assert incident.is_stranger and incident.track_id == F and incident.sighting_id == s.id
