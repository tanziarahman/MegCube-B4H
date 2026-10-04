"""Counting queries for the People counting page. Totals come from `sightings` (unique people can't
be added across buckets); charts come from the 15-minute `count_buckets`.

Every query takes a Filters: cameras, a [start, end) time range, an optional hours-of-day window
(may wrap past midnight) and optional ISO weekdays. Each camera's count_basis decides which of its
sightings count: merged = all, face = those with a face track, body = those with a body track.
"""
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, case, false, func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from alarms.rules import plain
from faces import grouping
from faces.embedder import models_present
from faces.worker import ENABLED as FACE_MATCHING_ON
from models import Camera, CountBasis, CountBucket, Event, EventKind, PersonSource, RecognitionResult, Sighting

from .builder import bucket_start
from .settings import BUCKET, VISIT_GAP_SECONDS, box_tz

IDENTITY_LOOKBACK = timedelta(days=7)


@dataclass(frozen=True)
class Filters:
    cameras: dict[int, str]               # camera id -> count_basis
    start: datetime                       # UTC, inclusive
    end: datetime                         # UTC, exclusive
    hours: tuple[int, int] | None = None  # inclusive local hours; (22, 5) runs past midnight
    days: tuple[int, ...] | None = None   # ISO weekdays, 1 = Monday

    def ids(self, basis: CountBasis | None = None) -> list[int]:
        return [c for c, b in self.cameras.items() if basis is None or plain(b) == basis.value]


def _hour_filter(column, hours):
    start, end = hours
    if start <= end:
        return column.between(start, end)
    return or_(column >= start, column <= end)


def _common(f: Filters, table) -> list:
    """Camera, hour-of-day and weekday conditions; `table` is Sighting or CountBucket."""
    conditions = [col(table.camera_id).in_(f.ids() or [-1])]
    if f.hours is not None:
        conditions.append(_hour_filter(col(table.local_hour), f.hours))
    if f.days:
        conditions.append(col(table.iso_dow).in_(f.days))
    return conditions


def sighting_filter(f: Filters) -> list:
    """WHERE conditions on `sightings` for these filters, including each camera's count_basis."""
    basis = []
    if merged := f.ids(CountBasis.MERGED):
        basis.append(col(Sighting.camera_id).in_(merged))
    if face := f.ids(CountBasis.FACE):
        basis.append(and_(col(Sighting.camera_id).in_(face), col(Sighting.face_track_id).is_not(None)))
    if body := f.ids(CountBasis.BODY):
        basis.append(and_(col(Sighting.camera_id).in_(body), col(Sighting.body_track_id).is_not(None)))
    return [*_common(f, Sighting), Sighting.first_seen_at >= f.start, Sighting.first_seen_at < f.end,
            or_(*basis) if basis else false()]


def _bucket_count(f: Filters):
    """sum() of the bucket column that matches each camera's count_basis."""
    whens = []
    if face := f.ids(CountBasis.FACE):
        whens.append((col(CountBucket.camera_id).in_(face), CountBucket.face_sightings))
    if body := f.ids(CountBasis.BODY):
        whens.append((col(CountBucket.camera_id).in_(body), CountBucket.body_sightings))
    column = case(*whens, else_=CountBucket.sightings) if whens else CountBucket.sightings
    return func.coalesce(func.sum(column), 0)


def bucket_filter(f: Filters) -> list:
    # Buckets are 15 minutes: one that starts before `start` but still holds part of the range counts.
    return [*_common(f, CountBucket), CountBucket.bucket_start >= bucket_start(f.start),
            CountBucket.bucket_start < f.end]


# ---------- summary ----------

def _totals_columns():
    paired = and_(col(Sighting.face_track_id).is_not(None), col(Sighting.body_track_id).is_not(None))
    return [
        func.count().label("walk_pasts"),
        func.count(func.distinct(Sighting.person_key)).label("unique_people"),
        func.count(func.distinct(Sighting.person_key))
            .filter(Sighting.person_source == PersonSource.RECOGNIZED.value).label("known_people"),
        func.count().filter(Sighting.recognition_result == RecognitionResult.STRANGER.value)
            .label("stranger_walk_pasts"),
        func.count().filter(col(Sighting.recognition_result).is_(None)).label("not_compared_walk_pasts"),
        func.count().filter(paired).label("paired"),
        func.count().filter(col(Sighting.body_track_id).is_(None)).label("face_only"),
        func.count().filter(col(Sighting.face_track_id).is_(None)).label("body_only"),
    ]


_TOTAL_KEYS = ("walk_pasts", "unique_people", "known_people", "stranger_walk_pasts", "not_compared_walk_pasts",
               "paired", "face_only", "body_only")


