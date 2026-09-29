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

Generate an API key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Access control (API key)

- With `API_KEY` set, all `/api/*` routes need `X-API-Key: <API_KEY>`. The key is checked in `core.check_access`, wired to every router in `main.py`. A missing or wrong key returns `401`. The key is **not** accepted as a URL parameter.
- The Next.js server adds the header (`client/src/middleware.ts` with `BACKEND_API_KEY`), so the browser never sees the key.
- **Live video** is loaded by an `<img>` tag, which can't send headers. `/api/preview/cameras` therefore returns a `stream_token` for each camera (`exp=…&sig=…`, an HMAC of camera id and expiry, valid for 12 hours). It only opens **that camera's** stream, and stops working if `API_KEY` changes.
- `GET /` stays open as a health check.

## Project structure

```
fastapi-app/
├─ main.py            # app entry: lifespan (login/close), error handlers, access check, router wiring
├─ core.py            # box client, config from .env, time-zone handling, people cache, API-key check
├─ b4h.py             # B4HClient: login (lockout-safe), session renewal, call/upload/get_bytes
├─ routers/
│  ├─ devices.py      # Devices page: camera list + status, add, edit, delete
│  ├─ preview.py      # Live view: camera list, RTSP → MJPEG stream (ffmpeg)
│  ├─ recognition.py  # Recognition records, face-library person list
│  ├─ capture.py      # Face/body capture records
│  ├─ personnel.py    # Face library: groups, add/edit/delete people
│  ├─ timeplan.py     # Time plans: box clock, regular/festival schedule plans
│  └─ common.py       # Camera names, image proxy
└─ tests/             # pytest suite (fake box) + live_check.py (real box)
```

## API endpoints

| Method | Path | Used by | Box endpoint(s) |
|---|---|---|---|
| GET | `/api/devices/detail` | Devices | `POST /device_access/device_config` + `POST /device_access/device_state` |
| POST | `/api/devices` | Devices: add | `POST /device_access/device` |
| PUT | `/api/devices/{id}` | Devices: edit (empty password keeps the current one) | `PUT /device_access/device_config` |
| DELETE | `/api/devices/{id}` | Devices: delete | `DELETE /device_access/device` |
| GET | `/api/devices` | Camera names on Recognition/Captures | `POST /device_access/device_config` (id + name only) |
| GET | `/api/preview/cameras` | Live view | `device_config`, `device_state`, `intelli_manager/task_list` |
| GET | `/api/preview/{id}/stream` | Live view (`<img src>`); `?hd=true` main stream, otherwise sub-stream | RTSP via ffmpeg |
| GET | `/api/recognition` | Recognition | `POST /device_alarm/alarm_history` |
| DELETE | `/api/recognition/{alarm_id}` | Recognition | `DELETE /device_alarm/alarm_history` |
| GET | `/api/people` | Recognition filters (cached) | `POST /face_manager/person/query` (all pages) |
| GET | `/api/capture` | Captures | `POST /device_alarm/alarm_history` |
| GET | `/api/personnel/groups` | People | `POST /face_manager/groups/query` |
| GET / POST | `/api/personnel` | People | `POST /face_manager/person/query`, upload to `/face_manager/person` |
| PUT / DELETE | `/api/personnel/{id}` | People | `PUT /face_manager/person` (upload) + `PUT /face_manager/person_bind`, `DELETE /face_manager/person` |
| GET | `/api/timeplans/time` | Time plans | `POST /system/get_system_time`, `POST /system/get_time_info` |
| GET | `/api/timeplans/regular`, `/festival` | Time plans | `POST /device_rules/schedule_plan/query` (type 1 / 2) |
| POST / PUT / DELETE | `/api/timeplans[/{plan_id}]` | Time plans | `POST` / `PUT` / `DELETE /device_rules/schedule_plan` |
| DELETE | `/api/timeplans/stream-subscriptions` | Time plans | `DELETE /media_video/subscribe_stream`, `DELETE /device_alarm/subscribe_stream` |
| GET | `/api/dashboard/summary` | Dashboard | device config/state, task list, box clock, recognition and capture history |
| GET | `/api/image?uri=…` | All image thumbnails | `/device_storage/get_image` |

Box request details are in [`../docs/box-api.md`](../docs/box-api.md). Request and response shapes for these routes are at `/docs`.

## How the box connection works (`b4h.py`)

**Login** is a challenge–response exchange:
1. `GET /auth/login/challenge?username=…` returns `session_id`, `salt` and `challenge`.
2. `POST /auth/login` with `password = sha256(password + salt + challenge)`.
3. Every request after that sends `Cookie: sessionID=<session_id>`.

Box quirks the client handles:

