"""Does an event match an alarm rule? Pure functions, no database: the engine loads each rule once
per batch into a RuleSpec and checks every new event against it."""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from models import AlarmRule, EventKind, MatchMode, TargetType


def plain(value):
    """Enum member -> its value. A str-Enum hashes by member NAME, so `EventKind.MATCHED in {"matched"}`
    is False; set lookups must use plain strings."""
    return value.value if isinstance(value, Enum) else value


@dataclass(frozen=True)
class Window:
    iso_dow: int          # 1 = Monday: the day the window STARTS on
    start: time
    end: time             # end < start: runs past midnight into the next day

    def contains(self, local: datetime) -> bool:
        t = local.time()
        if self.start < self.end:
            return local.isoweekday() == self.iso_dow and self.start <= t < self.end
        # Overnight, e.g. Mon 22:00 -> Tue 06:00: Monday evening, or Tuesday early morning.
        previous_day = (local - timedelta(days=1)).isoweekday()
        return (local.isoweekday() == self.iso_dow and t >= self.start) or \
               (previous_day == self.iso_dow and t < self.end)


@dataclass
class RuleSpec:
    id: int
    name: str
    severity: str
    event_kinds: frozenset[str]
    match_mode: str
    min_match_score: float | None
    min_liveness: float | None
    tz: ZoneInfo
    cooldown_seconds: int
    dedupe_scope: str
    max_delay_seconds: int
    email_delayed: bool
    attach_snapshot: bool
    camera_ids: frozenset[int]
    windows: list[Window] = field(default_factory=list)
    person_ids: frozenset[str] = frozenset()
    group_ids: frozenset[str] = frozenset()
    group_labels: frozenset[str] = frozenset()     # lower-cased group names, for records without ids
    recipient_ids: list[int] = field(default_factory=list)
    snapshot: dict = field(default_factory=dict)  # copied into each incident

    @classmethod
    def from_rule(cls, rule: AlarmRule, camera_ids, windows, targets, recipient_ids) -> "RuleSpec":
        persons = {t.target_value for t in targets if t.target_type == TargetType.PERSON}
        groups = [t for t in targets if t.target_type == TargetType.GROUP]
        return cls(
            id=rule.id, name=rule.name, severity=plain(rule.severity),
            event_kinds=frozenset(plain(k) for k in rule.event_kinds),
            match_mode=plain(rule.match_mode), min_match_score=rule.min_match_score, min_liveness=rule.min_liveness,
            tz=ZoneInfo(rule.timezone), cooldown_seconds=rule.cooldown_seconds,
            dedupe_scope=plain(rule.dedupe_scope),
            max_delay_seconds=rule.max_delay_seconds, email_delayed=rule.email_delayed,
            attach_snapshot=rule.attach_snapshot, camera_ids=frozenset(camera_ids),
            windows=[Window(w.iso_dow, w.start_time, w.end_time) for w in windows],
            person_ids=frozenset(persons),
            group_ids=frozenset(g.target_value for g in groups),
            group_labels=frozenset((g.label or "").strip().lower() for g in groups if g.label),
            recipient_ids=list(recipient_ids),
            snapshot={
                "id": rule.id, "name": rule.name, "severity": plain(rule.severity),
                "event_kinds": [plain(k) for k in rule.event_kinds],
                "match_mode": plain(rule.match_mode), "min_match_score": rule.min_match_score,
                "min_liveness": rule.min_liveness, "timezone": rule.timezone,
                "cooldown_seconds": rule.cooldown_seconds, "dedupe_scope": plain(rule.dedupe_scope),
                "attach_snapshot": rule.attach_snapshot,
                "camera_ids": sorted(camera_ids),
                "windows": [{"iso_dow": w.iso_dow, "start": w.start_time.isoformat(), "end": w.end_time.isoformat()}
                            for w in windows],
                "targets": [{"type": plain(t.target_type), "value": t.target_value, "label": t.label}
                            for t in targets],
                "version": rule.version,
            },
        )

    def active_at(self, occurred_at: datetime) -> bool:
        """No windows = always active."""
        if not self.windows:
            return True
        local = occurred_at.astimezone(self.tz)
        return any(w.contains(local) for w in self.windows)

    def _who_matches(self, event) -> bool:
        if self.match_mode == MatchMode.ANYONE:
            return True
        if self.match_mode == MatchMode.STRANGERS:
            return event.kind == EventKind.STRANGER
        if event.kind != EventKind.MATCHED:
            return False                      # KNOWN and TARGETS need a recognised person
        if self.match_mode == MatchMode.KNOWN:
            return True
        if event.person_uuid and event.person_uuid in self.person_ids:
            return True
        if self.group_ids & set(event.group_ids or []):
            return True
        names = {n.strip().lower() for n in event.group_names or []}
        return bool(self.group_labels & names)

    def matches(self, event) -> bool:
        """`event` is an Event row (or anything with the same attributes)."""
        if event.camera_id not in self.camera_ids or plain(event.kind) not in self.event_kinds:
            return False
        if not self._who_matches(event):
            return False
        # A score threshold only applies to recognised people (a stranger's score is its closest
        # non-match). Missing liveness passes: liveness detection may be off on the box.
        if self.min_match_score is not None and event.kind == EventKind.MATCHED and \
                (event.match_score is None or event.match_score < self.min_match_score):
            return False
        if self.min_liveness is not None and event.liveness_score is not None and \
                event.liveness_score < self.min_liveness:
            return False
        return self.active_at(event.occurred_at)