async def _visits(session: AsyncSession, f: Filters) -> dict[int, int]:
    """Visits per camera: sightings of the same person_key on the same camera within the visit gap
    are one visit. Unidentified keys are unique per sighting, so each is one visit."""
    prev_end = func.lag(Sighting.last_seen_at).over(
        partition_by=(Sighting.camera_id, Sighting.person_key), order_by=Sighting.first_seen_at)
    inner = select(Sighting.camera_id, Sighting.first_seen_at, prev_end.label("prev_end")) \
        .where(*sighting_filter(f)).subquery()
    gap = timedelta(seconds=VISIT_GAP_SECONDS)
    rows = (await session.exec(
        select(inner.c.camera_id, func.count())
        .where(or_(inner.c.prev_end.is_(None), inner.c.first_seen_at - inner.c.prev_end > gap))
        .group_by(inner.c.camera_id)
    )).all()
    return dict(rows)


_PEOPLE_COLUMNS = (Sighting.id, Sighting.camera_id, Sighting.local_date, Sighting.first_seen_at, Sighting.last_seen_at,
                   Sighting.person_source, Sighting.person_key, Sighting.face_embedding, Sighting.embedding_model,
                   Sighting.best_face_image_path, Sighting.body_embedding, Sighting.body_embedding_model,
                   Sighting.best_body_image_path)


async def _people_rows(session: AsyncSession, f: Filters) -> list:
    return list((await session.exec(select(*_PEOPLE_COLUMNS).where(*sighting_filter(f))
                                    .order_by(Sighting.first_seen_at, Sighting.id))).all())


def _kind(r) -> str:
    """known: recognised by the box; matchable: has a face or body fingerprint; pending: pictures not
    processed yet; unusable: nothing to compare (no clear face, no body picture, or pictures gone)."""
    if r.person_source == PersonSource.RECOGNIZED.value:
        return "known"
    if r.face_embedding is not None or r.body_embedding is not None:
        return "matchable"
    if (r.best_face_image_path and r.embedding_model is None) or (r.best_body_image_path and r.body_embedding_model is None):
        return "pending"
    return "unusable"


def _walk(r) -> grouping.WalkPast:
    return grouping.WalkPast(face=r.face_embedding, body=r.body_embedding, day=r.local_date, camera_id=r.camera_id,
                             first_seen_at=r.first_seen_at, last_seen_at=r.last_seen_at)


def _people_estimate(rows: list) -> dict:
    """Different people among these walk-pasts (time order): recognised people by their library id,
    everyone else by grouping body + face fingerprints. Walk-pasts with nothing to compare aren't in it."""
    known, walks, unusable, pending = set(), [], 0, 0
    for r in rows:
        kind = _kind(r)
        if kind == "known":
            known.add(r.person_key)
        elif kind == "matchable":
            walks.append(_walk(r))
        elif kind == "pending":
            pending += 1
        else:
            unusable += 1
    counted = grouping.count_people(walks)
    out = {"fingerprinted": len(walks) + sum(1 for r in rows if _kind(r) == "known"), "unusable": unusable,
           "pending": pending, "too_many": counted is None, "people": None, "low": None, "high": None}
    if counted is not None:
        out.update({k: v + len(known) for k, v in counted.items()})
    return out


async def _face_estimates(session: AsyncSession, f: Filters) -> dict:
    """{None: whole selection, camera_id: that camera} -> people estimate."""
    rows = await _people_rows(session, f)
    scopes: dict = {None: rows}
    for r in rows:
        scopes.setdefault(r.camera_id, []).append(r)

    def estimate_all() -> dict:
        return {scope: _people_estimate(scope_rows) for scope, scope_rows in scopes.items()}
    return await asyncio.to_thread(estimate_all)       # grouping is CPU work: keep the server responsive


@dataclass(frozen=True)
class PersonVisit:
    """Who a walk-past was, within the chosen period: the n-th different person seen."""
    person_no: int
    new: bool                     # their first walk-past in the period: counted as a new person
    first_seen_at: datetime       # when this person first walked past in the period


