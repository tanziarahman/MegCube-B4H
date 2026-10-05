# Dashboard performance plan: Redis cache + pre-computed counts

> **Who this is for:** an AI coding agent implementing the change in this repository (`MegCube-B4H`).
> **Status:** plan only. Nothing in this document has been implemented yet.
> **Scope:** backend `fastapi-app/` (main work), a small part of `client/` (Phase 7), docs (Phase 9).

---

## 0. Rules for the agent (read first)

1. **Work in phase order.** Each phase ends with a **checkpoint** (commands to run plus what must be true). Don't start the next phase until the checkpoint passes.
2. **Don't invent APIs.** Every existing function, file, column and env var named here was checked against the code on 2026-10-05. If something named here doesn't exist, stop and report it. Don't guess a replacement.
3. **Don't change the existing response shape of `GET /api/dashboard/summary`.** Add new things only under the new top-level key `meta`. In particular, the `health` object must keep **exactly** its current six keys, because `tests/test_dashboard.py` compares it with `==`.
4. **The two existing tests in `tests/test_dashboard.py` must pass without edits** at every checkpoint.
5. **Never call the box in parallel** (no `asyncio.gather` over `box.call`). `b4h.B4HClient` serializes calls with a lock, and the box can't handle parallel queries.
6. **Never run two queries at once on one `AsyncSession`** (no `asyncio.gather` over the same session).
7. **Match the house style:** module docstrings that explain *why*, short comments, `plain()` for enum values, `pg_insert` upserts, raw `text()` SQL where the codebase already uses it (`counting/builder.py`).
8. **Redis and the database are both optional infrastructure.** With `REDIS_URL` empty the app must work exactly as it does without caching. With `DATABASE_URL` empty the dashboard must work exactly as it does today (box path).
9. Run commands from `fastapi-app/` with `uv run ...`. On Windows PowerShell, set env vars like this: `$env:TEST_DATABASE_URL="postgresql://..."`.
10. Don't commit unless the user asks.

---

## 1. How the system works today (verified facts)

### 1.1 Big picture

```
Browser → Next.js (client/, :3000) → rewrites /api/* (+ X-API-Key via src/middleware.ts) → FastAPI (fastapi-app/, :8000) → B4H box (HTTPS, one call at a time)
                                                                                       ↘ PostgreSQL on Neon (optional, DATABASE_URL)
```

- `main.py`: the lifespan logs in to the box, starts the background workers (`alarms/worker.start()`) and disposes the DB and box client on shutdown. It maps `B4HError` to 502, `httpx` transport errors to 503/504 and `DBAPIError` to 503. Every router is included with `Depends(check_access)`.
- `core.py`: box client singleton `box`, `BOX_TZ`, `BOX_TIMEZONE_NAME`, `to_ms`, `time_range`, `alarm_history_page`, `box_image`, and the in-process `people_cache` (the only cache that exists today).
- `b4h.py`: `B4HClient.call()` holds `_call_lock`, so **every box call in the process is serialized**: dashboard calls, the ingest poller, devices, recognition and so on.
- `db.py`: lazy async engine (`db.sessions()` returns an `async_sessionmaker`), `db.get_session` (FastAPI dependency), `db.enabled()`. It handles the Neon pooler (statement cache off).

### 1.2 The background ingest pipeline (already stores everything the dashboard needs)

`alarms/worker.ingest_loop` runs every `ALARM_POLL_SECONDS` (5 s) when `DATABASE_URL` is set:

1. `ingest.sync_cameras` (every 10 min): copies the box's `device_config` into `cameras`.
2. For each `IngestStream` (`recognition`, `capture`), `ingest.poll_stream` reads `alarm_history` for the window `[cursor − 60 s, now]` and normalizes each record (`alarms/normalize.py`) into **`events`**: one row per box record, `kind ∈ {matched, stranger, face_capture, body_capture}`. It inserts with `ON CONFLICT DO NOTHING RETURNING`, so only new events continue.
3. In the **same transaction**: `counting.attach(session, new_events, box_id)` builds `sightings`, then `rebuild_buckets` **recounts** the touched 15-minute `count_buckets` rows from `sightings` and `events`. After that, `engine.process` fires the alarm rules.
4. Outside that transaction: `faces.worker.process_pending` (fingerprints).

Key point: **every matched, stranger, face-capture and body-capture record the dashboard downloads from the box is already in `events`**, with `occurred_at`, `camera_id`, `face_track_id`, `body_track_id`, `person_uuid`, `person_name`, `match_score` (0–100) and `liveness_score` (0–100).

### 1.3 Relevant tables (from `models/`)

| Table | Key columns | Notes |
|---|---|---|
| `boxes` | `id`, `base_url` (unique) | One row; `ingest.ensure_box` upserts it |
| `cameras` | `id`, `box_id`, `device_id` (box id), `name`, `deleted_at` | Soft-deleted |
| `events` | `id`, `box_id`, `camera_id`, `alarm_id`, `kind`, `occurred_at` (UTC), track ids, person fields, scores | Unique `(box_id, kind, alarm_id)`. Indexes: `(camera_id, occurred_at)`, BRIN `occurred_at`, partial `(person_uuid, occurred_at)`, `sighting_id` |
| `sightings` | one walk-past | People counting |
| `count_buckets` | PK `(camera_id, bucket_start)`; `local_date`, `local_hour`, `local_minute`, `iso_dow`; `sightings`, `face_sightings`, `body_sightings`, `events` | **Recounted, never incremented**, by `counting/builder.rebuild_buckets` (raw SQL `_REBUILD`). `bucket_start` is UTC floored to 15 min, which lines up with local 15-min boundaries |
| `ingest_cursors` | PK `(box_id, stream)`; `last_occurred_at`, `last_success_at`, `consecutive_failures` | Poll progress |

Alembic head today: **`ad18f13a53a4`** (`migrations/versions/2026_10_04-ad18f13a53a4_body_fingerprints.py`). The file name template is `YYYY_MM_DD-<rev>_<slug>.py`.

### 1.4 The dashboard today (`routers/dashboard.py`, `GET /api/dashboard/summary?date=YYYY-MM-DD`)

Per request, **sequentially**, all through the box lock:

1. `device_config`, `device_state`, `task_list` (3 calls)
2. `get_system_time`, `get_time_info` (2 calls)
3. `_collect_history` for today's **matched**, **strangers**, **captures**: pages of 30 records, up to 5,000 records each, so **up to ~500 box calls**
4. Yesterday's three totals (`size: 1`, 3 calls)

It then computes, in Python: totals, a face/body capture split, peak hour, busiest device, average score, low confidence (<70), low liveness (<80), top 5 people, 24-hour histogram, latest 8 events, and "encounter" metrics (distinct `device:track` keys).

The frontend (`client/src/components/dashboard/DashboardView.tsx`) calls it on load, **every 45 s per open tab**, and on the Refresh button (`fetch(..., {cache: 'no-store'})` in `client/src/lib/dashboard.ts`).

### 1.5 Why it's slow

- Hundreds of serialized box round trips per load on a busy day, and they queue behind the ingest poller's own box calls every 5 s.
- It **re-downloads data the backend already has in `events`**.
- Nothing is cached, so every tab and every 45 s repeats all of it.
- The DB has no stored per-kind or per-day dashboard counts, so even a DB rewrite would need aggregation on every request.

---

## 2. Goal and non-goals

**Goal**

