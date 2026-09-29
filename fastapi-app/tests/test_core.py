"""core.py helpers: time zone handling."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import core


@pytest.mark.parametrize("server_tz", ["UTC", "Asia/Dhaka", "America/New_York"])
def test_times_mean_box_time_whatever_the_server_time_zone(monkeypatch, server_tz):
    """A server/Docker container set to UTC must not shift every date filter by 6 hours."""
    import os
    import time
    monkeypatch.setenv("TZ", server_tz)
    if hasattr(time, "tzset"):
        time.tzset()
    monkeypatch.setattr(core, "BOX_TZ", ZoneInfo("Asia/Dhaka"))
    expected = int(datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc).timestamp() * 1000) - 6 * 3600 * 1000
    assert core.to_ms("2026-09-28 00:00:00") == expected
    monkeypatch.delenv("TZ")
    if hasattr(time, "tzset"):
        time.tzset()


def test_other_box_time_zone(monkeypatch):
    monkeypatch.setattr(core, "BOX_TZ", ZoneInfo("Asia/Kolkata"))   # UTC+5:30
    expected = int(datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc).timestamp() * 1000) - int(5.5 * 3600 * 1000)
    assert core.to_ms("2026-09-28 00:00:00") == expected


def test_missing_time_zone_data_falls_back_to_pc_time(monkeypatch):
    monkeypatch.setenv("BOX_TIMEZONE", "Not/AZone")
    assert core._load_timezone() is None
    monkeypatch.setattr(core, "BOX_TZ", None)
    assert core.to_ms("2026-09-28 00:00:00") == int(datetime(2026, 9, 28).timestamp() * 1000)
