# MegCube B4H Portal

A web portal for the **MegCube B4H** AI analytics box. It shows live camera video, face recognition and capture records, the face library, camera management and time plans in one browser app, and runs on your own PC next to the box.

| Part | Folder | Tech | Details |
|---|---|---|---|
| Frontend | [`client/`](client/README.md) | Next.js 15, React 19, TypeScript, Tailwind | [client/README.md](client/README.md) |
| Backend | [`fastapi-app/`](fastapi-app/README.md) | Python 3.10+, FastAPI, httpx | [fastapi-app/README.md](fastapi-app/README.md) |
| Box API notes | [`docs/`](docs/box-api.md) | Reverse-engineered box endpoints | [docs/box-api.md](docs/box-api.md) |

## How it fits together

```
Browser ──▶ Next.js frontend ──▶ FastAPI backend ──▶ B4H box
            localhost:3000       localhost:8000      HTTPS on the LAN
            (/api/* rewrite,     (login, session,
             adds API key)        masks passwords)
```

- The **browser only talks to Next.js**. Requests to `/api/*` are forwarded to the backend, so there is no CORS setup. The Next.js server adds the backend's **API key** on the way, so the browser never sees it.
- The **backend is the only thing that talks to the box**. It handles the box's challenge–response login, re-logs in when the session expires, stops trying after a refused password (so the box account can't get locked), and never sends camera passwords to the browser.
- **Live video**: the box's own player needs a Windows plugin, so the backend uses ffmpeg to turn each camera's RTSP stream into MJPEG that a plain `<img>` can show. Those `<img>` URLs carry a short-lived signed token instead of the API key.

## Requirements