- **Idle sessions expire after about 30 s** (code `512`). The client logs in again and retries **once**. Many requests hitting an expired session together share **one** re-login.
- **One query at a time per session.** Parallel calls fail with code `1073741825`, so calls are serialised with a lock.
- **5 wrong passwords in a row lock the box account.** Only one login runs at a time, and after the box refuses the credentials no more attempts are made until restart.
- **At most 30 records per page** for record queries (`BOX_MAX_PAGE_SIZE`). Asking for a page past the end gives an empty page, not the box's `general` error.
- **Self-signed HTTPS certificate**, so TLS verification is off for the box connection only.
- **Times are in the box's time zone** (`BOX_TIMEZONE`), whatever the server's own time zone is.

**Error mapping:**

| Situation | HTTP status to frontend |
|---|---|
| Missing or wrong API key | `401` |
| Bad input from the frontend (bad date, unknown type, page size > 30, start after end) | `422`. Refused before anything reaches the box. |
| Unknown id / duplicate name | `404` / `409` |
| Face photo too large | `413` |
| Box returned a non-zero `code` | `502` with `detail: "Box error on <path>: <message> (code N)"` |
| Box unreachable, or too many live videos open | `503` |
| Box connected but too slow (e.g. a long date range) | `504` with a hint to shorten the range |

## Testing

### Automated tests (pytest, no box needed)

```bash
cd fastapi-app
uv sync                 # installs pytest (dev dependency group)
uv run pytest           # about 310 tests, under a minute
uv run pytest -v tests/test_devices.py        # one file
uv run pytest -k "password"                  # tests whose name matches
```

- `tests/conftest.py` swaps the box connection for a **`FakeBox`**. Each test fills in `fake_box.replies[(METHOD, path)]` with data, an exception, or a function. The fake **records every request** the backend sent, so tests check both the API response and the exact box payload (`fake_box.sent("PUT", "/device_access/device_config")`).
- An unexpected box call fails the test, so a route can't silently hit an endpoint nobody planned for.
- The API-key check is off in tests by default. `test_access.py` turns it on.
- Sample box data in `conftest.py` (`DEVICE_CONFIG`, `DEVICE_STATE`, `TASK_LIST`) is copied from real responses.

| Test file | Covers |
|---|---|
| `test_b4h_client.py` | Hashed login, lockout protection, session expiry and one retry, serialised calls, shared re-login, unreachable box |
| `test_access.py` | API key on every route, wrong/missing key, signed stream links (other camera, expired, tampered, old key) |
| `test_core.py` | Box time zone vs server time zone, missing tz data |
| `test_main.py` | Starts with the box offline, unknown route, unexpected error → 500, all routes registered |
| `test_devices.py` | Password masking, detail list, add (lowest free id, duplicate names, bad input, concurrent adds), delete |
| `test_preview.py` | Camera list, ffmpeg start/stop, sub vs main stream, stream limit, missing ffmpeg, bad params |
| `test_recognition.py` | Box payload, paging, validation, empty pages, 502/503/504 mapping, delete, `/api/people` paging and cache |
| `test_capture.py` | Target-type mapping, record flattening, missing fields, paging, errors |
| `test_personnel.py` | Groups, list, add/edit/delete, Bangla names, photo size limit, group-binding failure |
| `test_common.py` | Image proxy: path whitelist, content types, fallbacks, session expiry, 404s |

**Not covered yet:** `PUT /api/devices/{id}` (device edit) and all of `routers/timeplan.py` have no tests. Add them next.

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
2. Copy the request method, path, payload and response, and add them to `../docs/box-api.md`.
3. Add a route in the matching `routers/*.py` that calls `box.call(METHOD, "/box/path", payload)`. `call()` returns `data` or raises `B4HError`. New router files must be added to the list in `main.py` so they get the API-key check.
4. Validate input with a Pydantic model, and never return passwords (see `_mask_url` in `devices.py`).
5. Add tests with `fake_box` that assert the exact payload sent to the box.
6. Add a client function in `client/src/lib/`, an MSW handler, and flip the frontend's `*_READY` flag if there is one.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `B4H login at startup failed` in the log | Box offline or wrong `B4H_BASE_URL`; the server retries on the first request |
| `B4H login refused` in the log | Wrong `B4H_USER` / `B4H_PASS`. Fix `.env` and **restart**; no more attempts are made until then. |
| `API_KEY is not set` warning | Set `API_KEY` in `.env` and the same value as `BACKEND_API_KEY` in `client/.env.local` |
| `401 Missing or wrong API key` | The two keys don't match, or the frontend wasn't restarted after setting it |
| `503 B4H box unreachable` | This PC can't reach the box IP (network, VPN, or box rebooting) |
| `504 The box took too long` | Shorten the date range, or raise `B4H_TIMEOUT` |
| `Time zone '…' not found` | Windows: `uv add tzdata` |
| `ffmpeg not found` | Install ffmpeg and restart the backend from a **new** terminal, or set `FFMPEG_PATH` |
| `Too many live videos open` | Close tiles or tabs, or raise `MAX_STREAMS` |
| `(b4h-portal-api)` appears in the terminal | That's the project's virtual environment. Leave it active to run the backend; `deactivate` exits it. |