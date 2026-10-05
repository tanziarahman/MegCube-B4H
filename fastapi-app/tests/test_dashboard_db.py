"""Database-backed dashboard count tests (run with TEST_DATABASE_URL)."""
from datetime import timedelta

import pytest
from sqlmodel import select

from models import CountBucket, DailyStat
from tests.test_counting_builder import F, T, record, save
from tests.test_alarms_db import setup_box


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_dashboard_bucket_columns_are_recounted(database, fake_box):
    box_id, cameras = await setup_box(database)
    await save(
        database, box_id,
        record("matched", F, T, person="p1", score=95),
        record("matched", F + 1, T + timedelta(seconds=1), person="p1", score=60),
        record("stranger", F + 2, T + timedelta(seconds=2), score=50),
        record("face_capture", F, T + timedelta(seconds=3)),
        record("body_capture", F - 1, T + timedelta(seconds=4)),
    )
    async with database() as session:
        bucket = (await session.exec(select(CountBucket))).one()
    assert bucket.camera_id == cameras[2]
    assert (bucket.matched_events, bucket.stranger_events) == (2, 1)
    assert (bucket.face_capture_events, bucket.body_capture_events) == (1, 1)
    assert bucket.low_confidence_events == 2
    assert bucket.identity_score_sum == 205
    assert bucket.identity_score_count == 3


@pytest.mark.anyio
async def test_dashboard_daily_stats_use_distinct_track_keys(database, fake_box):
    box_id, _ = await setup_box(database)
    await save(
        database, box_id,
        record("matched", F, T, person="p1"),
        record("face_capture", F, T + timedelta(seconds=1)),
        record("stranger", F + 2, T + timedelta(seconds=2)),
        record("face_capture", F + 3, T + timedelta(seconds=3)),
    )
    async with database() as session:
        daily = (await session.exec(select(DailyStat))).one()
    assert (daily.tracked_encounters, daily.face_encounters) == (2, 2)
    assert (daily.recognized_encounters, daily.stranger_encounters) == (1, 1)
    assert daily.recognized_capture_tracks == 1
    assert daily.unique_recognized_people == 1