1. Serve dashboard activity and insight numbers **from PostgreSQL**, using **pre-computed counts** stored in tables (`count_buckets` gets per-kind columns, plus a new `daily_stats` table). Keep the box path as a fallback.
2. Put a **Redis read-through cache** in front of every dashboard part: Redis first (hit); on a miss, load from the DB or box, store it, and return it.
3. Keep the HTTP contract backward compatible, the app working without Redis and/or without a DB, and all existing tests passing.

**Targets** (measure in Phase 10):

- Cache hit: < 50 ms server time.
- Cache miss, DB source: < 1 s, including the 5 health box calls.
- Zero `alarm_history` box calls for DB-covered dates.

**Non-goals** (don't do these):

- Don't cache or change the counting, alarms, recognition, capture or personnel pages.
- Don't move `core.people_cache` to Redis.
- Don't change ingest polling frequency or alarm logic.
- Don't add multi-process support (the app must stay one process; see `alarms/worker.py`).
- Don't remove the box-based dashboard code. It becomes the fallback.

---

## 3. Design

### 3.1 Data flow after the change

```
                       GET /api/dashboard/summary?date=D[&fresh=1]
                                        │
                     parse/validate D (422 before ANY I/O)
                                        │
        ┌───────────────────────────────┼─────────────────────────────────┐
        ▼                               ▼                                 ▼
  HEALTH part                    COVERAGE info                     ACTIVITY part (per date + source)
  key dash:health                key dash:coverage                  key dash:activity:<D>:<source>
  TTL 15 s                       TTL 300 s                          TTL 15 s (D ≥ today) / 3600 s (past)
  loader: box (5 calls)          loader: DB (box id,                loader: source = database → SQL on count_buckets,
                                 min(count_buckets.local_date))              daily_stats, events (≈6 small queries)
                                                                    loader: source = box → existing box code
        └───────────────────────────────┴─────────────────────────────────┘
                                        │
                          compose response (+ new "meta"), never cached as a whole

WRITE SIDE (existing ingest transaction, every 5 s):
 events inserted → counting.attach → rebuild_buckets (now also per-kind/score columns)
                                   → dashboard_data.stats.rebuild_days (daily_stats for touched local dates)
 after COMMIT → delete Redis activity keys for touched dates that are before today (and the day after each)
```

### 3.2 Decisions and reasons

| # | Decision | Why |
|---|---|---|
| D1 | Additive numbers (per-kind counts, low-confidence/liveness counts, score sum/count) go into **`count_buckets`** as new columns, recounted by the existing `_REBUILD` SQL | The bucket recount runs for every new event batch, merge and backfill. "Recount, never increment" means the totals can't drift. Day totals are then a `SUM` over ≤ 96 × cameras rows, and the hourly histogram is a `GROUP BY local_hour` |
| D2 | Distinct-count numbers (encounters, unique recognized people, recognized capture tracks) go into a new **`daily_stats`** table, one row per `(box_id, local_date)`, **recounted** from `events` for each local date a batch touches | Distinct counts can't be summed across buckets. Recounting one day per batch is one indexed aggregate. They depend on `events` only, so sighting merges don't affect them |
| D3 | `daily_stats` is rebuilt at the **end of `counting.attach`** | `attach` is the single place that runs for polls, the counting backfill and the tests' `save()` helper, so everything that adds events keeps the stats right |
| D4 | Latest 8 events and top 5 people are **queried live** from `events` (new btree index `(box_id, occurred_at)`) and cached in Redis | They're small `LIMIT` queries; storing them adds complexity without benefit |
| D5 | Health (devices online, streams, tasks, box clock) **stays on the box**, cached 15 s | The DB has no live device state |
| D6 | Source selection per date: **database** when the DB is configured and the date is fully covered by ingested data, else **box** (existing code) | Before ingest existed, `events` has nothing, so the DB would show wrong zeros. Coverage start = `min(count_buckets.local_date) + 1 day` (the first ingested day is assumed partial) |
| D7 | Redis is **fail-open** with a 30 s circuit breaker and 0.5 s socket timeouts | A Redis outage must never break or slow the dashboard by more than one timeout |
| D8 | **In-process single-flight** (per-key `asyncio.Lock`) around loaders | Several tabs refreshing at once would otherwise queue duplicate box calls. One process is already required by the workers |
| D9 | Today's keys rely on a short TTL (15 s) and **aren't invalidated** by ingest. Past dates are invalidated after commit | Ingest touches today every 5 s, so invalidating today would make the cache useless. Past dates change only through late records or backfills |
| D10 | Invalidate **after** the transaction commits, never inside it | Invalidating before commit lets a reader re-cache the old numbers |
| D11 | If the DB fails while loading coverage or activity (auto mode), **fall back to the box** and report it in `meta` | The dashboard is the landing page and must stay up |

### 3.3 Semantic differences in database mode (document them; they're intended)

| Field | Box mode (today) | Database mode |
|---|---|---|
| `activity.captures` | box `total_count`, **includes `structure` records** (pedestrian, vehicle, …) | `face_captures + body_captures` (normalize drops structure records) |
| `activity.capture_breakdown_limited`, `insights.analysis_limited` | true above 5,000 records | always `false` (no sampling) |
| `insights.analysis_sampled` | records read | `matched + strangers + captures` |
| `insights.top_people` | names found anywhere in matched + stranger records (a stranger's *closest* library face could leak in) | `person_name` of **matched** events only (fixes that leak) |
| encounter keys | `device_id:track_id` | `camera_id:track_id` (same meaning, DB ids) |
| Deleted recognition records (`DELETE /api/recognition/{id}`) | disappear (deleted on the box) | **still counted** (the portal's own `events` keeps them, like incidents). Known limitation; don't fix in this plan |

### 3.4 New response key `meta` (additive)

```json
"meta": {
  "source": "database",            // "database" | "box"
  "fallback_reason": null,         // string when auto mode fell back to the box because the DB failed
  "coverage_start": "2026-10-02",  // first box-local date served from the DB, or null
  "cache": { "health": "hit", "activity": "miss" },   // each: "hit" | "miss" | "bypass" | "off"
  "ingest_last_success_at": "2026-10-05T08:15:03+00:00"   // DB source + today only, else null
}
```

And one new attention item type (database source, today only), appended after the existing ones:
`{"severity": "warning", "type": "ingest_lagging", "message": "Dashboard numbers may be behind: box records were last read N min ago", "device_id": null}`

### 3.5 New query parameter

`fresh` (bool, default `false`): when true, skip the Redis **read** for health and activity (still single-flighted, and the result is still written to Redis). The Refresh button uses it. The 45 s auto-refresh doesn't.

### 3.6 New environment variables

| Variable | Default | Meaning |
|---|---|---|
| `REDIS_URL` | (empty = cache off) | e.g. `redis://localhost:6379/0` |
| `REDIS_PREFIX` | `b4h` | Namespace for every key |
| `DASHBOARD_HEALTH_CACHE_SECONDS` | `15` | Health part TTL |
| `DASHBOARD_TODAY_CACHE_SECONDS` | `15` | Activity TTL for today (and future dates) |
| `DASHBOARD_PAST_CACHE_SECONDS` | `3600` | Activity TTL for past dates |
| `DASHBOARD_SOURCE` | `auto` | `auto` \| `database` \| `box` |
| `DASHBOARD_INGEST_LAG_SECONDS` | `120` | Above this, add the `ingest_lagging` attention item |

---

## 4. File map (what will exist at the end)

```
fastapi-app/
├─ cache.py                         NEW  Redis client, fail-open helpers, single-flight get_or_load, key builder
├─ dashboard_data/                  NEW  package (named so it doesn't clash with routers/dashboard.py)
│  ├─ __init__.py                   NEW  docstring only
│  ├─ stats.py                      NEW  thresholds, local_day_range(), rebuild_days() (daily_stats writer)
│  ├─ queries.py                    NEW  coverage(), activity() (DB read side)
│  ├─ box_source.py                 NEW  the existing box-based code, moved out of routers/dashboard.py
│  └─ rebuild.py                    NEW  CLI: recount buckets + daily_stats for existing data
├─ models/dashboard.py              NEW  DailyStat table
├─ models/__init__.py               EDIT export DailyStat, update docstring module list
├─ models/counting.py               EDIT CountBucket: 8 new columns
├─ models/ingest.py                 EDIT Event: new index ix_events_box_time
├─ counting/builder.py              EDIT _REBUILD SQL fills the new columns; attach() calls rebuild_days()
├─ alarms/ingest.py                 EDIT poll_stream: invalidate past-date dashboard keys after commit
├─ routers/dashboard.py             EDIT thin orchestrator: validate → cache → source → compose
├─ routers/devices.py               EDIT invalidate dash:health after add/edit/delete
├─ main.py                          EDIT lifespan: cache.connect()/cache.close()
├─ migrations/versions/2026_10_05-<rev>_dashboard_stats.py   NEW
├─ pyproject.toml / uv.lock         EDIT add redis
└─ tests/
   ├─ conftest.py                   EDIT cache off by default; FakeRedis + `redis_cache` fixture
   ├─ test_cache.py                 NEW
   ├─ test_dashboard.py             EDIT add tests (existing two unchanged)
   ├─ test_dashboard_db.py          NEW  (needs TEST_DATABASE_URL)
   └─ test_models.py                EDIT daily_stats + new index
client/src/lib/dashboard.ts         EDIT meta type, fresh option
client/src/components/dashboard/DashboardView.tsx   EDIT Refresh → fresh; small source label
client/src/mocks/handlers.ts        EDIT (optional) add meta to sampleDashboard
docs/backend-api.md, docs/architecture.md, fastapi-app/README.md   EDIT
```

---

## Phase 0: Baseline

1. `cd fastapi-app && uv sync && uv run pytest -q`. Record the pass/skip counts. If `TEST_DATABASE_URL` is available, also run with it.
2. If a running backend and box are available, record the baseline:
   `curl -s -o NUL -w "%{time_total}\n" -H "X-API-Key: $KEY" "http://localhost:8000/api/dashboard/summary"` (×3). Write the numbers down for Phase 10.
3. Read these files completely before you change anything: `routers/dashboard.py`, `counting/builder.py`, `alarms/ingest.py`, `db.py`, `core.py`, `models/counting.py`, `models/ingest.py`, `tests/conftest.py`, `tests/test_dashboard.py`, `tests/test_counting_builder.py` (helpers `record`, `save`), `tests/test_alarms_db.py` (helpers `BoxHistory`, `setup_box`, `rows`).

**Checkpoint 0:** the test suite is green (DB tests may be skipped). Baseline recorded or noted as unavailable.

---

## Phase 1: Redis infrastructure (`cache.py`)

### 1.1 Dependency

`uv add "redis>=5.0"` (this updates `pyproject.toml` and `uv.lock`). Use `redis.asyncio`. Don't add `fakeredis`; tests use a small fake (1.5).

### 1.2 `fastapi-app/cache.py`: exact public API

```python
"""Redis cache (optional: REDIS_URL). Fail-open: any Redis problem counts as a miss, so the portal
works the same without Redis, only slower. After an error Redis is skipped for 30 s, so an outage costs
one short timeout, not one per request. Loaders are single-flighted in this process (one backend
process is required anyway, see alarms/worker.py), so tabs refreshing together don't queue duplicate
box calls."""

REDIS_URL: str            # os.getenv("REDIS_URL", "")
PREFIX: str               # os.getenv("REDIS_PREFIX", "b4h")
VERSION = "v1"            # bump when a cached payload's shape changes

def key(*parts: str) -> str                      # f"{PREFIX}:{VERSION}:" + ":".join(parts)
def enabled() -> bool                            # a client exists (or can be created from REDIS_URL)
def configure(client) -> None                    # tests: use this client (None = off)
async def connect() -> None                      # lifespan: create client lazily + PING; log OK / warning; never raises
async def close() -> None                        # lifespan: aclose() the client if any
async def get_json(k: str) -> Any | None         # None = miss / off / error
async def set_json(k: str, value: Any, ttl: float) -> None
async def delete(*keys: str) -> None
async def delete_prefix(prefix: str) -> None     # SCAN MATCH prefix* + DELETE in chunks of 500; NEVER use KEYS
async def get_or_load(k: str, ttl: float, loader: Callable[[], Awaitable[Any]], *, fresh: bool = False) -> tuple[Any, str]
    # returns (value, state) where state ∈ {"hit", "miss", "bypass", "off"}
```

Implementation requirements:

- Client: `redis.asyncio.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5, health_check_interval=30)`. Create it lazily on first use (`from_url` doesn't connect until the first command).
- Serialization: `json.dumps(value, separators=(",", ":"), default=str)` / `json.loads`.
- TTL: `SET k v PX int(ttl*1000)`.
- **Circuit breaker:** module global `_skip_until = 0.0` (monotonic). Any exception from a Redis command sets `_skip_until = time.monotonic() + 30` and logs `log.warning("Redis unavailable (%r); caching paused for 30 s", exc)` at most once per pause. While paused, `get_json` returns `None`, and `set_json`/`delete` do nothing. Catch `Exception` (Redis errors, `OSError`, `asyncio.TimeoutError`), but never `asyncio.CancelledError`.
- **`get_or_load`:**
  1. If off (no client), return `(normalize(await loader()), "off")`.
  2. If not `fresh`: `cached = await get_json(k)`; if not None, return `(cached, "hit")`.
  3. `async with _locks.setdefault(k, asyncio.Lock()):` re-check the cache (unless `fresh`; a concurrent caller may have filled it, and if so return "hit"). Otherwise `value = normalize(await loader())`, then `await set_json(k, value, ttl)`, then return `(value, "bypass" if fresh else "miss")`.
  4. `normalize(v) = json.loads(json.dumps(v, default=str))`, so a miss returns **exactly** what a later hit returns (datetimes become strings either way).
  5. Loader exceptions propagate (nothing is cached).
- Logger: `logging.getLogger("b4h.cache")`.
- Load `.env` the same way `db.py` does (`load_dotenv()` at import).

### 1.3 Key catalogue (the only keys used)

| Key | Built with | TTL |
|---|---|---|
| `b4h:v1:dash:health` | `cache.key("dash", "health")` | `DASHBOARD_HEALTH_CACHE_SECONDS` |
| `b4h:v1:dash:coverage` | `cache.key("dash", "coverage")` | 300 s |
| `b4h:v1:dash:activity:<YYYY-MM-DD>:<database\|box>` | `cache.key("dash", "activity", day.isoformat(), source)` | today/future: `DASHBOARD_TODAY_CACHE_SECONDS`; past: `DASHBOARD_PAST_CACHE_SECONDS` |

Dashboard prefix for bulk delete: `cache.key("dash", "")` → `b4h:v1:dash:`.

### 1.4 Wire into `main.py`

In `lifespan`, call `await cache.connect()` right after the box login block (before `alarm_worker.start()`), and `await cache.close()` after `await db.dispose()`. Add `import cache`.

### 1.5 Tests support (`tests/conftest.py`)

- Right after `db.DATABASE_URL = ""`, add `import cache` and then `cache.REDIS_URL = ""` and `cache.configure(None)`. **Caching is off in every test unless a test asks for it.**
- Add `class FakeRedis` with async `get`, `set(name, value, px=None)`, `delete(*names)`, `scan_iter(match=None, count=None)` (async generator), `ping`, `aclose`. Store values in a dict with an expiry (`time.monotonic() + px/1000`) and treat expired entries as missing. Add a `fail = False` flag: when True, every method raises `ConnectionError("down")`. Count calls in `self.calls`.
- Fixture:
  ```python
  @pytest.fixture
  def redis_cache(monkeypatch):
      fake = FakeRedis()
      cache.configure(fake)
      monkeypatch.setattr(cache, "_skip_until", 0.0)
      yield fake
      cache.configure(None)
  ```

### 1.6 `tests/test_cache.py` (no Redis, no DB)

Write these tests (use `pytest.mark.anyio` with an `anyio_backend` fixture returning `"asyncio"`, as `test_counting_builder.py` does):

1. `set_json` then `get_json` round-trips a dict; `get_or_load` gives "miss" first, then "hit", and the loader is called once.
2. With `px` expired (monkeypatch `time.monotonic` in the fake, or use ttl=0.001 and a short `asyncio.sleep`), it's a miss again.
3. `fresh=True` calls the loader and returns "bypass", and the new value is stored.
4. Off (`configure(None)`): returns "off", and the loader runs every call.
5. Fail-open: `fake.fail = True`, so `get_or_load` returns the loader value with no exception. A second call within 30 s doesn't touch the fake (`fake.calls` unchanged).
6. Single-flight: 5 concurrent `get_or_load` calls on one key with a slow loader (`await asyncio.sleep(0.05)`) mean the loader runs exactly once.
7. `delete_prefix("b4h:v1:dash:")` removes only matching keys.
8. A miss value equals the later hit value for a payload containing a `datetime` (both are strings).

**Checkpoint 1:** `uv run pytest -q` is green; `tests/test_cache.py` passes; with `REDIS_URL` empty the app starts and logs nothing about Redis beyond one info line.

---

## Phase 2: Schema (models + migration)

### 2.1 `models/counting.py`: `CountBucket` new columns

Add after `events: int = 0`, each with a DB default so existing rows get filled:

```python
    # Dashboard numbers, recounted with the others (counting/builder.py _REBUILD). Additive, so a day
    # or an hour is a SUM over buckets. "identity" = matched + stranger records.
    matched_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    stranger_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    face_capture_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    body_capture_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    low_confidence_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})   # identity, match_score < 70
    low_liveness_events: int = Field(default=0, sa_column_kwargs={"server_default": "0"})     # identity, liveness_score < 80
    identity_score_sum: float = Field(default=0, sa_column_kwargs={"server_default": "0"})    # sum of match_score
    identity_score_count: int = Field(default=0, sa_column_kwargs={"server_default": "0"})    # rows with a match_score
```

Update the class docstring to mention the dashboard columns in one sentence.

### 2.2 `models/dashboard.py` (new)

```python
"""Dashboard: per-day numbers that can't be added up from 15-minute buckets (distinct counts)."""
from datetime import date, datetime

from sqlalchemy import Date
from sqlmodel import Field, SQLModel

from .base import updated_at_field


class DailyStat(SQLModel, table=True):
    """One box-local day. Recounted from `events` for every day a batch touches
    (dashboard_data/stats.py), never incremented, so it can't drift. Built from events only, so
    sighting merges don't change it. Keys: a "track key" is camera + face/body track id (or the
    record itself when it has no track)."""
    __tablename__ = "daily_stats"

    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE", primary_key=True)
    local_date: date = Field(sa_type=Date, primary_key=True)
    tracked_encounters: int = 0          # distinct track keys among face + body captures
    face_encounters: int = 0             # ... among face captures
    body_encounters: int = 0             # ... among body captures
    recognized_encounters: int = 0       # ... among matched records
    stranger_encounters: int = 0         # ... among stranger records
    recognized_capture_tracks: int = 0   # track keys both matched and face-captured
    unique_recognized_people: int = 0    # distinct person_uuid (else lower(name)) among matched
    updated_at: datetime = updated_at_field()
```

Give every int column `sa_column_kwargs={"server_default": "0"}` too, to match 2.1.

### 2.3 `models/ingest.py`: new index on `Event`

Add to `Event.__table_args__`:
```python
        # Dashboard: one box's records of one local day (daily_stats recount, latest events, top people).
        Index("ix_events_box_time", "box_id", "occurred_at"),
```

### 2.4 `models/__init__.py`

`from .dashboard import DailyStat`, add `"DailyStat"` to `__all__` under a new `# dashboard` comment, and add the line `dashboard  daily_stats` to the docstring's module list.

### 2.5 Migration

1. `uv run alembic revision --autogenerate -m "dashboard stats"` (needs a DB at head `ad18f13a53a4`). If no DB is available, write the file by hand with `down_revision = 'ad18f13a53a4'`, named `2026_10_05-<12 hex chars>_dashboard_stats.py`, in the same style as `ad18f13a53a4_body_fingerprints.py`, including a short paragraph in the module docstring explaining the change.
2. Review it so it contains **exactly**:
   - `op.add_column('count_buckets', ...)` × 8 with `server_default='0'` and `nullable=False` (`sa.Integer()`, and `sa.Float()` for `identity_score_sum`).
   - `op.create_table('daily_stats', ...)` with PK `pk_daily_stats`, FK `fk_daily_stats_box_id_boxes` `ondelete='CASCADE'`, and the 7 int columns plus `updated_at` (`server_default=sa.text('now()')`).
   - The index, created **concurrently** so writes to the big `events` table aren't blocked:
     ```python
     with op.get_context().autocommit_block():
         op.create_index('ix_events_box_time', 'events', ['box_id', 'occurred_at'], unique=False,
                         postgresql_concurrently=True, if_not_exists=True)
     ```
   - A `downgrade()` that reverses all of it (drop the index concurrently in an autocommit block, drop the table, drop the 8 columns).
   - Nothing else. Delete any unrelated autogenerate noise.
3. `uv run alembic upgrade head`, then `uv run alembic check` (must report no differences).

### 2.6 `tests/test_models.py`

Add assertions in the file's existing style: `daily_stats` compiles for PostgreSQL with PK `(box_id, local_date)`; `events` has index `ix_events_box_time`; `count_buckets` has the 8 new columns.

**Checkpoint 2:** `uv run pytest -q` is green. With a DB: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` all succeed, and `alembic check` is clean.

---

## Phase 3: Write side (keep the stored counts correct)

### 3.1 `dashboard_data/__init__.py`

A docstring only: "Dashboard numbers from our database: stored per-day/per-bucket counts (stats), the read queries (queries), the original box-based computation used as a fallback (box_source), and a rebuild CLI (rebuild)."

### 3.2 `dashboard_data/stats.py`

```python
LOW_CONFIDENCE = 70.0   # identity records with match_score below this
LOW_LIVENESS = 80.0     # identity records with liveness_score below this (photo / screen held up)

def local_day_range(day: date, tz=None) -> tuple[datetime, datetime]:
    """[local midnight, next local midnight) of a box-local day, in UTC. DST-safe: both ends are
    built with datetime.combine(..., time(0), tz)."""

async def rebuild_days(session: AsyncSession, box_id: int, days: set[date]) -> None:
    """Recount daily_stats for these box-local days from `events` (upsert)."""
```

- `tz` defaults to `counting.settings.box_tz()`.
- `rebuild_days` runs `_REBUILD_DAY` once per day in `sorted(days)`:

```sql
WITH e AS (
    SELECT kind, person_uuid, person_name,
           CASE WHEN coalesce(face_track_id, body_track_id) IS NOT NULL
                THEN camera_id::text || ':' || coalesce(face_track_id, body_track_id)::text
                ELSE kind || ':' || camera_id::text || ':' || alarm_id::text END AS track_key
    FROM events
    WHERE box_id = :box_id AND occurred_at >= :start AND occurred_at < :end
), k AS (
    SELECT count(DISTINCT track_key) FILTER (WHERE kind IN ('face_capture', 'body_capture')) AS tracked,
           count(DISTINCT track_key) FILTER (WHERE kind = 'face_capture') AS face,
           count(DISTINCT track_key) FILTER (WHERE kind = 'body_capture') AS body,
           count(DISTINCT track_key) FILTER (WHERE kind = 'matched') AS recognized,
           count(DISTINCT track_key) FILTER (WHERE kind = 'stranger') AS stranger,
           count(DISTINCT coalesce(person_uuid, nullif(lower(btrim(person_name)), '')))
               FILTER (WHERE kind = 'matched') AS people
    FROM e
), j AS (
    SELECT count(*) AS n FROM (
        SELECT track_key FROM e WHERE kind = 'matched'
        INTERSECT
        SELECT track_key FROM e WHERE kind = 'face_capture'
    ) x
)
INSERT INTO daily_stats (box_id, local_date, tracked_encounters, face_encounters, body_encounters,
                         recognized_encounters, stranger_encounters, unique_recognized_people,
                         recognized_capture_tracks, updated_at)
SELECT :box_id, :local_date, k.tracked, k.face, k.body, k.recognized, k.stranger, k.people, j.n, now()
FROM k, j
ON CONFLICT (box_id, local_date) DO UPDATE SET
    tracked_encounters = excluded.tracked_encounters, face_encounters = excluded.face_encounters,
    body_encounters = excluded.body_encounters, recognized_encounters = excluded.recognized_encounters,
    stranger_encounters = excluded.stranger_encounters,
    unique_recognized_people = excluded.unique_recognized_people,
    recognized_capture_tracks = excluded.recognized_capture_tracks, updated_at = excluded.updated_at
```

Why these keys: they mirror `_encounter_key` / `_person_key` in today's `routers/dashboard.py`. A record without a track gets a per-kind key, so it never intersects across kinds. Faces and bodies use one track counter on the box, so `coalesce(face, body)` doesn't collide. Put this explanation in a comment above the SQL.

### 3.3 `counting/builder.py`

1. **Extend `_REBUILD`.** Replace the `e` CTE and the INSERT/UPDATE lists:

```sql
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
                           low_confidence_events, low_liveness_events, identity_score_sum, identity_score_count,
                           updated_at)
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
```
   In `rebuild_buckets`, add `"low_confidence": LOW_CONFIDENCE, "low_liveness": LOW_LIVENESS` to `params` (import from `dashboard_data.stats`). `_DROP_EMPTY` stays as it is (the kind counts are ≤ `events`).

2. **Call the daily recount at the end of `attach()`**, after `await rebuild_buckets(...)`:
   ```python
       # Dashboard day totals (distinct counts) for every local day these events fall on.
       await rebuild_days(session, box_id, {e.occurred_at.astimezone(batch.tz).date() for e in events})
   ```
   (`from dashboard_data.stats import rebuild_days`.) Check that this doesn't create an import cycle: `dashboard_data.stats` must import only `sqlalchemy`, `sqlmodel`, `datetime` and `counting.settings`. **Don't** import `counting.builder` or `counting` from it.

3. Update the `attach` docstring: "...then rebuild the 15-minute buckets those sightings touch and the dashboard's day totals (daily_stats)."

### 3.4 `alarms/ingest.py`: invalidate past dates after commit

In `poll_stream`, after the `async with sessions() as session: async with session.begin(): ...` block (that is, **after commit**), and before `return len(new_events)`:

```python
    await _forget_dashboard_days(new_events)
```

and add:

```python
async def _forget_dashboard_days(events: list[Event]) -> None:
    """Late records changed a past day's dashboard numbers: drop its cached copy (and the next day's,
    whose "vs yesterday" uses it). Today's copy expires within seconds on its own (D9)."""
    if not events or not cache.enabled():
        return
    tz = box_tz()
    today = datetime.now(timezone.utc).astimezone(tz).date()
    keys = []
    for day in {e.occurred_at.astimezone(tz).date() for e in events}:
        for d in (day, day + timedelta(days=1)):
            if d < today or (d == today and day < today):
                keys.append(cache.key("dash", "activity", d.isoformat(), "database"))
    await cache.delete(*keys)
```

(Imports: `import cache`, `from counting.settings import box_tz`. `timedelta` is already imported.) This is a no-op when Redis is off. Because `cache.delete` is fail-open, it can never break polling.

### 3.5 `dashboard_data/rebuild.py` (CLI for existing data)

Same structure as `counting/backfill.py`. Usage: `uv run python -m dashboard_data.rebuild [--since YYYY-MM-DD]`.

Algorithm:
1. Configure the engine like `counting/backfill._main` (`db.make_engine(db.DATABASE_URL, null_pool=True)`).
2. For each `box_id` in `boxes`: find `min(occurred_at)` and `max(occurred_at)` in `events` (or start at `--since`). Iterate box-local days from first to last. For **each day, in its own transaction**:
   - `start, end = local_day_range(day)`
   - Touched buckets = rows of
     `SELECT DISTINCT camera_id, date_bin('15 minutes', occurred_at, TIMESTAMPTZ '2000-01-01 00:00:00+00') FROM events WHERE box_id = :box_id AND occurred_at >= :start AND occurred_at < :end`
     ∪ existing `count_buckets` rows for that `local_date` whose camera belongs to the box (so emptied buckets get dropped).
   - `await rebuild_buckets(session, touched, tz)`, then `await rebuild_days(session, box_id, {day})`.
   - Print `"<day>: <n> buckets, daily stats rebuilt"` (flush=True).
3. At the end: `await cache.delete_prefix(cache.key("dash", ""))` (no-op without Redis).
4. It's idempotent and safe to re-run, and it can run while the backend polls (same reasoning as the backfill docstring). Say so in its docstring.

**Checkpoint 3:** `uv run pytest -q` is green, and with `TEST_DATABASE_URL` **all existing counting and alarm DB tests still pass** (`tests/test_counting_builder.py`, `tests/test_alarms_db.py`, `tests/test_counting_api.py`, `tests/test_faces.py`).

---

## Phase 4: Read side (`dashboard_data/box_source.py`, `dashboard_data/queries.py`)

### 4.1 `box_source.py`: move, don't rewrite

Move these from `routers/dashboard.py` **verbatim**: constants `MATCHED`, `STRANGER`, `MAX_ANALYSIS_RECORDS`, and the functions `_find`, `_record_time`, `_device_id`, `_person_name`, `_score`, `_history_body`, `_capture_body`, `_first_page`, `_collect_history`, `_device_health`, `_clock`, `_device_rows`, `_sample_metrics`, `_encounter_key`, `_person_key`, `_encounter_metrics`. Then add three public functions built only from the moved code:

```python
async def load_health() -> dict:
    """{"devices": [...rows...], "tasks_total": int, "clock": {...}}: the live part, from the box.
    Calls (in this order): device_config, device_state, task_list, get_system_time, get_time_info."""

async def load_activity(day: date, device_names: dict[str, str]) -> dict:
    """{"activity": {...}, "insights": {...}} for one box-local day: the original computation
    (today's three paged histories, then yesterday's three size-1 totals). Same fields and values
    as before this change."""

async def previous_totals(day: date) -> dict:
    """{"previous_matched", "previous_strangers", "previous_captures"} for `day`, from three size-1
    box calls. Used when the day before a database-served day isn't in the database."""
```

`load_activity` must produce exactly the `activity` and `insights` dicts the old route built (including `previous_*`), using `day.strftime("%Y-%m-%d 00:00:00")` / `"... 23:59:59"` as the old code did. Keep the box call order: current matched, current strangers, current captures, previous matched, previous strangers, previous captures.

### 4.2 `queries.py`

```python
async def coverage(session: AsyncSession) -> dict:
    """{"box_id": int | None, "start": "YYYY-MM-DD" | None}. box_id: the boxes row for B4H_BASE_URL
    (read-only lookup, never insert). start: the first box-local day served from the database
    = min(count_buckets.local_date) of this box's cameras + 1 day (the first ingested day is partial)."""

async def activity(session: AsyncSession, box_id: int, day: date, *, with_previous: bool,
                   now: datetime | None = None) -> dict:
    """{"activity": {...}, "insights": {...}, "ingest": {...} | None}: same fields as box_source.load_activity.
    previous_* are filled only when with_previous (else left out for the caller to fill)."""
```

Run the queries **sequentially** on the one session:

| # | Purpose | Query (SQLModel/SQLAlchemy, filtered to `Camera.box_id == box_id` via `JOIN cameras ON cameras.id = count_buckets.camera_id`) |
|---|---|---|
| Q1 | Per camera, day | `SELECT c.id, c.device_id, c.name, SUM(matched_events), SUM(stranger_events), SUM(face_capture_events), SUM(body_capture_events), SUM(low_confidence_events), SUM(low_liveness_events), SUM(identity_score_sum), SUM(identity_score_count) ... WHERE local_date = :day GROUP BY c.id, c.device_id, c.name` |
| Q2 | Hourly | `SELECT local_hour, SUM(matched_events + stranger_events) ... WHERE local_date = :day GROUP BY local_hour` |
| Q3 | Previous day (only if `with_previous`) | `SELECT SUM(matched_events), SUM(stranger_events), SUM(face_capture_events + body_capture_events) ... WHERE local_date = :day - 1` (coalesce to 0) |
| Q4 | Distincts | `session.get(DailyStat, (box_id, day))`; missing means all zeros |
| Q5 | Latest 8 | `SELECT events.alarm_id, kind, person_name, occurred_at, match_score, cameras.device_id, cameras.name FROM events JOIN cameras ... WHERE events.box_id = :box_id AND kind IN ('matched','stranger') AND occurred_at >= :start AND occurred_at < :end ORDER BY occurred_at DESC, events.id DESC LIMIT 8` |
| Q6 | Top people | `SELECT person_name, count(*) FROM events WHERE box_id = :box_id AND kind = 'matched' AND person_name IS NOT NULL AND btrim(person_name) <> '' AND occurred_at in range GROUP BY person_name ORDER BY count(*) DESC, person_name LIMIT 5` |
| Q7 | Ingest (only if `day == today`) | `SELECT min(last_success_at) FROM ingest_cursors WHERE box_id = :box_id` |

`start, end = stats.local_day_range(day)`. Use `EventKind.MATCHED.value` and the other enum values instead of string literals in SQLAlchemy expressions.

Build the result (must match the box-mode field names exactly):

```
activity = {
  "matched": Σ matched, "strangers": Σ stranger, "captures": Σ face_capture + Σ body_capture,
  "face_captures": Σ face_capture, "body_captures": Σ body_capture, "capture_breakdown_limited": False,
  ["previous_matched", "previous_strangers", "previous_captures"]  (from Q3 when with_previous)
}
hours = {h: n} from Q2
insights = {
  "peak_hour": hour with max count, earliest hour on ties; None if all counts are 0,
  "busiest_device_id": str(device_id) of the camera with max (matched+stranger) > 0, ties → lowest device_id; else None,
  "busiest_device": that camera's name; else None,
  "average_match_score": round(Σ score_sum / Σ score_count, 1) if Σ score_count else None,
  "low_confidence_count": Σ low_confidence, "low_liveness_count": Σ low_liveness,
  "top_people": [{"name", "count"}] from Q6,
  "hourly_activity": [{"hour": h, "count": hours.get(h, 0)} for h in range(24)],
  "events": [{"id": str(alarm_id), "type": kind ("matched"/"stranger"), "person": person_name or None,
              "device_id": str(device_id), "device": camera name,
              "time_ms": int(occurred_at.timestamp() * 1000),
              "score": round(match_score, 1) if match_score is not None else None}] from Q5,
  "tracked_encounters", "face_encounters", "body_encounters", "unique_recognized_people",
  "recognized_encounters", "stranger_encounters", "recognized_capture_tracks"  (from Q4),
  "recognition_coverage_percent": round(rct / face_encounters * 100, 1) if face_encounters else None,
  "busiest_capture_device": name of the camera with max (face_capture+body_capture) > 0 (ties → lowest device_id), else None,
  "analysis_sampled": matched + strangers + captures,
  "analysis_limited": False,
}
ingest = {"last_success_at": iso string or None, "lag_seconds": int or None} if day == today else None
```

`now` defaults to `datetime.now(timezone.utc)`; tests pass it explicitly.

**Checkpoint 4:** `uv run pytest -q` is green (the route isn't switched yet, so nothing visible changes). Import check: `uv run python -c "import dashboard_data.queries, dashboard_data.box_source, dashboard_data.rebuild"`.

---

## Phase 5: The route (`routers/dashboard.py`)

Replace the module with a thin orchestrator. Docstring: "Operational dashboard: live camera health from the box, activity from our database (pre-computed counts) or, for days the database doesn't cover, from the box; every part through the Redis cache."

```python
SOURCE = os.getenv("DASHBOARD_SOURCE", "auto")              # auto | database | box
HEALTH_TTL = float(os.getenv("DASHBOARD_HEALTH_CACHE_SECONDS", "15"))
TODAY_TTL = float(os.getenv("DASHBOARD_TODAY_CACHE_SECONDS", "15"))
PAST_TTL = float(os.getenv("DASHBOARD_PAST_CACHE_SECONDS", "3600"))
INGEST_LAG = int(os.getenv("DASHBOARD_INGEST_LAG_SECONDS", "120"))
COVERAGE_TTL = 300
```

Route logic, in this exact order:

1. **Validate `date` first** (unchanged error: `422 "date must use YYYY-MM-DD"`). No Redis, DB or box access before this. Default day = box-local today: `datetime.now(BOX_TZ) if BOX_TZ is not None else datetime.now()`, as today's code does. Keep `day` as a `date`; `today` is computed the same way.
2. **Health:** `health, health_state = await cache.get_or_load(cache.key("dash","health"), HEALTH_TTL, box_source.load_health, fresh=fresh)`.
3. **Coverage** (`None` when `SOURCE == "box"` or `not db.enabled()`):
   `coverage, _ = await cache.get_or_load(cache.key("dash","coverage"), COVERAGE_TTL, _load_coverage)`, where `_load_coverage` opens `async with db.sessions()() as session:` and calls `queries.coverage(session)`. Wrap it in `try/except (DBAPIError, OSError, asyncio.TimeoutError, HTTPException)`. On failure in auto mode, log a warning, set `coverage = None` and `fallback_reason = "database unavailable"`. In `database` mode, re-raise (main.py turns it into 503).
4. **Choose the source:**
   - `"box"` if `coverage is None` or `coverage["box_id"] is None`
   - else `"database"` if `SOURCE == "database"`
   - else `"database"` if `coverage["start"]` and `day >= date.fromisoformat(coverage["start"])`
   - else `"box"`.
5. **Activity:** `ttl = TODAY_TTL if day >= today else PAST_TTL`, then `activity, activity_state = await cache.get_or_load(cache.key("dash","activity", day.isoformat(), source), ttl, loader, fresh=fresh)`, where:
   - database loader: in one session, `with_previous = coverage start ≤ day − 1` (or `SOURCE == "database"`). Call `queries.activity(...)`. If not `with_previous`, fill `previous_*` with `await box_source.previous_totals(day - timedelta(days=1))`.
   - box loader: `box_source.load_activity(day, {str(r["id"]): r["name"] for r in health["devices"]})`.
   - In auto mode, if the database loader raises one of the DB errors above, log a warning, set `fallback_reason`, switch `source = "box"` and repeat step 5 with the box loader.
6. **Compose** (not cached):
   ```python
   rows = health["devices"]; online = [r for r in rows if r["online"]]
   attention = <the same three comprehensions as today> + clock_unavailable (same as today)
   if source == "database" and activity.get("ingest") and lag > INGEST_LAG: attention.append(ingest_lagging item)
   return {
     "date": day.isoformat(),
     "generated_at": datetime.now().isoformat(timespec="seconds"),
     "period": {"start": f"{day} 00:00:00", "end": f"{day} 23:59:59",
                "previous_start": f"{prev} 00:00:00", "previous_end": f"{prev} 23:59:59"},
     "health": {"devices_total": len(rows), "devices_online": len(online), "devices_offline": len(rows) - len(online),
                "streams_pulling": sum(r["pulling_stream"] for r in rows), "tasks_total": health["tasks_total"],
                "clock": health["clock"]},
     "activity": activity["activity"], "insights": activity["insights"],
     "devices": rows, "attention": attention,
     "meta": {"source": source, "fallback_reason": fallback_reason,
              "coverage_start": coverage["start"] if coverage else None,
              "cache": {"health": health_state, "activity": activity_state},
              "ingest_last_success_at": (activity.get("ingest") or {}).get("last_success_at")},
   }
   ```
   The `ingest_lagging` message is `f"Dashboard numbers may be behind: box records were last read {lag // 60} min ago"`. Compute `lag` from `last_success_at` against **now** at compose time, so a cached activity part doesn't hide a growing lag.
7. Signature: `async def dashboard_summary(date: str | None = Query(None, description="Box-local date: YYYY-MM-DD"), fresh: bool = Query(False, description="Skip the cache (the Refresh button)"))`.

**Checkpoint 5:** the two existing `tests/test_dashboard.py` tests pass **unchanged**. That proves the box path (no DB, no Redis) is identical.

---

## Phase 6: Other invalidation hooks

- `routers/devices.py`: at the end of the successful POST `/api/devices`, PUT `/api/devices/{device_id}` and DELETE `/api/devices/{device_id}` handlers, call `await cache.delete(cache.key("dash", "health"))`.
- Nothing else. Camera names in the database activity part refresh within their TTL; incidents don't feed the dashboard.

**Checkpoint 6:** `uv run pytest -q tests/test_devices.py` is green.

---

## Phase 7: Frontend (small)

1. `client/src/lib/dashboard.ts`:
   - Add to `DashboardSummary`:
     ```ts
     meta?: {
       source: 'database' | 'box';
       fallback_reason?: string | null;
       coverage_start?: string | null;
       cache?: { health: string; activity: string };
       ingest_last_success_at?: string | null;
     };
     ```
   - Change the signature to `fetchDashboardSummary(date?: string, options: { fresh?: boolean } = {})` and build the query with `URLSearchParams` (`date` if given, `fresh=1` if `options.fresh`). Everything else stays the same.
2. `client/src/components/dashboard/DashboardView.tsx`:
   - Change `load` to `load(initial = false, fresh = false)` and call `fetchDashboardSummary(undefined, { fresh })`. The Refresh button calls `load(false, true)`; the interval and the first load stay non-fresh.
   - In the top status bar, after `refreshes every 45 seconds`, show ` · from {data.meta.source === 'database' ? 'portal database' : 'box'}` only when `data.meta` exists. No other UI changes.
3. Optional: add a `meta` object to `sampleDashboard` in `client/src/mocks/handlers.ts`.
4. Run `cd client && npm test` (vitest), and fix `DashboardView.test.tsx` only where it asserts the exact fetch URL or arguments.

**Checkpoint 7:** client tests pass; `npm run build` succeeds (or `npx tsc --noEmit`).

---

## Phase 8: Tests

### 8.1 `tests/test_dashboard.py` (no DB; add these, keep the existing two)

Use the existing `CONFIG/STATE/TASKS/SYSTEM_TIME/CURRENT_TIME/HISTORY` replies (factor the reply setup into a helper `_box_replies(fake_box)` used by the new tests; **don't** edit the two existing tests).

1. `test_meta_says_box_without_a_database`: `meta.source == "box"`, `meta.cache == {"health": "off", "activity": "off"}`.
2. `test_second_request_is_served_from_redis(client, fake_box, redis_cache)`: first call → `"miss"`/`"miss"`; record `n = len(fake_box.calls)`; second call → `"hit"`/`"hit"`, `len(fake_box.calls) == n`, and the body equals the first apart from `generated_at` and `meta.cache`.
3. `test_fresh_skips_the_cache`: after one call, `?fresh=1` → `"bypass"` and new box calls were made.
4. `test_redis_down_still_answers`: `redis_cache.fail = True` → 200, same numbers as the first test.
5. `test_bad_date_touches_nothing(client, fake_box, redis_cache)`: 422, `fake_box.calls == []`, `redis_cache.calls == []`.
6. `test_device_change_forgets_health`: prime the cache, call `DELETE /api/devices/{id}` with the replies `tests/test_devices.py` uses for deletes, and check the health key is gone (`redis_cache` dict).

### 8.2 `tests/test_dashboard_db.py` (new; skipped without `TEST_DATABASE_URL`)

Reuse `record`, `save` from `tests/test_counting_builder.py` and `BoxHistory`, `setup_box` from `tests/test_alarms_db.py` (import them the way `test_counting_builder.py` does). Use dates relative to a fixed `NOW` and pass `now=` where the API allows. For the route tests, monkeypatch the router's "today" (put the `today` computation in a small function `_today()` in the router so tests can patch it).

1. **Buckets carry per-kind numbers:** save 2 matched (scores 95 and 60, liveness 90 and 70), 1 stranger (score 50), 2 face captures, 1 body capture in one 15-min window → that `count_buckets` row has matched 2, stranger 1, face_capture 2, body_capture 1, low_confidence 2, low_liveness 1, score_sum 205, score_count 3.
2. **daily_stats mirrors the old encounter semantics:** build the same scenario as `test_dashboard_aggregates_health_activity_and_attention` (3 matched on tracks 1–3 of one person, 2 strangers, 4 face captures on tracks 1–4, same camera) → `tracked 4, face 4, body 0, recognized 3, stranger 2, recognized_capture_tracks 3, unique_recognized_people 1`.
3. **Late record recount:** saving one more record for an earlier day updates that day's `daily_stats` and bucket.
4. **Merge doesn't change daily_stats:** body then face of one person in two separate `save` calls → `daily_stats` is the same as when both are saved in one call.
5. **Rebuild CLI equals incremental:** after a scenario, snapshot buckets + daily_stats; zero the new columns (`UPDATE count_buckets SET matched_events = 0, ...`) and `DELETE FROM daily_stats`; run `dashboard_data.rebuild.run(...)` (expose a `run(sessions, since=None, quiet=True)` like the backfill); the snapshot is equal again.
6. **Route serves the DB for a covered day with zero history calls:** seed one event on D−2 and events on D−1 and D. Configure the health replies only (**no `HISTORY` reply**; an unexpected box call fails the test) → 200, `meta.source == "database"`, activity, insights and previous totals match the seeded data.
7. **Uncovered day falls back to the box:** request D−3 → `meta.source == "box"` and `alarm_history` was called.
8. **Previous day not covered:** coverage starts at D → `previous_*` come from three size-1 history calls, everything else from the DB.
9. **Forced box:** monkeypatch `routers.dashboard.SOURCE = "box"` → box path even for D.
10. **Ingest lag:** set the cursors' `last_success_at` to 10 min before `NOW` → an `ingest_lagging` attention item is present.
11. **Past-day invalidation (with `redis_cache`):** prime `dash:activity:<D-1>:database`, then run one `ingest.poll_stream` (via `BoxHistory`, as in the counting builder's end-to-end tests) that returns a record dated D−1 → the key is deleted. A record dated today doesn't delete today's key.
12. **DB down falls back to the box (auto mode):** monkeypatch `queries.activity` to raise `DBAPIError(None, None, Exception("x"))` → 200, `meta.source == "box"`, `meta.fallback_reason` set.

### 8.3 Optional real-Redis smoke test

If `TEST_REDIS_URL` is set, one test runs `cache.configure(redis.asyncio.Redis.from_url(TEST_REDIS_URL, decode_responses=True))`, sets and gets a key, and deletes by prefix. Skip it otherwise.

**Checkpoint 8:** `uv run pytest -q` is green, both without and with `TEST_DATABASE_URL`.

---

## Phase 9: Documentation

1. `fastapi-app/README.md`:
   - Env table: the 7 new variables (3.6).
   - New section "Cache (Redis, optional)": what's cached, TTLs, fail-open behavior, and how to run Redis locally (`docker run -d --name b4h-redis -p 6379:6379 redis:7-alpine`, or Memurai / WSL on Windows).
   - Setup: after `alembic upgrade head`, run `uv run python -m dashboard_data.rebuild` once to fill the new counts for existing data.
   - Project structure: `cache.py`, `dashboard_data/`.
   - Testing table: `test_cache.py`, `test_dashboard_db.py`.
   - Troubleshooting rows: "Redis unavailable; caching paused" warning; "Dashboard says *from box* although the database is set" (the date is before coverage start, or `DASHBOARD_SOURCE=box`).
2. `docs/backend-api.md` §4.1: the `fresh` parameter, `meta`, the `ingest_lagging` attention type, the semantic-differences table (3.3), the new "Box calls" text (database source: 5 health calls only, cached 15 s), and replace the "Performance" note.
3. `docs/architecture.md`: change the Dashboard row in the page → API → box-calls table to "box: device_config, device_state, task_list, get_system_time, get_time_info (cached 15 s); database: count_buckets, daily_stats, events (box alarm_history only for days before the database's coverage)". Add a short paragraph on the Redis cache.

**Checkpoint 9:** docs mention every new env var, file and response field; there are no references to removed behavior.

---

## Phase 10: Rollout and verification

1. `uv run alembic upgrade head` on the real DB.
2. `uv run python -m dashboard_data.rebuild` (once; it's safe to re-run).
3. Start Redis; set `REDIS_URL` in `.env`; restart the backend (one process; **no `--workers`**).
4. Check: the startup log shows a Redis OK line. `GET /api/dashboard/summary` (×3) → first `meta.cache.activity == "miss"`, then `"hit"`; `meta.source == "database"` for today (once coverage exists).
5. Time it like the Phase 0 baseline and compare against the targets in §2. Report the numbers to the user.
6. Check the write cost: with the `b4h` log at INFO, poll cycles must not slow down noticeably. If you have DB access, run `EXPLAIN ANALYZE` on the `_REBUILD_DAY` query for today; it should use `ix_events_box_time`. **If its p95 is above 250 ms on real data**, report that to the user instead of optimizing on your own (a possible follow-up is throttling `rebuild_days` for today to once per 30 s).
7. Cross-check numbers: for one fully covered past day, compare `?date=<day>` with `DASHBOARD_SOURCE=box` and then with `auto` (after a `fresh=1`). `matched`, `strangers` and the encounter numbers should match. `captures` may be higher in box mode (structure records, see 3.3).

**Rollback:** set `DASHBOARD_SOURCE=box` (box behavior, still cached) and/or empty `REDIS_URL` (no cache). The schema change is additive. `alembic downgrade -1` removes it if needed.

---

## Appendix A: Pitfalls checklist

- [ ] `health` dict keeps exactly 6 keys; new things only in `meta`.
- [ ] 422 for a bad date before any Redis, DB or box access.
- [ ] Cached values are JSON-native; `get_or_load` normalizes so hit and miss bodies are identical.
- [ ] Invalidation runs after commit, never inside the ingest transaction.
- [ ] No `KEYS` command; `SCAN` only.
- [ ] No `asyncio.gather` over box calls or over one DB session.
- [ ] Local day boundaries come from `stats.local_day_range` (DST-safe), never from `+ timedelta(hours=24)` on a UTC time.
- [ ] `count_buckets` filtered by `local_date`, joined to `cameras` for `box_id`; deleted cameras are **included** (history).
- [ ] `dashboard_data.stats` imports nothing from `counting` except `counting.settings` (no import cycle).
- [ ] New NOT NULL columns have `server_default='0'` in the migration; the index is created concurrently in an autocommit block.
- [ ] `conftest.py` turns caching off by default; the existing tests didn't need edits.
- [ ] `test_main.py`'s route list still passes (no route added or removed).

## Appendix B: Commands

```bash
cd fastapi-app
uv add "redis>=5.0"
uv run alembic revision --autogenerate -m "dashboard stats"   # then review/trim (Phase 2.5)
uv run alembic upgrade head && uv run alembic check
uv run python -m dashboard_data.rebuild [--since YYYY-MM-DD]
uv run pytest -q
TEST_DATABASE_URL=postgresql://postgres@localhost:5432/b4h_test uv run pytest -q   # PowerShell: $env:TEST_DATABASE_URL="..."
cd ../client && npm test && npx tsc --noEmit
```
