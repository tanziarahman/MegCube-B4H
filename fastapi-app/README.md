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
- `GET /` stays open as a health check. FastAPI's own `/docs` and `/openapi.json` are also open (they aren't under `/api`).
- The portal's sign-in page is a demo and doesn't protect anything; see [Architecture → Security model](../docs/architecture.md#4-security-model).

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
| `test_dashboard.py` | Summary totals, people-flow counts, attention items (offline camera, stream not pulling), bad date refused before any box call |
| `test_capture.py` | Target-type mapping, record flattening, missing fields, paging, errors |
| `test_personnel.py` | Groups, list, add/edit/delete, Bangla names, photo size limit, group-binding failure |
| `test_common.py` | Image proxy: path whitelist, content types, fallbacks, session expiry, 404s |
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
| A `(…)` prefix appears in the terminal prompt | That's the project's Python virtual environment. Leave it active to run the backend; `deactivate` exits it. |