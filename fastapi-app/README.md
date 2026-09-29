# B4H Portal: Backend

FastAPI service that sits between the web portal (`../client`) and the MegCube B4H analytics box. It:

- logs in to the box and keeps the session alive,
- exposes simple `/api/*` endpoints for the frontend,
- strips camera passwords before anything reaches the browser,
- proxies box images and converts camera RTSP streams to MJPEG for the Live view.

```
Browser  →  Next.js (localhost:3000)  →  /api/* rewrite  →  FastAPI (localhost:8000)  →  B4H box (HTTPS)
```

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Network access to the box (default `https://192.168.90.200`)
- **ffmpeg**, only needed for the Live view (`winget install ffmpeg` on Windows, then open a new terminal)

## Setup and run

```bash
cd fastapi-app
uv sync                          # creates .venv and installs dependencies
# create .env (see below)
uv run uvicorn main:app --reload # http://localhost:8000
```

Without uv:

```bash
python -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install "fastapi[standard]" httpx python-dotenv python-multipart
uvicorn main:app --reload
```

Interactive API docs are generated automatically at **http://localhost:8000/docs**.

If the box is offline at startup, the server still starts and logs in again on the first request.

## Environment variables

Create `fastapi-app/.env`. It is git-ignored, so never commit it.

```env
B4H_BASE_URL=https://192.168.90.200
B4H_USER=admin
B4H_PASS=your-box-password
RECOG_MAJOR=face_basic_business
# FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe   # only if ffmpeg isn't on PATH
```

| Variable | Default | Purpose |
|---|---|---|
| `B4H_BASE_URL` | `https://192.168.90.200` | Box address |
| `B4H_USER` | `admin` | Box login user |
| `B4H_PASS` | (none; set it) | Box login password |
| `RECOG_MAJOR` | `face_basic_business` | Alarm major type that recognition and capture records are stored under |
| `FFMPEG_PATH` | `ffmpeg` | Path to ffmpeg for the Live view |

> Security: remove the hard-coded default password from `core.py` so the box password only ever lives in `.env`.

## Project structure

```
fastapi-app/
├─ main.py            # app entry: lifespan (login/close), error handlers, router wiring
├─ core.py            # shared box client, config from .env, small helpers
├─ b4h.py             # B4HClient: login, session handling, call/upload/get_bytes
└─ routers/
   ├─ devices.py      # Devices page: camera list + status, add, delete
   ├─ preview.py      # Live view: camera list, RTSP → MJPEG stream (ffmpeg)
   ├─ recognition.py  # Recognition records, face-library person list
   ├─ capture.py      # Face/body capture records
   ├─ personnel.py    # Face library: groups, add/edit/delete people
   └─ common.py       # Image proxy
```

## API endpoints

| Method | Path | Used by | Box endpoint(s) |
|---|---|---|---|
| GET | `/api/devices/detail` | Devices | `POST /device_access/device_config` + `POST /device_access/device_state` |
| POST | `/api/devices` | Devices: add | `POST /device_access/device` |
| DELETE | `/api/devices/{id}` | Devices: delete | `DELETE /device_access/device` |
| GET | `/api/preview/cameras` | Live view | `device_config`, `device_state`, `intelli_manager/task_list` |
| GET | `/api/preview/{id}/stream` | Live view (`<img src>`) | RTSP via ffmpeg |
| GET | `/api/recognition` | Recognition | `POST /device_alarm/alarm_history` |
| DELETE | `/api/recognition/{alarm_id}` | Recognition | `DELETE /device_alarm/alarm_history` |
| GET | `/api/people` | Recognition filters | `POST /face_manager/person/query` |
| GET | `/api/capture` | Captures | `POST /device_alarm/alarm_history` |
| GET | `/api/personnel/groups` | People | `POST /face_manager/groups/query` |
| GET / POST | `/api/personnel` | People | `POST /face_manager/person/query`, upload to `/face_manager/person` |
| PUT / DELETE | `/api/personnel/{id}` | People | `PUT /face_manager/person` (upload) + `PUT /face_manager/person_bind`, `DELETE /face_manager/person` |
| GET | `/api/image?uri=…` | All image thumbnails | `/device_storage/get_image` |

See `/docs` for request and response shapes.

## How the box connection works (`b4h.py`)

**Login** is a challenge–response exchange:
1. `GET /auth/login/challenge?username=…` returns `session_id`, `salt` and `challenge`.
2. `POST /auth/login` with `password = sha256(password + salt + challenge)`.
3. Every request after that sends `Cookie: sessionID=<session_id>`.

Box quirks the client already handles:

- **Idle sessions expire after about 30 s** (code `512`). `call()` logs in again and retries once.
- **One query at a time per session.** Parallel calls fail with code `1073741825`, so calls are serialised with a lock.
- **At most 30 records per page** for record queries (`BOX_MAX_PAGE_SIZE`).
- **Self-signed HTTPS certificate**, so TLS verification is off for the box connection only.
- **5 wrong passwords in a row lock the box account.** Double-check `B4H_PASS` before restarting repeatedly.

**Error mapping:**

| Situation | HTTP status to frontend |
|---|---|
| Box returned a non-zero `code` | `502` with `detail: "Box error on <path>: <message> (code N)"` |
| Box unreachable or timed out | `503` |
| Bad input from the frontend | `422` (FastAPI validation) |
| Unknown id / duplicate name | `404` / `409` |

## Adding an endpoint for a new box feature

1. Use the feature in the box's own web UI with DevTools → Network open ("Preserve log" on).
2. Copy the request method, path, payload and response.
3. Add a route in the matching `routers/*.py` that calls `box.call(METHOD, "/box/path", payload)`. `call()` returns `data` or raises `B4HError`.
4. Validate input with a Pydantic model, and never return passwords (see `_mask_url` in `devices.py`).
5. Add a client function in `client/src/lib/` and flip the frontend's `*_READY` flag if there is one.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `B4H login at startup failed` in the log | Box offline or wrong `B4H_BASE_URL`; the server retries on the first request |
| `Box error on /auth/login` | Wrong `B4H_USER` / `B4H_PASS`. Stop before 5 attempts or the account locks. |
| `503 B4H box unreachable` | This PC can't reach the box IP (network, VPN, or box rebooting) |
| `ffmpeg not found` | Install ffmpeg and restart the backend from a **new** terminal, or set `FFMPEG_PATH` |
| `(b4h-portal-api)` or `.venv` appears in the terminal | That's the project's virtual environment. Leave it active to run the backend; `deactivate` exits it. |