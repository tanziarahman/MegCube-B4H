# B4H Portal: Backend

FastAPI service that sits between the web portal (`../client`) and the MegCube B4H analytics box. It:

- logs in to the box and keeps the session alive, without ever risking an account lockout,
- exposes simple `/api/*` endpoints for the frontend, protected by an API key,
- strips camera passwords before anything reaches the browser,
- proxies box images and converts camera RTSP streams to MJPEG for the Live view.

```
Browser  →  Next.js (localhost:3000)  →  /api/* + X-API-Key  →  FastAPI (localhost:8000)  →  B4H box (HTTPS)
```

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Network access to the box (default `https://192.168.90.200`)
- **ffmpeg**, only needed for the Live view (`winget install ffmpeg` on Windows, then open a new terminal)

## Setup and run

```bash
cd fastapi-app
uv sync                          # creates .venv, installs dependencies (incl. pytest)
# create .env (see below)
uv run uvicorn main:app --reload # http://localhost:8000
```

Without uv:

```bash
python -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install "fastapi[standard]" httpx python-dotenv python-multipart tzdata pytest
uvicorn main:app --reload
```

Interactive API docs are generated automatically at **http://localhost:8000/docs**.

If the box is offline at startup, the server still starts and logs in on the first request. If the box **refuses the username or password**, the server logs an error and makes **no further login attempts until it is restarted**. This protects the box account from the 5-wrong-passwords lock.

## Environment variables

Create `fastapi-app/.env`. It is git-ignored, so never commit it.

```env
B4H_BASE_URL=https://192.168.90.200
B4H_USER=admin
B4H_PASS=your-box-password
API_KEY=a-long-random-string        # same value as BACKEND_API_KEY in client/.env.local
BOX_TIMEZONE=Asia/Dhaka
# FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe

# Alarms (optional; see "Database and alarms" below)
# DATABASE_URL=postgresql://user:password@ep-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
# DATABASE_URL_DIRECT=postgresql://user:password@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
# SMTP_HOST=smtp.gmail.com
# SMTP_USER=alarms@yourdomain.com
# SMTP_PASSWORD=app-password
# SMTP_FROM=alarms@yourdomain.com
# PORTAL_URL=http://192.168.90.10:3000
```

