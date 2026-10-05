"""Puts new events into sightings and recounts the 15-minute buckets they touch.

A sighting is one person passing one camera once. The box never puts a face and a body in the same
record, but it numbers them from one counter: face track F and body track F-1 on the same camera
are the same person (verified on real data, docs: People Counting Build Plan section 04). Records
arrive in any order and across polls, so a face and its body may first become two sightings and be
merged when the second half shows up.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import or_, text, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from alarms.rules import plain
from dashboard_data.stats import LOW_CONFIDENCE, LOW_LIVENESS, rebuild_days
from models import Event, EventKind, Incident, PersonSource, RecognitionResult, Sighting

from .settings import BUCKET, PAIR_MAX, box_tz

log = logging.getLogger("b4h.counting")

# A track already in a sighting filed under the previous local day (it started before midnight)
# is only reused if its last record is this recent, so ids reused after a box reboot don't join.
TRACK_CONTINUES = timedelta(hours=1)


def bucket_start(at: datetime) -> datetime:
    """Floor to 15 minutes. Done in UTC: every real time zone offset is a multiple of 15 minutes,
    so UTC and local 15-minute boundaries line up."""
    return at.replace(minute=at.minute - at.minute % 15, second=0, microsecond=0)


def person_key(s: Sighting) -> tuple[str, str]:
    """(person_source, person_key) for a sighting; see models.enums.PersonSource for the formats."""
    if plain(s.recognition_result) == RecognitionResult.MATCHED.value and s.person_uuid:
        return PersonSource.RECOGNIZED.value, f"p:{s.person_uuid}"
    if s.stranger_profile_id is not None:
        return PersonSource.STRANGER.value, f"s:{s.stranger_profile_id}"
    track = f"b{s.body_track_id}" if s.body_track_id is not None else f"f{s.face_track_id}"
    return PersonSource.UNIDENTIFIED.value, f"t:{s.camera_id}:{s.local_date.isoformat()}:{track}"


def _set_local(s: Sighting, tz) -> None:
    local = s.first_seen_at.astimezone(tz)
    s.local_date, s.local_hour, s.iso_dow = local.date(), local.hour, local.isoweekday()


def _refresh_identity(s: Sighting) -> None:
    s.person_source, s.person_key = person_key(s)


def _better_match(score: float | None, than: float | None) -> bool:
    return (score if score is not None else -1) > (than if than is not None else -1)


@dataclass
class _Batch:
    """Sightings loaded or created while handling one batch, by (camera, local date, 'f'|'b', track),
    so a second record of the same track neither re-queries nor inserts twice."""
    session: AsyncSession
    tz: object
    index: dict[tuple, Sighting] = field(default_factory=dict)
    looked_up: set[tuple] = field(default_factory=set)
    touched: set[tuple[int, datetime]] = field(default_factory=set)

    @staticmethod
    def keys(s: Sighting) -> list[tuple]:
        out = []
        if s.face_track_id is not None:
            out.append((s.camera_id, s.local_date, "f", s.face_track_id))
        if s.body_track_id is not None:
            out.append((s.camera_id, s.local_date, "b", s.body_track_id))
        return out

    def add(self, s: Sighting) -> None:
        for key in self.keys(s):
            self.index[key] = s

    def remove(self, s: Sighting) -> None:
        for key in self.keys(s):
            if self.index.get(key) is s:
                del self.index[key]

    async def find(self, camera_id: int, days: list[date], wanted: list[tuple[str, int]]) -> None:
        """Load the sightings holding any of these tracks on these days (unless already looked up)."""
        keys = [(camera_id, d, kind, track) for d in days for kind, track in wanted]
        missing = [k for k in keys if k not in self.looked_up and k not in self.index]
        if not missing:
            return
        faces = {t for kind, t in wanted if kind == "f"}
        bodies = {t for kind, t in wanted if kind == "b"}
        rows = (await self.session.exec(select(Sighting).where(
            Sighting.camera_id == camera_id, col(Sighting.local_date).in_(days),
            or_(col(Sighting.face_track_id).in_(faces or [-1]), col(Sighting.body_track_id).in_(bodies or [-1])),
        ))).all()
        for s in rows:
            self.add(s)
        self.looked_up.update(keys)

    def get(self, camera_id: int, days: list[date], kind: str, track: int | None) -> Sighting | None:
        if track is None:
            return None
        for d in days:
            if (s := self.index.get((camera_id, d, kind, track))) is not None:
                return s
        return None

    def touch(self, camera_id: int, at: datetime) -> None:
        self.touched.add((camera_id, bucket_start(at)))


async def attach(session: AsyncSession, events: list[Event], box_id: int) -> None:
    """Put each new event into its sighting (creating or merging sightings), set
    events.sighting_id, then rebuild the 15-minute buckets those sightings touch and the dashboard's
    day totals (daily_stats)."""
    if not events:
        return
    batch = _Batch(session, box_tz())
    for e in sorted(events, key=lambda e: (e.occurred_at, e.id or 0)):
        if e.camera_id is None:
            log.warning("Event %s has no camera; not counted", e.id)
            continue
        batch.touch(e.camera_id, e.occurred_at)          # the bucket's raw record count
        if e.face_track_id is None and e.body_track_id is None:
            continue
        await _attach_one(batch, e, box_id)
    await session.flush()
    await rebuild_buckets(session, batch.touched, batch.tz)
    await rebuild_days(session, box_id, {e.occurred_at.astimezone(batch.tz).date() for e in events})


async def _attach_one(batch: _Batch, e: Event, box_id: int) -> None:
    session, tz = batch.session, batch.tz
    d = e.occurred_at.astimezone(tz).date()
    days = [d, d - timedelta(days=1)]          # a face at 23:59:59 and its body at 00:00:01
    face, body = e.face_track_id, e.body_track_id
    partner_body = face - 1 if face is not None else None
    partner_face = body + 1 if body is not None else None

    wanted = [(k, t) for k, t in (("f", face), ("b", body), ("b", partner_body), ("f", partner_face))
              if t is not None]
    await batch.find(e.camera_id, days, wanted)

    own = batch.get(e.camera_id, days, "f", face) or batch.get(e.camera_id, days, "b", body)
    if own is not None and own.local_date != d and e.occurred_at - own.last_seen_at > TRACK_CONTINUES:
        own = None
    partner = batch.get(e.camera_id, days, "b", partner_body) or batch.get(e.camera_id, days, "f", partner_face)
    if partner is not None and partner is not own:
        # Compare the two halves' first records: this record may be a late one of a long track,
        # or an earlier one that arrived late (which can bring two halves within reach: merge).
        first = min(own.first_seen_at, e.occurred_at) if own is not None else e.occurred_at
        if abs(partner.first_seen_at - first) > PAIR_MAX:
            partner = None

    if own is not None and partner is not None and own is not partner:
        s = await _merge(batch, own, partner)
    else:
        s = own or partner
    if s is None:
        s = Sighting(box_id=box_id, camera_id=e.camera_id, face_track_id=face, body_track_id=body,
                     first_seen_at=e.occurred_at, last_seen_at=e.occurred_at, event_count=0, person_key="")
        _set_local(s, tz)
    else:
        batch.remove(s)
        batch.touch(s.camera_id, s.first_seen_at)      # first_seen_at may move to an earlier bucket
        s.face_track_id = s.face_track_id if face is None else face
        s.body_track_id = s.body_track_id if body is None else body
        s.first_seen_at = min(s.first_seen_at, e.occurred_at)
        s.last_seen_at = max(s.last_seen_at, e.occurred_at)
        _set_local(s, tz)

    s.event_count += 1
    s.best_face_image_path = s.best_face_image_path or e.face_image_path
    s.best_body_image_path = s.best_body_image_path or e.body_image_path
    kind = plain(e.kind)
    if kind == EventKind.MATCHED.value:
        if plain(s.recognition_result) != RecognitionResult.MATCHED.value or _better_match(e.match_score,
                                                                                         s.best_match_score):
            s.person_uuid, s.person_name, s.best_match_score = e.person_uuid, e.person_name, e.match_score
        s.recognition_result = RecognitionResult.MATCHED.value
    elif kind == EventKind.STRANGER.value and s.recognition_result is None:
        s.recognition_result = RecognitionResult.STRANGER.value
    _refresh_identity(s)

    session.add(s)
    await session.flush()                              # new sightings get their id
    batch.add(s)
    batch.touch(s.camera_id, s.first_seen_at)
    e.sighting_id = s.id
    session.add(e)


async def _merge(batch: _Batch, a: Sighting, b: Sighting) -> Sighting:
    """Both halves of one person exist as separate sightings: keep the older row, move the other's
    tracks, times, counts and identity onto it, re-point its events, and delete it."""
    session = batch.session
    kept, gone = (a, b) if a.id < b.id else (b, a)
    batch.remove(kept)
    batch.remove(gone)
    batch.touch(kept.camera_id, kept.first_seen_at)
    batch.touch(gone.camera_id, gone.first_seen_at)

    tracks = (gone.face_track_id, gone.body_track_id)
    kept.first_seen_at = min(kept.first_seen_at, gone.first_seen_at)
    kept.last_seen_at = max(kept.last_seen_at, gone.last_seen_at)
    kept.event_count += gone.event_count
    kept.best_face_image_path = kept.best_face_image_path or gone.best_face_image_path
    kept.best_body_image_path = kept.best_body_image_path or gone.best_body_image_path
    gone_matched = plain(gone.recognition_result) == RecognitionResult.MATCHED.value
    kept_matched = plain(kept.recognition_result) == RecognitionResult.MATCHED.value
    if gone_matched and (not kept_matched or _better_match(gone.best_match_score, kept.best_match_score)):
        kept.person_uuid, kept.person_name = gone.person_uuid, gone.person_name
        kept.best_match_score = gone.best_match_score
        kept.recognition_result = RecognitionResult.MATCHED.value
    elif kept.recognition_result is None:
        kept.recognition_result = gone.recognition_result
    kept.stranger_profile_id = kept.stranger_profile_id or gone.stranger_profile_id
    if kept.face_embedding is None and gone.face_embedding is not None:
        kept.face_embedding, kept.embedding_model = gone.face_embedding, gone.embedding_model
    if kept.body_embedding is None and gone.body_embedding is not None:
        kept.body_embedding, kept.body_embedding_model = gone.body_embedding, gone.body_embedding_model

    await session.exec(update(Event).where(col(Event.sighting_id) == gone.id).values(sighting_id=kept.id))
    await session.exec(update(Incident).where(col(Incident.sighting_id) == gone.id).values(sighting_id=kept.id))
    # Delete before copying the track ids over, or the partial unique indexes on the tracks fire.
    await session.delete(gone)
    await session.flush()
    kept.face_track_id = kept.face_track_id if kept.face_track_id is not None else tracks[0]
    kept.body_track_id = kept.body_track_id if kept.body_track_id is not None else tracks[1]
    _set_local(kept, batch.tz)
    _refresh_identity(kept)
    session.add(kept)
    await session.flush()
    batch.add(kept)
    return kept


# ---------- 15-minute buckets ----------

_REBUILD = text("""
WITH s AS (
    SELECT count(*) AS n, count(face_track_id) AS f, count(body_track_id) AS b
    FROM sightings WHERE camera_id = :camera_id AND first_seen_at >= :start AND first_seen_at < :end
), e AS (
    SELECT count(*) AS n,
           count(*) FILTER (WHERE kind = 'matched') AS matched,
           count(*) FILTER (WHERE kind = 'stranger') AS stranger,
           count(*) FILTER (WHERE kind = 'face_capture') AS face_capture,
           count(*) FILTER (WHERE kind = 'body_capture') AS body_capture,
           count(*) FILTER (WHERE kind IN ('matched', 'stranger') AND match_score < :low_confidence) AS low_conf,
           count(*) FILTER (WHERE kind IN ('matched', 'stranger') AND liveness_score < :low_liveness) AS low_live,
           coalesce(sum(match_score) FILTER (WHERE kind IN ('matched', 'stranger')), 0) AS score_sum,
           count(match_score) FILTER (WHERE kind IN ('matched', 'stranger')) AS score_n
    FROM events WHERE camera_id = :camera_id AND occurred_at >= :start AND occurred_at < :end
)
INSERT INTO count_buckets (camera_id, bucket_start, local_date, local_hour, local_minute, iso_dow,
                           sightings, face_sightings, body_sightings, events,
                           matched_events, stranger_events, face_capture_events, body_capture_events,
                           low_confidence_events, low_liveness_events, identity_score_sum,
                           identity_score_count, updated_at)
