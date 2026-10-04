"""People counting: groups new events into sightings (one person passing one camera once) and keeps
the 15-minute totals in `count_buckets` up to date. Queries for the counting page are in queries.py.

Runs inside the alarm ingest transaction (alarms/ingest.py), so only genuinely new events are counted
and a crash rolls back events and sightings together.
"""
from .builder import attach

__all__ = ["attach"]