| Variable | Default | Purpose |
|---|---|---|
| `B4H_BASE_URL` | `https://192.168.90.200` | Box address |
| `B4H_USER` | `admin` | Box login user |
| `B4H_PASS` | (empty; set it) | Box login password |
| `B4H_TIMEOUT` | `15` | Seconds to wait for a box reply before answering `504` |
| `API_KEY` | (empty) | When set, every `/api` request needs header `X-API-Key: <key>`. **When empty, the API is open to anyone who can reach it** (a warning is logged). |
| `BOX_TIMEZONE` | `Asia/Dhaka` | Time zone the portal's date filters are in. Needs the `tzdata` package on Windows. |
| `RECOG_MAJOR` | `face_basic_business` | Alarm major type that recognition and capture records are stored under |
| `PEOPLE_CACHE_SECONDS` | `60` | How long `/api/people` (the whole face library) is cached; cleared on any add, edit or delete |
| `MAX_PHOTO_MB` | `5` | Largest face photo accepted (`413` above it) |
| `FFMPEG_PATH` | `ffmpeg` | Path to ffmpeg for the Live view |
| `MAX_STREAMS` | `16` | Most live videos running at once (`503` above it) |
| `DATABASE_URL` | (empty = alarms off) | PostgreSQL (Neon) connection string, pooled host. Without it the portal works as before and `/api/alarms/*` answers `503`. |
| `DATABASE_URL_DIRECT` | (DATABASE_URL) | Neon's direct (non-pooler) host, used by Alembic migrations |
| `SMTP_HOST` / `SMTP_PORT` | (empty) / `587` (`465` with ssl) | Email server for alarm emails. Without `SMTP_HOST` and `SMTP_FROM`, alarms are recorded and their emails wait in the queue. |
| `SMTP_USER` / `SMTP_PASSWORD` | (empty) | SMTP login (for Gmail: an app password) |
| `SMTP_FROM` / `SMTP_FROM_NAME` | `SMTP_USER` / `B4H Portal` | Sender address and name |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` or `none` |
| `PORTAL_URL` | `http://localhost:3000` | Portal address used in the links inside alarm emails. Set it to an address the recipients can open. |
| `ALARM_POLL_SECONDS` | `5` | How often new detections are read from the box |
| `ALARM_POLL_OVERLAP_SECONDS` | `60` | Each poll re-reads this much of the previous window, so records the box saves late aren't missed. Raise it if the box clock runs behind this PC. |
| `ALARM_MAX_RECIPIENTS` | `5` | Most email recipients per rule |
| `ALARM_WORKERS` | `1` | `0` turns polling and emails off in this process (e.g. a second instance) |
| `COUNT_PAIR_MAX_SECONDS` | `120` | People counting: a face track and its body track (face id − 1) are one walk-past when their first records are at most this far apart |
| `COUNT_VISIT_GAP_SECONDS` | `120` | People counting: the same identified person on the same camera again within this gap is still one visit |
| `FACE_MATCHING` | `1` | `0` turns face and body fingerprints off (different people is then the same as walk-pasts) |
| `FACE_MODEL_DIR` | `fastapi-app/face_models` | Where the three model files are (`uv run python -m faces.download`) |
| `PEOPLE_MATCH_THRESHOLD` / `PEOPLE_MATCH_RANGE` | `0.35` / `0.05` | How alike two walk-pasts must be (on average, group against group) to be one person; the shown range uses ± `PEOPLE_MATCH_RANGE`. Applies at once (grouping happens per request) |
| `PEOPLE_BODY_WEIGHT` | `0.6` | Share of the body (clothing) similarity when both a face and a body can be compared |
| `FACE_MIN_DETECTION_SCORE` / `FACE_MIN_PIXELS` / `BODY_MIN_PIXELS` | `0.85` / `40` / `64` | Faces less certain or smaller, and body pictures shorter, than this get no fingerprint |
| `FACE_PER_CYCLE` / `PEOPLE_MAX_GROUPING` | `40` / `2000` | Walk-pasts fingerprinted per poll cycle; most walk-pasts grouped for one request |

Generate an API key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Access control (API key)