- **Node.js** 18.18+ (20 LTS recommended)
- **Python** 3.10+ and [**uv**](https://docs.astral.sh/uv/) (or pip)
- **ffmpeg** on the backend machine, for Live view only (Windows: `winget install ffmpeg`)
- The PC must be on the **same network as the box** and able to open its web UI (e.g. `https://192.168.90.200`)

## Quick start

Open two terminals from the project root.

**1. Backend**

```bash
cd fastapi-app
uv sync
```

Create `fastapi-app/.env`:

```env
B4H_BASE_URL=https://192.168.90.200
B4H_USER=admin
B4H_PASS=your-box-password
API_KEY=a-long-random-string
```

```bash
uv run uvicorn main:app --reload        # http://localhost:8000  (API docs at /docs)
```

**2. Frontend**

```bash
cd client
npm install
cp .env.example .env.local              # Windows PowerShell: copy .env.example .env.local
```

Add the same key to `client/.env.local`:

```env
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=a-long-random-string    # must equal API_KEY in fastapi-app/.env
```

```bash
npm run dev                             # http://localhost:3000
```

Open **http://localhost:3000** and log in with any username and password `admin` (demo login).

> Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Without `API_KEY` the backend still works, but its API is open to anyone on the network, and it logs a warning.

## Configuration

All settings live in git-ignored env files. **Never commit real passwords or keys.** The main ones are below. See each part's README for the full list.

| File | Variable | Default | Purpose |
|---|---|---|---|
| `fastapi-app/.env` | `B4H_BASE_URL` | `https://192.168.90.200` | Box address |
| | `B4H_USER` / `B4H_PASS` | `admin` / (set it) | Box login |
| | `API_KEY` | (empty = API open) | Key every `/api` request must carry |
| | `BOX_TIMEZONE` | `Asia/Dhaka` | Time zone for date filters |
| | `FFMPEG_PATH` / `MAX_STREAMS` | `ffmpeg` / `16` | Live view: ffmpeg location, most videos at once |
| | `B4H_TIMEOUT`, `RECOG_MAJOR`, `PEOPLE_CACHE_SECONDS`, `MAX_PHOTO_MB` | | See [backend README](fastapi-app/README.md#environment-variables) |
| `client/.env.local` | `BACKEND_URL` | `http://localhost:8000` | Where the Next.js server forwards `/api/*` |
| | `BACKEND_API_KEY` | (none) | Same value as the backend's `API_KEY` |
| | `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | Backend address as the browser sees it (live video) |

## Features and status

| Area | Page | Status |
|---|---|---|
| Live view | `/live` | ✅ Live MJPEG video per camera; light sub-stream in the grid, HD main stream on demand |
| Recognition | `/recognition` | ✅ List, filter, delete records |
| Captures | `/captures` | ✅ Face and body capture records |
| People (face library) | `/people` | ✅ Groups; add, edit, delete people |
| Devices | `/devices` | ✅ List with online status, add, edit, delete · ⏳ Picture / GB28181 devices |
| Time plans | `/timeplans` | ✅ Box clock; regular and festival plans: list, add, edit, delete |
| Dashboard, Alarms, People counting, Settings | | ⏳ Placeholder pages |

A disabled button showing *"…isn't connected yet"* means that box action hasn't been implemented yet (see the `*_READY` flags in the frontend).

## Testing

**No test needs the box**, except the optional live check.

| What | Where | Command | Needs |
|---|---|---|---|
| Backend unit/API tests (~310) | `fastapi-app/tests/` | `cd fastapi-app && uv run pytest` | Nothing; a `FakeBox` stands in for the box |
| Frontend unit/component tests | `client/src/**/*.test.tsx` | `cd client && npm test` | Nothing; MSW fakes the backend |
| Frontend end-to-end tests | `client/e2e/` | `cd client && npm run test:e2e` | Browsers, via `npx playwright install` the first time |
| Live check (read-only) | `fastapi-app/tests/live_check.py` | `uv run python tests/live_check.py` | Running backend **and the real box** |

Before pushing, run:

```bash
cd fastapi-app && uv run pytest
cd ../client && npx tsc --noEmit && npm run lint && npm test
```

How the fakes work and how to add tests: [frontend testing](client/README.md#testing) · [backend testing](fastapi-app/README.md#testing).

## Repository layout

```
MegCube-B4H/
├─ README.md            ← you are here
├─ docs/
│  └─ box-api.md        ← B4H box endpoints, payloads, error codes
├─ client/              ← Next.js frontend       (see client/README.md)
│  ├─ src/app, src/components, src/lib (API clients), src/middleware.ts
│  ├─ src/mocks, src/test ← MSW handlers + Vitest setup
│  └─ e2e/              ← Playwright tests
└─ fastapi-app/         ← FastAPI backend         (see fastapi-app/README.md)
   ├─ main.py, core.py, b4h.py (box client)
   ├─ routers/          ← devices, preview, recognition, capture, personnel, timeplan, common
   └─ tests/            ← pytest suite + live_check.py
```

## Adding a feature from the box

The box's API isn't publicly documented; endpoints are found from its own web UI.

1. Open the box's web UI, then **DevTools → Network** with "Preserve log" on.
2. Perform the action there (e.g. edit a camera) and copy the request's **method, URL, payload and response** into [`docs/box-api.md`](docs/box-api.md).
3. **Backend**: add a route in the matching `fastapi-app/routers/*.py` that calls `box.call(...)` with that payload, plus pytest tests using `fake_box`.
4. **Frontend**: add a function in `client/src/lib/*.ts`, an MSW handler in `src/mocks/handlers.ts`, use it in the component, and flip any `*_READY` flag.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| Frontend pages show load errors / `ECONNREFUSED` | Backend isn't running, or `BACKEND_URL` is wrong |
| `401 Missing or wrong API key` | `BACKEND_API_KEY` (client) ≠ `API_KEY` (backend), or the frontend wasn't restarted |
| `503 B4H box unreachable` | This PC can't reach the box (network, VPN, box rebooting) |
| `504 The box took too long` | Shorten the date range, or raise `B4H_TIMEOUT` |
| `B4H login refused` / `Box error on /auth/login` | Wrong `B4H_USER` / `B4H_PASS`. Fix `.env` and restart the backend. **5 wrong attempts lock the box account**, so the backend stops trying after one refusal. |
| Live view black / `ffmpeg not found` | Install ffmpeg, restart the backend from a new terminal, or set `FFMPEG_PATH` |
| `(b4h-portal-api)` in the terminal prompt | The backend's Python virtual environment; `deactivate` exits it |

More detail in [client/README.md](client/README.md) and [fastapi-app/README.md](fastapi-app/README.md).