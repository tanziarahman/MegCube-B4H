"""Different people among the walk-pasts of a period: group walk-pasts that look like the same person.

Runs at query time on the walk-pasts of the chosen cameras and period, so "different people" is
always for exactly that window, and a new threshold applies at once.

Two walk-pasts are compared by their whole-body (clothing) fingerprints, and by their face
fingerprints when both have one: 60 % body, 40 % face. Bodies are only compared within the same
local day (people change clothes), so across days only faces can link a person. Two walk-pasts on
the same camera at the same moment are two people and never grouped. Groups are joined by average
similarity (every member of one group against every member of the other), which doesn't chain one
look-alike into a big wrong group the way "most similar member" does.

Calibrated on this box's pictures (2026-10-04, checked by eye: about 6 people in 70 walk-pasts):
faces alone gave 25-42 people, body + face at 0.35 gave 8 (a person on the other camera's lighting
split off). The range uses PEOPLE_MATCH_RANGE either side.
"""
import os
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

MATCH_THRESHOLD = float(os.getenv("PEOPLE_MATCH_THRESHOLD", "0.35"))
RANGE = float(os.getenv("PEOPLE_MATCH_RANGE", "0.05"))
BODY_WEIGHT = float(os.getenv("PEOPLE_BODY_WEIGHT", "0.6"))
MAX_WALK_PASTS = int(os.getenv("PEOPLE_MAX_GROUPING", "2000"))   # beyond this a period is too long to group


@dataclass(frozen=True)
class WalkPast:
    face: list[float] | None
    body: list[float] | None
    day: date                     # box-local
    camera_id: int
    first_seen_at: datetime
    last_seen_at: datetime


def _fingerprints(values: list[list[float] | None]) -> tuple[np.ndarray, np.ndarray]:
    present = np.array([v is not None for v in values])
    size = next((len(v) for v in values if v is not None), 1)
    matrix = np.array([v if v is not None else [0.0] * size for v in values], dtype=np.float64)
    return matrix, present


def similarities(walks: list[WalkPast]) -> tuple[np.ndarray, np.ndarray]:
    """(similarity, apart): similarity is NaN where nothing can be compared; apart marks pairs that
    were on one camera at the same time."""
    faces, has_face = _fingerprints([w.face for w in walks])
    bodies, has_body = _fingerprints([w.body for w in walks])
    days = np.array([w.day.toordinal() for w in walks])
    face_ok = has_face[:, None] & has_face[None, :]
    body_ok = has_body[:, None] & has_body[None, :] & (days[:, None] == days[None, :])
    face_sim, body_sim = faces @ faces.T, bodies @ bodies.T
    sim = np.where(face_ok & body_ok, BODY_WEIGHT * body_sim + (1 - BODY_WEIGHT) * face_sim,
                   np.where(body_ok, body_sim, np.where(face_ok, face_sim, np.nan)))

    cameras = np.array([w.camera_id for w in walks])
    starts = np.array([w.first_seen_at.timestamp() for w in walks])
    ends = np.array([w.last_seen_at.timestamp() for w in walks])
    apart = (cameras[:, None] == cameras[None, :]) & (starts[:, None] <= ends[None, :]) & (starts[None, :] <= ends[:, None])
    np.fill_diagonal(apart, False)
    np.fill_diagonal(sim, np.nan)
    return sim, apart


def group(sim: np.ndarray, apart: np.ndarray, threshold: float) -> list[int]:
    """Average-linkage grouping: repeatedly join the two groups with the highest average similarity
    while it's at least `threshold` and no member of one was seen together with a member of the other.
    Returns a group label per walk-past."""
    n = len(sim)
    if not n:
        return []
    valid = ~np.isnan(sim)
    total = np.where(valid, sim, 0.0)
    count = valid.astype(np.float64)
    blocked = apart.copy()
    alive = np.ones(n, dtype=bool)
    label = np.arange(n)

    def averages(i: int) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            row = np.where((count[i] > 0) & ~blocked[i] & alive, total[i] / count[i], -np.inf)
        row[i] = -np.inf
        return row

    best = np.full(n, -np.inf)
    best_to = np.zeros(n, dtype=np.int64)

    def refresh(i: int) -> None:
        row = averages(i)
        best_to[i] = int(np.argmax(row))
        best[i] = row[best_to[i]]

    for i in range(n):
        refresh(i)
    while True:
        i = int(np.argmax(np.where(alive, best, -np.inf)))
        if not alive[i] or best[i] < threshold:
            break
        j = int(best_to[i])
        total[i] += total[j]
        total[:, i] = total[i]
        count[i] += count[j]
        count[:, i] = count[i]
        blocked[i] |= blocked[j]
        blocked[:, i] = blocked[i]
        alive[j] = False
        best[j] = -np.inf
        label[label == j] = i
        row = averages(i)
        best_to[i] = int(np.argmax(row))
        best[i] = row[best_to[i]]
        # Groups whose best partner was i or j must look again; others may now prefer i.
        for k in np.flatnonzero(alive & ((best_to == i) | (best_to == j))):
            if k != i:
                refresh(int(k))
        better = alive & (row > best)
        better[i] = False
        best_to[better] = i
        best[better] = row[better]
    _, labels = np.unique(label, return_inverse=True)
    return [int(v) for v in labels]


def labels(walks: list[WalkPast], threshold: float = MATCH_THRESHOLD) -> list[int] | None:
    """Group label per walk-past, or None if there are too many to group."""
    if len(walks) > MAX_WALK_PASTS:
        return None
    sim, apart = similarities(walks) if walks else (np.zeros((0, 0)), np.zeros((0, 0), dtype=bool))
    return group(sim, apart, threshold)


def count_people(walks: list[WalkPast]) -> dict | None:
    """{"people", "low", "high"}: low from a looser threshold, high from a stricter one; None if too many."""
    if len(walks) > MAX_WALK_PASTS:
        return None
    if not walks:
        return {"people": 0, "low": 0, "high": 0}
    sim, apart = similarities(walks)
    count = lambda threshold: len(set(group(sim, apart, threshold)))
    return {"people": count(MATCH_THRESHOLD), "low": count(MATCH_THRESHOLD - RANGE),
            "high": count(MATCH_THRESHOLD + RANGE)}
