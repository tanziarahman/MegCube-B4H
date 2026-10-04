"""Face and body fingerprints and the "different people" estimate.

Grouping and the real models' refusals run anywhere (the model test is skipped without the model
files); the worker and summary tests need TEST_DATABASE_URL. The worker tests use fake embedders
(fingerprint = a vector chosen per picture), so they don't depend on the models.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest
from sqlalchemy import update
from sqlmodel import col

from alarms import worker as alarm_worker
from faces import grouping, worker
from faces.embedder import BodyEmbedder, FaceEmbedder, Fingerprint, models_present
from models import Sighting
from tests.test_alarms_db import BoxHistory, rows, setup_box
from tests.test_counting_api import DAY, MONDAY, at
from tests.test_counting_builder import F, T, record, save


@pytest.fixture
def anyio_backend():
    return "asyncio"


def unit(*values) -> list[float]:
    v = np.zeros(128)
    v[:len(values)] = values
    return list(v / np.linalg.norm(v))


A, B, C = unit(1), unit(0, 1), unit(0, 0, 1)
A_ISH = unit(1, 0.3)          # cosine 0.96 with A: the same person, another picture


# ---------- grouping ----------

MONDAY_9 = datetime(2026, 9, 28, 3, 0, tzinfo=timezone.utc)


def walk(minute: int, face=None, body=None, camera_id=2, day=date(2026, 9, 28), seconds=5) -> grouping.WalkPast:
    at = MONDAY_9 + timedelta(minutes=minute)
    return grouping.WalkPast(face=face, body=body, day=day, camera_id=camera_id, first_seen_at=at,
                             last_seen_at=at + timedelta(seconds=seconds))


def people(walks, threshold=grouping.MATCH_THRESHOLD) -> list[int]:
    return grouping.group(*grouping.similarities(walks), threshold)


def test_alike_people_group_together_and_different_ones_dont():
    walks = [walk(0, body=A), walk(5, body=B), walk(10, body=A_ISH), walk(15, body=C), walk(20, body=B)]
    assert people(walks) == [0, 1, 0, 2, 1]


def test_clothes_only_count_within_a_day_and_faces_link_days():
    tuesday = date(2026, 9, 29)
    # Same clothes on two days, no faces: can't be linked, so two people.
    assert len(set(people([walk(0, body=A), walk(1500, body=A, day=tuesday)]))) == 2
    # The same face on both days links them.
    assert len(set(people([walk(0, face=A, body=B), walk(1500, face=A_ISH, body=C, day=tuesday)]))) == 1


def test_body_and_face_are_weighed_together():
    # Same clothes (1.0), different faces (0.0): 0.6 * 1 + 0.4 * 0 = 0.6, still one person at 0.35.
    assert len(set(people([walk(0, face=A, body=C), walk(5, face=B, body=C)]))) == 1
    # Different clothes (0.0), same face (1.0): 0.4, one person at 0.35, two at 0.45.
    pair = [walk(0, face=A, body=B), walk(5, face=A, body=C)]
    assert len(set(people(pair, 0.35))) == 1 and len(set(people(pair, 0.45))) == 2


def test_two_people_on_camera_together_are_never_merged():
    # Identical clothes, but in view at the same moment on one camera: two people. On another camera
    # at the same moment they can be one person (a camera overlap), unless something else says not.
    assert len(set(people([walk(0, body=A, seconds=30), walk(0, body=A, seconds=30)]))) == 2
    assert len(set(people([walk(0, body=A, seconds=30), walk(0, body=A, camera_id=1, seconds=30)]))) == 1
    # A third look-alike can't join a group that already holds someone seen together with it.
    assert len(set(people([walk(0, body=A), walk(10, body=A, seconds=60), walk(10, body=A_ISH, seconds=60)]))) == 2


def test_the_count_is_a_range_from_loose_to_strict():
    borderline = unit(1, 2.511)  # cosine 0.37 with A: one person at 0.30 and 0.35, two at 0.40
    walks = [walk(0, body=A), walk(5, body=borderline), walk(10, body=C)]
    assert grouping.count_people(walks) == {"people": 2, "low": 2, "high": 3}
    assert grouping.count_people([]) == {"people": 0, "low": 0, "high": 0}


def test_too_many_walk_pasts_give_no_estimate(monkeypatch):
    monkeypatch.setattr(grouping, "MAX_WALK_PASTS", 2)
    assert grouping.count_people([walk(0, body=A), walk(1, body=B), walk(2, body=C)]) is None
    assert grouping.labels([walk(0, body=A), walk(1, body=B), walk(2, body=C)]) is None


@pytest.mark.skipif(not models_present(), reason="models not downloaded")
def test_the_real_models_refuse_what_they_cant_use():
    import cv2
    embedder = FaceEmbedder()
    assert embedder.fingerprint(b"not a picture") is None
    blank = cv2.imencode(".jpg", np.full((200, 160, 3), 200, np.uint8))[1].tobytes()
    assert embedder.fingerprint(blank) is None
    body = BodyEmbedder()
    assert body.fingerprint(b"not a picture") is None
    assert body.fingerprint(cv2.imencode(".jpg", np.full((40, 20, 3), 200, np.uint8))[1].tobytes()) is None   # too small
    vector = body.fingerprint(cv2.imencode(".jpg", np.full((256, 128, 3), 120, np.uint8))[1].tobytes())
    assert len(vector) == 768 and abs(sum(v * v for v in vector) - 1) < 1e-6


# ---------- worker ----------

class FakeBody:
    """Picture path -> vector; paths not listed are unusable."""

    def __init__(self, bodies: dict[str, list[float]] | None = None):
        self.bodies = bodies or {}

    def fingerprint(self, data: bytes):
        return self.bodies.get(data.decode())


class FakeEmbedder:
    """Picture path -> vector; paths not listed have no usable face."""

    def __init__(self, faces: dict[str, list[float]]):
        self.faces = faces
        self.seen: list[str] = []

    def fingerprint(self, data: bytes):
        path = data.decode()
        self.seen.append(path)
        vector = self.faces.get(path)
        return Fingerprint(vector=vector, detection_score=0.9, face_pixels=60) if vector else None


@pytest.fixture
def pictures(monkeypatch):
    """The box has every picture except those in the returned set."""
    gone: set[str] = set()

    async def fake_box_image(path):
        return None if path in gone else (path.encode(), "image/jpeg")
    monkeypatch.setattr(worker, "box_image", fake_box_image)
    return gone


def face_path(event_record) -> str:
    return event_record["faces"][0]["image_data"]["value"]


@pytest.mark.anyio
async def test_each_walk_past_gets_one_fingerprint_once(database, fake_box, pictures):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    clear, blurry, gone_rec = (record("face_capture", F, T), record("face_capture", F + 10, T),
                               record("face_capture", F + 20, T))
    second_clear = record("face_capture", F, T + timedelta(seconds=1))
    await save(database, box_id, clear, second_clear, blurry, gone_rec,
               record("body_capture", F + 29, T))                        # body only: nothing to fingerprint
    pictures.add(face_path(gone_rec))
    fake = FakeEmbedder({face_path(clear): A, face_path(second_clear): A_ISH})

    body_only = await rows(database, Sighting)
    body_path = next(s.best_body_image_path for s in body_only if s.face_track_id is None)
    assert await worker.process_pending(database, face_embedder=fake, body_embedder=FakeBody({body_path: B})) == 4
    found = {s.face_track_id: s for s in await rows(database, Sighting)}
    assert np.allclose(found[F].face_embedding, worker._average([A, A_ISH]))
    assert found[F].embedding_model == "sface-2021dec"
    assert found[F + 10].face_embedding is None and found[F + 10].embedding_model == worker.NO_FACE
    assert found[F + 20].embedding_model == worker.NO_FACE              # the box no longer had it
    assert found[None].embedding_model is None and found[None].body_embedding == B
    assert found[None].body_embedding_model == "youtu-reid-2021nov"
    assert await worker.process_pending(database, face_embedder=fake, body_embedder=FakeBody()) == 0   # nothing twice


@pytest.mark.anyio
async def test_a_merge_keeps_the_fingerprint(database, fake_box, pictures):
    BoxHistory(fake_box)
    box_id, cameras = await setup_box(database)
    # The body is seen first 14 minutes after the face: two walk-pasts, the body's row older.
    await save(database, box_id, record("body_capture", F - 1, T + timedelta(minutes=14)))
    face = record("face_capture", F, T)
    await save(database, box_id, face)
    await worker.process_pending(database, face_embedder=FakeEmbedder({face_path(face): A}), body_embedder=FakeBody())
    # A late body record from T + 10 s pairs them; the body's row is kept and takes the fingerprint.
    await save(database, box_id, record("body_capture", F - 1, T + timedelta(seconds=10)))
    [s] = await rows(database, Sighting)
    assert (s.face_track_id, s.body_track_id) == (F, F - 1) and np.allclose(s.face_embedding, A)
    assert s.body_embedding_model == worker.NO_BODY          # the fake body model found nothing usable


@pytest.mark.anyio
async def test_a_face_failure_doesnt_stop_polling(monkeypatch):
    async def broken(sessions):
        raise RuntimeError("box busy")
    monkeypatch.setattr(worker, "process_pending", broken)
    await alarm_worker._fingerprint_faces(None)
    assert worker.state["last_error"] == "RuntimeError: box busy"


# ---------- the estimate in the summary ----------

def test_the_summary_counts_different_people_by_face(client, database, fake_box):
    async def seed():
        BoxHistory(fake_box)
        box_id, cameras = await setup_box(database)
        times = ["09:00", "10:00", "11:00", "12:00", "13:00"]
        await save(database, box_id, *[record("face_capture", 1001 + 10 * i, at(MONDAY, t)) for i, t in enumerate(times)],
                   record("body_capture", 2000, at(MONDAY, "14:00")))
        vectors = {1001: A, 1011: A_ISH, 1021: B}         # 1031: no usable face, 1041: not fingerprinted yet
        async with database() as s:
            async with s.begin():
                for track, vector in vectors.items():
                    await s.exec(update(Sighting).where(col(Sighting.face_track_id) == track)
                                 .values(face_embedding=vector, embedding_model="sface-2021dec"))
                await s.exec(update(Sighting).where(col(Sighting.face_track_id) == 1031)
                             .values(embedding_model=worker.NO_FACE))
        return cameras
    cameras = asyncio.run(seed())
    body = client.get("/api/counting/summary", params=DAY).json()
    assert body["totals"]["walk_pasts"] == 6 and body["totals"]["unique_people"] == 6
    assert body["totals"]["face_estimate"] == {"people": 2, "low": 2, "high": 2, "fingerprinted": 3,
                                               "unusable": 1, "pending": 2, "too_many": False}
    d3 = next(c for c in body["by_camera"] if c["camera_id"] == cameras[2])
    assert d3["face_estimate"]["people"] == 2
    assert body["face_matching"]["available"] is models_present()
    # Only the hours with A and B: still 2 people; only 09:00-10:00 (A twice): 1 person.
    assert client.get("/api/counting/summary", params={**DAY, "hours": "9-10"}).json()["totals"]["face_estimate"]["people"] == 1


def test_a_person_is_new_once_and_not_counted_again_when_they_come_back(client, database, fake_box):
    # 09:00 A arrives (new), 10:00 B arrives (new), 11:00 A comes back (not new), 12:00 no clear face.
    async def seed():
        BoxHistory(fake_box)
        box_id, _ = await setup_box(database)
        await save(database, box_id, *[record("face_capture", 3001 + 10 * i, at(MONDAY, t))
                                       for i, t in enumerate(["09:00", "10:00", "11:00", "12:00"])])
        async with database() as s:
            async with s.begin():
                for track, vector in {3001: A, 3011: B, 3021: A_ISH}.items():
                    await s.exec(update(Sighting).where(col(Sighting.face_track_id) == track)
                                 .values(face_embedding=vector, embedding_model="sface-2021dec"))
                await s.exec(update(Sighting).where(col(Sighting.face_track_id) == 3031)
                             .values(embedding_model=worker.NO_FACE))
    asyncio.run(seed())

    points = client.get("/api/counting/series", params={**DAY, "granularity": "hour", "hours": "9-12"}).json()["points"]
    assert [(p["start"][11:16], p["walk_pasts"], p["new_people"]) for p in points] == [
        ("09:00", 1, 1), ("10:00", 1, 1), ("11:00", 1, 0), ("12:00", 1, 0)]

    items = {i["first_seen_at"][11:16]: i for i in client.get("/api/counting/sightings", params=DAY).json()["items"]}
    assert (items["03:00"]["person_no"], items["03:00"]["new_person"]) == (1, True)        # 09:00 Dhaka = 03:00 UTC
    assert (items["04:00"]["person_no"], items["04:00"]["new_person"]) == (2, True)
    came_back = items["05:00"]
    assert (came_back["person_no"], came_back["new_person"]) == (1, False)
    assert came_back["person_first_seen_at"].startswith("2026-09-28T03:00:00")
    assert items["06:00"]["person_no"] is None and items["06:00"]["new_person"] is None   # no clear face

    # A period starting after A's first visit: A's 11:00 walk-past is new in that period.
    later = client.get("/api/counting/series", params={"start": f"{MONDAY} 10:30:00", "end": f"{MONDAY} 23:00:00",
                                                       "granularity": "hour", "hours": "11-11"}).json()["points"]
    assert later[0]["new_people"] == 1