SELECT :camera_id, :start, :local_date, :local_hour, :local_minute, :iso_dow, s.n, s.f, s.b, e.n,
       e.matched, e.stranger, e.face_capture, e.body_capture, e.low_conf, e.low_live, e.score_sum, e.score_n,
       now()
FROM s, e
ON CONFLICT (camera_id, bucket_start) DO UPDATE SET
    sightings = excluded.sightings, face_sightings = excluded.face_sightings,
    body_sightings = excluded.body_sightings, events = excluded.events,
    matched_events = excluded.matched_events, stranger_events = excluded.stranger_events,
    face_capture_events = excluded.face_capture_events, body_capture_events = excluded.body_capture_events,
    low_confidence_events = excluded.low_confidence_events, low_liveness_events = excluded.low_liveness_events,
    identity_score_sum = excluded.identity_score_sum, identity_score_count = excluded.identity_score_count,
    updated_at = excluded.updated_at
""")
# A bucket left with nothing in it (its only sighting merged into an earlier one, no records) goes.
_DROP_EMPTY = text("DELETE FROM count_buckets WHERE camera_id = :camera_id AND bucket_start = :start "
                   "AND sightings = 0 AND events = 0")


async def rebuild_buckets(session: AsyncSession, touched: set[tuple[int, datetime]], tz=None) -> None:
    """Recount these (camera_id, bucket_start) buckets from `sightings` and `events`. Recounting
    instead of adding/subtracting means merges and late records can never make the totals drift."""
    tz = tz or box_tz()
    for camera_id, start in sorted(touched):
        local = start.astimezone(tz)
        params = {"camera_id": camera_id, "start": start, "end": start + BUCKET, "local_date": local.date(),
                  "local_hour": local.hour, "local_minute": local.minute, "iso_dow": local.isoweekday(),
                  "low_confidence": LOW_CONFIDENCE, "low_liveness": LOW_LIVENESS}
        await session.exec(_REBUILD, params=params)
        await session.exec(_DROP_EMPTY, params={"camera_id": camera_id, "start": start})