async def people_in_period(session: AsyncSession, f: Filters) -> dict[int, PersonVisit] | None:
    """sighting id -> PersonVisit, for the walk-pasts whose person can be told apart (recognised, or a
    face/body fingerprint). A person is new on their first walk-past in the period and not counted
    again when they come back. None when the period has too many walk-pasts to group."""
    rows = await _people_rows(session, f)
    matchable = [r for r in rows if _kind(r) == "matchable"]
    groups = await asyncio.to_thread(grouping.labels, [_walk(r) for r in matchable])
    if groups is None:
        return None
    group_of = {r.id: label for r, label in zip(matchable, groups)}

    out: dict[int, PersonVisit] = {}
    first: dict[str, tuple[int, datetime]] = {}
    for r in rows:
        if _kind(r) == "known":
            person = r.person_key
        elif r.id in group_of:
            person = f"group:{group_of[r.id]}"
        else:
            continue                  # nothing to compare: can't tell who it was
        new = person not in first
        if new:
            first[person] = (len(first) + 1, r.first_seen_at)
        number, first_at = first[person]
        out[r.id] = PersonVisit(person_no=number, new=new, first_seen_at=first_at)
    return out


def face_matching_status() -> dict:
    if not FACE_MATCHING_ON:
        return {"available": False, "reason": "Face matching is turned off (FACE_MATCHING=0)"}
    if not models_present():
        return {"available": False, "reason": "The matching models aren't installed (uv run python -m faces.download)"}
    return {"available": True, "reason": None}


