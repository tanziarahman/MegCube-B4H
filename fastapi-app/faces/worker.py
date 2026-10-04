"""Fingerprints each new walk-past's face and whole body (sightings.face_embedding, .body_embedding),
a few per poll cycle.

Called by the alarm ingest loop after each poll, outside the alarm transaction, so alarms never wait
for pictures. Oldest first: the box rotates old pictures out, so they're the ones at risk. A
picture with nothing usable is marked "<model>:none" and not tried again.
"""
import asyncio
import logging
import os

from sqlalchemy import or_, update
from sqlmodel import col, select

from core import box_image
from models import Event, Sighting

from .embedder import BODY_MODEL_NAME, MODEL_NAME, BodyEmbedder, FaceEmbedder, models_present

log = logging.getLogger("b4h.faces")

ENABLED = os.getenv("FACE_MATCHING", "1") != "0"
PER_CYCLE = int(os.getenv("FACE_PER_CYCLE", "40"))
PICTURES_PER_SIGHTING = 3            # try up to this many of a walk-past's face pictures
NO_FACE = f"{MODEL_NAME}:none"
NO_BODY = f"{BODY_MODEL_NAME}:none"

state: dict = {"enabled": False, "reason": None, "last_error": None, "done": 0}
_embedders: tuple[FaceEmbedder, BodyEmbedder] | None = None


def embedders() -> tuple[FaceEmbedder, BodyEmbedder] | None:
    """The shared (face, body) embedders, or None (with state["reason"]) when matching can't run."""
    global _embedders
    if _embedders is not None:
        return _embedders
    if not ENABLED:
        state["reason"] = "FACE_MATCHING=0"
        return None
    if not models_present():
        state["reason"] = "Models missing: run `uv run python -m faces.download`"
        return None
    try:
        _embedders = (FaceEmbedder(), BodyEmbedder())
    except Exception as exc:  # noqa: BLE001 - e.g. OpenCV missing; the rest of the portal still works
        state["reason"] = f"Couldn't load the models: {exc!r}"[:300]
        return None
    state.update(enabled=True, reason=None)
    return _embedders


def _average(vectors: list[list[float]]) -> list[float]:
    total = [sum(values) for values in zip(*vectors)]
    norm = sum(v * v for v in total) ** 0.5 or 1.0
    return [v / norm for v in total]


async def _pictures(paths: list[str], fingerprint) -> list[list[float]]:
    """Fingerprints of the pictures the box still has (fingerprint: bytes -> vector or None)."""
    vectors = []
    for path in paths:
        found = await box_image(path)               # None: the box has rotated it out
        if found is None:
            continue
        vector = await asyncio.to_thread(fingerprint, found[0])
        if vector is not None:
            vectors.append(vector)
    return vectors


async def process_pending(sessions, limit: int = PER_CYCLE, face_embedder=None, body_embedder=None) -> int:
    """Fingerprint up to `limit` walk-pasts that have a face or body picture without a fingerprint yet.
    Returns how many were handled. A box that can't be reached raises (tried again next cycle)."""
    if face_embedder is None or body_embedder is None:
        loaded = embedders()
        if loaded is None:
            return 0
        face_embedder, body_embedder = face_embedder or loaded[0], body_embedder or loaded[1]
    face_todo = col(Sighting.best_face_image_path).is_not(None) & col(Sighting.embedding_model).is_(None)
    body_todo = col(Sighting.best_body_image_path).is_not(None) & col(Sighting.body_embedding_model).is_(None)
    async with sessions() as session:
        pending = (await session.exec(
            select(Sighting.id, Sighting.embedding_model, Sighting.best_face_image_path,
                   Sighting.body_embedding_model, Sighting.best_body_image_path)
            .where(or_(face_todo, body_todo)).order_by(Sighting.first_seen_at, Sighting.id).limit(limit))).all()
        if not pending:
            return 0
        rows = (await session.exec(
            select(Event.sighting_id, Event.face_image_path)
            .where(col(Event.sighting_id).in_([p[0] for p in pending]), col(Event.face_image_path).is_not(None))
            .order_by(Event.sighting_id, Event.occurred_at, Event.id))).all()
    faces: dict[int, list[str]] = {p[0]: [] for p in pending}
    for sid, path in rows:
        if len(faces[sid]) < PICTURES_PER_SIGHTING and path not in faces[sid]:
            faces[sid].append(path)

    updates: dict[int, dict] = {}
    for sid, face_model, face_path, body_model, body_path in pending:
        values: dict = {}
        if face_path is not None and face_model is None:
            vectors = await _pictures(faces[sid], lambda data: getattr(face_embedder.fingerprint(data), "vector", None))
            values.update(face_embedding=_average(vectors) if vectors else None,
                          embedding_model=MODEL_NAME if vectors else NO_FACE)
        if body_path is not None and body_model is None:
            vectors = await _pictures([body_path], body_embedder.fingerprint)
            values.update(body_embedding=vectors[0] if vectors else None,
                          body_embedding_model=BODY_MODEL_NAME if vectors else NO_BODY)
        updates[sid] = values

    async with sessions() as session:
        async with session.begin():
            for sid, values in updates.items():
                # Only fill what's still empty: a merge may have moved or removed the row meanwhile.
                for model_column in ("embedding_model", "body_embedding_model"):
                    part = {k: v for k, v in values.items()
                            if (k in ("face_embedding", "embedding_model")) == (model_column == "embedding_model")}
                    if part:
                        await session.exec(update(Sighting).where(
                            col(Sighting.id) == sid, col(getattr(Sighting, model_column)).is_(None)).values(**part))
    state["done"] += len(updates)
    return len(updates)