- With `API_KEY` set, all `/api/*` routes need `X-API-Key: <API_KEY>`. The key is checked in `core.check_access`, wired to every router in `main.py`. A missing or wrong key returns `401`. The key is **not** accepted as a URL parameter.
- The Next.js server adds the header (`client/src/middleware.ts` with `BACKEND_API_KEY`), so the browser never sees the key.
- **Live video** is loaded by an `<img>` tag, which can't send headers. `/api/preview/cameras` therefore returns a `stream_token` for each camera (`exp=…&sig=…`, an HMAC of camera id and expiry, valid for 12 hours). It only opens **that camera's** stream, and stops working if `API_KEY` changes.
- `GET /` stays open as a health check. FastAPI's own `/docs` and `/openapi.json` are also open (they aren't under `/api`).
- The portal's sign-in page is a demo and doesn't protect anything; see [Architecture → Security model](../docs/architecture.md#4-security-model).

## Database and alarms

Alarms are the portal's own feature: the box's licensed alarm algorithms aren't needed. The backend reads every detection from the box, checks it against rules you set (camera, who, time window) and emails up to 5 recipients.

**Set up (once):**

1. Create a project on [Neon](https://neon.tech) in the region nearest the box (for Dhaka: Singapore). Copy the **pooled** connection string into `DATABASE_URL` and the **direct** one into `DATABASE_URL_DIRECT`.
2. Create the tables: `uv run alembic upgrade head`
3. Set the `SMTP_*` variables and `PORTAL_URL`, then restart the backend.
4. On the **Alarms** page: add recipients, send a test email, create a rule.

**How it works:**

```
box alarm_history --poll every 5 s--> events --> rules --> incidents --> notifications --> SMTP
```

- `alarms/ingest.py` reads the recognition and capture records of the last few seconds (re-reading a 60 s overlap) and saves them in `events`. A record is saved once (unique `box_id, kind, alarm_id`), so re-reading is harmless.
- Only new events go to `alarms/engine.py`, **in the same transaction**: a crash never leaves an event without its alarm, and a replay never alarms twice.
- A rule fires once per camera per quiet period (cooldown). Detections during the quiet period join the open alarm (`event_count`) instead of sending more email.
- Times are checked in the rule's time zone (default `BOX_TIMEZONE`); a window ending before it starts (22:00 to 06:00) runs past midnight.
- Records that arrive late (the portal was offline and is catching up) become alarms marked **delayed** and aren't emailed unless the rule says so. The first start only looks back 5 minutes.
- `alarms/mailer.py` sends one email per recipient, with the snapshot attached, and retries failures (30 s, 1 min, 2 min…, 5 tries).
- The pollers run inside the backend process: run **one** backend process (no `--workers N`).

**People counting** uses the same events. In the same transaction, before the rules, `counting/builder.py` puts each new event into a **sighting** (one person passing one camera once): the box's repeated records of a track collapse into one, and face track `F` + body track `F − 1` on the same camera are merged (the box numbers them from one counter). The 15-minute totals in `count_buckets` are recounted from `sightings` after every batch, so they can't drift. Counting queries are in `counting/queries.py`, the routes in `routers/counting.py`.

**Different people by face and clothing.** The box sends no identities, so the backend tells people apart itself. After each poll, `faces/worker.py` downloads the face and body pictures of each new walk-past from the box and computes two fingerprints with OpenCV: SFace for the face (`sightings.face_embedding`), YouTu ReID for the whole body, mostly clothing (`sightings.body_embedding`). It runs outside the alarm transaction, oldest first (the box rotates old pictures out); a picture with nothing usable is marked and not retried. For each request, `faces/grouping.py` groups the walk-pasts of the chosen period by average similarity (60 % body, 40 % face; bodies only within one day; two walk-pasts on camera together are never one person) and returns a range of people. One-time setup: `uv run python -m faces.download` (three files, ~146 MB, checked by SHA-256, into `face_models/`, which git ignores).

Calibrated on this box's pictures on 2026-10-04 (checked by eye: about 6 people in 70 walk-pasts): faces alone gave 25 people, because ceiling-camera faces are small, tilted and often half-covered; body + face gives 7 (likely 6–10).

Events saved before people counting existed have no sighting. Build them once (safe to re-run; it skips events that already have one):

```bash
uv run python -m counting.backfill                     # everything
uv run python -m counting.backfill --since 2026-10-01  # only from this box-local day
```

**Schema changes:** edit `models/`, then `uv run alembic revision --autogenerate -m "what changed"`, review the file in `migrations/versions/`, and `uv run alembic upgrade head`. `uv run alembic check` tells you if the models and migrations differ.

## Project structure

```
fastapi-app/
├─ main.py            # app entry: lifespan (login/close), error handlers, access check, router wiring
├─ core.py            # box client, config from .env, time-zone handling, people cache, API-key check
├─ b4h.py             # B4HClient: login (lockout-safe), session renewal, call/upload/get_bytes
├─ db.py              # database connection (Neon URL handling, sessions)
├─ models/            # database tables (SQLModel): reference, ingest, counting, alarms, admin
├─ alarms/            # box records -> events -> rules -> incidents -> emails (+ background workers)
├─ counting/          # people counting: events -> sightings + 15-minute buckets, queries, backfill
├─ faces/             # face and body fingerprints (OpenCV) and grouping them into different people
├─ face_models/       # the three model files (not in git; uv run python -m faces.download)
├─ migrations/        # Alembic migrations (alembic.ini at the top)
├─ routers/
│  ├─ alarms.py       # Alarms page: rules, recipients, incidents, status, test email
│  ├─ counting.py     # People counting page: totals, series, busy times, sightings, camera settings
│  ├─ devices.py      # Devices page: camera list + status, add, edit, delete
│  ├─ preview.py      # Live view: camera list, RTSP → MJPEG stream (ffmpeg)
│  ├─ recognition.py  # Recognition records, face-library person list
│  ├─ capture.py      # Face/body capture records
│  ├─ personnel.py    # Face library: groups, add/edit/delete people
│  ├─ timeplan.py     # Time plans: box clock, regular/festival schedule plans
│  ├─ dashboard.py    # Dashboard: one summary of today's activity and camera health
│  └─ common.py       # Camera names, image proxy
└─ tests/             # pytest suite (fake box) + live_check.py (real box)
```

## API endpoints

The full reference (parameters, response shapes, errors, and the box calls behind each route) is in **[docs/backend-api.md](../docs/backend-api.md)**. Swagger UI is at `http://localhost:8000/docs` while the server runs.

| Router | Routes |
|---|---|
| `dashboard.py` | `GET /api/dashboard/summary` |
| `devices.py` | `GET /api/devices/detail`, `POST /api/devices`, `PUT /api/devices/{id}`, `DELETE /api/devices/{id}` |
| `common.py` | `GET /api/devices` (id + name), `GET /api/image` |
| `preview.py` | `GET /api/preview/cameras`, `GET /api/preview/{id}/stream` |
| `recognition.py` | `GET /api/recognition`, `DELETE /api/recognition/{alarm_id}`, `GET /api/people` |
| `capture.py` | `GET /api/capture` |
| `personnel.py` | `GET /api/personnel/groups`, `GET/POST /api/personnel`, `PUT/DELETE /api/personnel/{id}` |
| `counting.py` | `GET /api/counting/summary`, `GET /api/counting/series`, `GET /api/counting/heatmap`, `GET /api/counting/sightings`, `GET /api/counting/cameras`, `PATCH /api/counting/cameras/{id}` |
| `alarms.py` | `GET /api/alarms/status`, `GET /api/alarms/cameras`, `GET/POST /api/alarms/contacts`, `PUT/DELETE /api/alarms/contacts/{id}`, `POST /api/alarms/test-email`, `GET/POST /api/alarms/rules`, `GET/PUT/DELETE /api/alarms/rules/{id}`, `PATCH /api/alarms/rules/{id}/enabled`, `GET /api/alarms/incidents`, `GET /api/alarms/incidents/{id or public id}`, `PATCH /api/alarms/incidents/{id}` |
| `timeplan.py` | `GET /api/timeplans/time`, `GET /api/timeplans/regular`, `GET /api/timeplans/festival`, `POST /api/timeplans`, `PUT/DELETE /api/timeplans/{plan_id}`, `DELETE /api/timeplans/stream-subscriptions` |

The box endpoints these call are in [docs/box-api.md](../docs/box-api.md).

## How the box connection works (`b4h.py`)

All box traffic goes through one `B4HClient`. In short:

- **Login** is challenge–response (`GET /auth/login/challenge`, then `POST /auth/login` with `sha256(password + salt + challenge)`); the session travels as `Cookie: sessionID=…`.
- **Expired session** (code `512`, after ~30 s idle): log in again and retry **once**; simultaneous requests share one re-login.
- **One call at a time**: the box can't handle parallel queries, so calls are serialised with a lock.
- **Lockout protection**: after the box refuses the credentials, no further login is attempted until restart.
- `box.call(method, path, body)` returns the box's `data` or raises `B4HError`; `box.upload(...)` sends multipart; `box.get_bytes(...)` downloads images.

`main.py` maps errors to HTTP statuses: `B4HError` → `502`, box unreachable → `503`, box too slow → `504`. Routes raise `401`, `404`, `409`, `413`, `415`, `422` and `501` themselves. Details: [Architecture §5](../docs/architecture.md#5-talking-to-the-box) and [Backend API §13](../docs/backend-api.md#13-errors).

## Testing

### Automated tests (pytest, no box needed)

```bash
cd fastapi-app
uv sync                 # installs pytest (dev dependency group)
uv run pytest           # about 400 tests, under a minute
uv run pytest -v tests/test_devices.py        # one file
uv run pytest -k "password"                  # tests whose name matches
```

- `tests/conftest.py` swaps the box connection for a **`FakeBox`**. Each test fills in `fake_box.replies[(METHOD, path)]` with data, an exception, or a function. The fake **records every request** the backend sent, so tests check both the API response and the exact box payload (`fake_box.sent("PUT", "/device_access/device_config")`).
- An unexpected box call fails the test, so a route can't silently hit an endpoint nobody planned for.
- The API-key check is off in tests by default. `test_access.py` turns it on.
- Sample box data in `conftest.py` (`DEVICE_CONFIG`, `DEVICE_STATE`, `TASK_LIST`) is copied from real responses.
- **Alarm and counting database tests** need a real PostgreSQL: set `TEST_DATABASE_URL` to an **empty, throwaway** database (its tables are dropped and recreated), e.g. a local Postgres or a Neon branch. Without it they are skipped.

  ```bash
  TEST_DATABASE_URL=postgresql://postgres@localhost:5432/b4h_test uv run pytest
  # PowerShell: $env:TEST_DATABASE_URL="postgresql://..."; uv run pytest
  ```

| Test file | Covers |
|---|---|
| `test_b4h_client.py` | Hashed login, lockout protection, session expiry and one retry, serialised calls, shared re-login, unreachable box |
| `test_access.py` | API key on every route, wrong/missing key, signed stream links (other camera, expired, tampered, old key) |
| `test_core.py` | Box time zone vs server time zone, missing tz data |
| `test_main.py` | Starts with the box offline, unknown route, unexpected error → 500, all routes registered |
| `test_devices.py` | Password masking, detail list, add (lowest free id, duplicate names, bad input, concurrent adds), delete |
| `test_preview.py` | Camera list, ffmpeg start/stop, sub vs main stream, stream limit, missing ffmpeg, bad params |
| `test_recognition.py` | Box payload, paging, validation, empty pages, 502/503/504 mapping, delete, `/api/people` paging and cache |
| `test_dashboard.py` | Summary totals, people-flow counts, attention items (offline camera, stream not pulling), bad date refused before any box call |
| `test_capture.py` | Target-type mapping, record flattening, missing fields, paging, errors |
| `test_personnel.py` | Groups, list, add/edit/delete, Bangla names, photo size limit, group-binding failure |
| `test_common.py` | Image proxy: path whitelist, content types, fallbacks, session expiry, 404s |
| `test_models.py` | Every table compiles to PostgreSQL; key unique constraints and indexes |
| `test_alarm_rules.py` | Box record → event, overnight time windows, rule matching (who, camera, score, liveness, time zone), email content, retry gaps |
| `test_alarms_db.py` | (needs `TEST_DATABASE_URL`) poll → events → alarm → queued emails, no duplicates on re-poll, cooldown grouping, per-track alarms, late events, box errors, email sending and retries, all `/api/alarms` routes |
| `test_counting_builder.py` | (needs `TEST_DATABASE_URL`) face + body pairing in one batch, across polls, in either order and across midnight; merging two halves; the 2-minute limit; many records of one track; other cameras; recognitions and strangers; re-polls change nothing; bucket recounts; backfill; alarms still fire |
| `test_faces.py` | Grouping: body + face weighing, clothes only within a day, people seen together never merged, the range, the too-many limit; real models refuse unusable pictures (skipped without the models); (needs `TEST_DATABASE_URL`) one fingerprint per walk-past, no retries, missing pictures, merges keep the fingerprint, a face failure doesn't stop polling, the summary's estimate per period and camera |
| `test_counting_api.py` | (most need `TEST_DATABASE_URL`) totals, visits and different people; hours (incl. past midnight), weekday and camera filters; counting basis; zero-filled series; heatmap averages; sightings list; camera settings + audit; `422` for bad input; `503` without a database |
| `test_timeplan.py` | Box clock and its fallback, plan list/create/update/delete payloads, id mismatch refused, stream-subscription route not shadowed by `{plan_id}` |

**Not covered yet:** `PUT /api/devices/{id}` (device edit) has no tests. Add them next.

**Adding a test:** use the `client` and `fake_box` fixtures, set the replies your route needs, call the route, then assert on the response **and** on `fake_box.calls`.

### Live check against the real box (read-only)

`tests/live_check.py` calls the running backend against the **real box** and reports PASS or FAIL for about 25 checks. It covers every read endpoint, image loading, one live video frame, bad input being refused, passwords never appearing in responses, and the API key (if set). **It changes nothing on the box.** It isn't collected by pytest.

```bash
uv run uvicorn main:app --port 8001          # terminal 1
uv run python tests/live_check.py            # terminal 2 (default http://localhost:8001)
uv run python tests/live_check.py http://localhost:8000   # another address
```

It reads `API_KEY` from `.env`. Run it after box firmware changes, or before a release.

## Adding an endpoint for a new box feature

1. Use the feature in the box's own web UI with DevTools → Network open ("Preserve log" on).
2. Copy the request method, path, payload and response, and add them to [`../docs/box-api.md`](../docs/box-api.md).
3. Add a route in the matching `routers/*.py` that calls `box.call(METHOD, "/box/path", payload)`. `call()` returns `data` or raises `B4HError`. New router files must be added to the list in `main.py` so they get the API-key check.
4. Validate input with a Pydantic model, and never return passwords (see `_mask_url` in `devices.py`).
5. Add tests with `fake_box` that assert the exact payload sent to the box.
6. Document the route in [`../docs/backend-api.md`](../docs/backend-api.md): parameters, response example, errors, box calls.
7. Add a client function in `client/src/lib/`, an MSW handler, and flip the frontend's `*_READY` flag if there is one.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `B4H login at startup failed` in the log | Box offline or wrong `B4H_BASE_URL`; the server retries on the first request |
| `B4H login refused` in the log | Wrong `B4H_USER` / `B4H_PASS`. Fix `.env` and **restart**; no more attempts are made until then. |
| `API_KEY is not set` warning | Set `API_KEY` in `.env` and the same value as `BACKEND_API_KEY` in `client/.env.local` |
| `401 Missing or wrong API key` | The two keys don't match, or the frontend wasn't restarted after setting it |
| `503 B4H box unreachable` | This PC can't reach the box IP (network, VPN, or box rebooting) |
| `504 The box took too long` | Shorten the date range, or raise `B4H_TIMEOUT` |
| `Time zone '…' not found` | Windows needs the `tzdata` package: run `uv sync` (it's a dependency), or `pip install tzdata` |
| `ffmpeg not found` | Install ffmpeg and restart the backend from a **new** terminal, or set `FFMPEG_PATH` |
| `Too many live videos open` | Close tiles or tabs, or raise `MAX_STREAMS` |
| `503 The database isn't configured` | Set `DATABASE_URL` in `.env` and restart |
| `503 The database is unreachable` | Check the Neon URL and internet access; Neon may be waking from scale-to-zero, so try again |
| `relation "…" does not exist` in the log | Run `uv run alembic upgrade head` |
| `Alarm polling failed` warnings | The box is unreachable; polling retries with growing waits (max 60 s) and catches up when it's back |
| Alarm emails stay "Waiting to send" | `SMTP_HOST` / `SMTP_FROM` aren't set, or the SMTP server refuses: use **Send test** on the Recipients tab to see its message |
| A `(…)` prefix appears in the terminal prompt | That's the project's Python virtual environment. Leave it active to run the backend; `deactivate` exits it. |