async def summary(session: AsyncSession, f: Filters, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    where = sighting_filter(f)
    row = (await session.exec(select(*_totals_columns()).where(*where))).one()
    totals = dict(zip(_TOTAL_KEYS, row))
    visits = await _visits(session, f)
    totals["visits"] = sum(visits.values())
    faces = await _face_estimates(session, f)
    empty_estimate = _people_estimate([])
    totals["face_estimate"] = faces[None]

    per_camera = {cid: dict(zip(_TOTAL_KEYS, rest)) for cid, *rest in (await session.exec(
        select(Sighting.camera_id, *_totals_columns()).where(*where).group_by(Sighting.camera_id))).all()}
    cameras = (await session.exec(select(Camera).where(col(Camera.id).in_(f.ids() or [-1]))
                                  .order_by(Camera.device_id))).all()
    by_camera = []
    for c in cameras:
        numbers = per_camera.get(c.id, dict.fromkeys(_TOTAL_KEYS, 0))
        by_camera.append({"camera_id": c.id, "name": c.name, "count_basis": plain(c.count_basis), **numbers,
                          "visits": visits.get(c.id, 0), "face_estimate": faces.get(c.id, empty_estimate)})

    identity = (await session.exec(select(Event.id).where(
        col(Event.camera_id).in_(f.ids() or [-1]),
        col(Event.kind).in_([EventKind.MATCHED.value, EventKind.STRANGER.value]),
        Event.occurred_at >= now - IDENTITY_LOOKBACK).limit(1))).first()
    last = (await session.exec(select(func.max(Sighting.last_seen_at)).where(
        col(Sighting.camera_id).in_(f.ids() or [-1])))).one()
    return {"totals": totals, "by_camera": by_camera, "identity_available": identity is not None,
            "face_matching": face_matching_status(), "last_sighting_at": last}


# ---------- time series ----------

def _slots(f: Filters, granularity: str) -> list[datetime]:
    """Every slot start (UTC) in the range that passes the hour/weekday filters, so charts have no gaps."""
    tz = box_tz()
    out = []
    if granularity == "day":
        day, last = f.start.astimezone(tz).date(), (f.end - timedelta(microseconds=1)).astimezone(tz).date()
        while day <= last:
            if not f.days or day.isoweekday() in f.days:
                out.append(datetime.combine(day, datetime.min.time(), tz).astimezone(timezone.utc))
            day += timedelta(days=1)
        return out
    step = BUCKET if granularity == "15m" else timedelta(hours=1)
    at = bucket_start(f.start)
    if granularity == "hour":
        local = at.astimezone(tz)
        at = (local - timedelta(minutes=local.minute)).astimezone(timezone.utc)
    while at < f.end:
        local = at.astimezone(tz)
        if (f.hours is None or _in_hours(local.hour, f.hours)) and (not f.days or local.isoweekday() in f.days):
            out.append(at)
        at += step
    return out


def _slot_of(at: datetime, granularity: str) -> datetime:
    """The start (UTC) of the chart slot this moment falls in."""
    if granularity == "15m":
        return bucket_start(at)
    local = at.astimezone(box_tz())
    if granularity == "hour":
        local = local.replace(minute=0, second=0, microsecond=0)
    else:
        local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


def _in_hours(hour: int, hours: tuple[int, int]) -> bool:
    start, end = hours
    return start <= hour <= end if start <= end else hour >= start or hour <= end


async def series(session: AsyncSession, f: Filters, granularity: str) -> list[dict]:
    """Walk-pasts per 15 minutes, hour or local day, zero-filled. `face` / `body` are the sightings
    with a face / body track (whatever the camera's count_basis). `new_people`: people seen for the
    first time in the period, in the slot of their first walk-past (None: too many to group)."""
    tz = box_tz()
    counts = [_bucket_count(f).label("walk_pasts"),
              func.coalesce(func.sum(CountBucket.face_sightings), 0).label("face"),
              func.coalesce(func.sum(CountBucket.body_sightings), 0).label("body")]
    if granularity == "15m":
        keys = (CountBucket.bucket_start,)
    elif granularity == "hour":
        keys = (CountBucket.local_date, CountBucket.local_hour)
    else:
        keys = (CountBucket.local_date,)
    rows = (await session.exec(select(*keys, *counts).where(*bucket_filter(f)).group_by(*keys))).all()

    def slot_of(row) -> datetime:
        if granularity == "15m":
            return row[0]
        hour = row[1] if granularity == "hour" else 0
        return datetime.combine(row[0], datetime.min.time(), tz).replace(hour=hour).astimezone(timezone.utc)

    found = {slot_of(r): (int(r[-3]), int(r[-2]), int(r[-1])) for r in rows}
    people = await people_in_period(session, f)
    new_people: dict[datetime, int] = {}
    for visit in (people or {}).values():
        if visit.new:
            slot = _slot_of(visit.first_seen_at, granularity)
            new_people[slot] = new_people.get(slot, 0) + 1
    return [{"start": slot.astimezone(tz), "walk_pasts": found.get(slot, (0, 0, 0))[0],
             "face": found.get(slot, (0, 0, 0))[1], "body": found.get(slot, (0, 0, 0))[2],
             "new_people": None if people is None else new_people.get(slot, 0)}
            for slot in _slots(f, granularity)]


# ---------- busy times ----------

def weekdays_in_range(f: Filters) -> dict[int, int]:
    """How many of each ISO weekday the range covers (local days, partial days included)."""
    tz = box_tz()
    out = dict.fromkeys(range(1, 8), 0)
    day: date = f.start.astimezone(tz).date()
    last: date = (f.end - timedelta(microseconds=1)).astimezone(tz).date()
    while day <= last:
        out[day.isoweekday()] += 1
        day += timedelta(days=1)
    if f.days:
        out = {d: (n if d in f.days else 0) for d, n in out.items()}
    return out


async def heatmap(session: AsyncSession, f: Filters) -> dict:
    """Average walk-pasts per weekday x hour: a range with three Mondays doesn't look three times busier."""
    days = weekdays_in_range(f)
    rows = (await session.exec(
        select(CountBucket.iso_dow, CountBucket.local_hour, _bucket_count(f))
        .where(*bucket_filter(f)).group_by(CountBucket.iso_dow, CountBucket.local_hour)
    )).all()
    cells = [{"iso_dow": dow, "hour": hour, "walk_pasts": int(total),
              "avg_walk_pasts": round(int(total) / days[dow], 2) if days[dow] else 0.0}
             for dow, hour, total in sorted(rows) if total]
    return {"cells": cells, "days_in_range": {str(d): n for d, n in days.items()}}


# ---------- the sightings behind the numbers ----------

async def sightings(session: AsyncSession, f: Filters, page: int, size: int) -> dict:
    where = sighting_filter(f)
    total = (await session.exec(select(func.count()).select_from(Sighting).where(*where))).one()
    rows = (await session.exec(
        select(Sighting, Camera.name).join(Camera, col(Camera.id) == Sighting.camera_id).where(*where)
        .order_by(col(Sighting.first_seen_at).desc(), col(Sighting.id).desc())
        .offset((page - 1) * size).limit(size)
    )).all()
    people = await people_in_period(session, f) or {}
    items = [{
        "id": s.id, "camera_id": s.camera_id, "camera_name": name, "first_seen_at": s.first_seen_at,
        "last_seen_at": s.last_seen_at, "duration_seconds": round((s.last_seen_at - s.first_seen_at).total_seconds(), 1),
        "face_track_id": s.face_track_id, "body_track_id": s.body_track_id,
        "person_source": plain(s.person_source), "person_name": s.person_name,
        "recognition_result": plain(s.recognition_result), "event_count": s.event_count,
        "face_image_path": s.best_face_image_path, "body_image_path": s.best_body_image_path,
        # Who it was within the period (null: no usable face, or too many to group).
        "person_no": people[s.id].person_no if s.id in people else None,
        "new_person": people[s.id].new if s.id in people else None,
        "person_first_seen_at": people[s.id].first_seen_at if s.id in people else None,
    } for s, name in rows]
    return {"total": total, "page": page, "size": size, "items": items}
