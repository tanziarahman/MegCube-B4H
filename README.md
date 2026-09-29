# MegCube B4H Portal

A web portal for the **MegCube B4H** AI analytics box. It shows live camera video, face recognition and capture records, the face library, and camera management in one browser app, and runs on your own PC next to the box.

| Part | Folder | Tech | Details |
|---|---|---|---|
| Frontend | [`client/`](client/README.md) | Next.js 15, React 19, TypeScript, Tailwind | [client/README.md](client/README.md) |
| Backend | [`fastapi-app/`](fastapi-app/README.md) | Python 3.10+, FastAPI, httpx | [fastapi-app/README.md](fastapi-app/README.md) |

## How it fits together

```
Browser ──▶ Next.js frontend ──▶ FastAPI backend ──▶ B4H box
            localhost:3000       localhost:8000      HTTPS on the LAN
            (/api/* rewrite)     (login, session,
                                  masks passwords)
```

- The **browser only talks to Next.js**. Requests to `/api/*` are forwarded to the backend, so there is no CORS setup.
- The **backend is the only thing that talks to the box**. It handles the box's challenge–response login, re-logs in when the session expires, and never sends camera passwords to the browser.
- **Live video**: the box's own player needs a Windows plugin, so the backend uses ffmpeg to turn each camera's RTSP stream into MJPEG that a plain `<img>` can show.

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
```

```bash
uv run uvicorn main:app --reload        # http://localhost:8000  (API docs at /docs)
```

**2. Frontend**

```bash
cd client
npm install
cp .env.example .env.local              # Windows PowerShell: copy .env.example .env.local
npm run dev                             # http://localhost:3000
```

Open **http://localhost:3000** and log in with any username and password `admin` (demo login).

## Configuration

All settings live in git-ignored env files. **Never commit real passwords.**

| File | Variable | Default | Purpose |
|---|---|---|---|
| `fastapi-app/.env` | `B4H_BASE_URL` | `https://192.168.90.200` | Box address |
| | `B4H_USER` | `admin` | Box login user |
| | `B4H_PASS` | (set it) | Box login password |
| | `RECOG_MAJOR` | `face_basic_business` | Alarm type holding recognition/capture records |
| | `FFMPEG_PATH` | `ffmpeg` | ffmpeg location, if not on PATH |
| `client/.env.local` | `BACKEND_URL` | `http://localhost:8000` | Where the frontend forwards `/api/*` |

## Features and status

| Area | Page | Status |
|---|---|---|
| Live view | `/live` | ✅ Live MJPEG video per camera |
| Recognition | `/recognition` | ✅ List, filter, delete records |
| Captures | `/captures` | ✅ Face and body capture records |
| People (face library) | `/people` | ✅ Groups; add, edit, delete people |
| Devices | `/devices` | ✅ List with online status, add, delete · ⏳ Edit (in progress) · ⏳ Picture / GB28181 devices |
| Dashboard, Alarms, People counting, Settings | | ⏳ Placeholder pages |

A disabled button showing *"…isn't connected yet"* means that box action hasn't been implemented yet (see the `*_READY` flags in the frontend).

## Repository layout

```
MegCube-B4H/
├─ README.md            ← you are here
├─ client/              ← Next.js frontend       (see client/README.md)
│  └─ src/app, src/components, src/lib (API clients) …
└─ fastapi-app/         ← FastAPI backend         (see fastapi-app/README.md)
   ├─ main.py, core.py, b4h.py (box client)
   └─ routers/          ← one file per feature: devices, preview, recognition, capture, personnel, common
```

## Adding a feature from the box

The box's API isn't publicly documented; endpoints are found from its own web UI.

1. Open the box's web UI, then **DevTools → Network** with "Preserve log" on.
2. Perform the action there (e.g. edit a camera) and copy the request's **method, URL, payload and response**.
3. **Backend**: add a route in the matching `fastapi-app/routers/*.py` that calls `box.call(...)` with that payload.
4. **Frontend**: add a function in `client/src/lib/*.ts`, use it in the component, and flip any `*_READY` flag.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| Frontend pages show load errors / `ECONNREFUSED` | Backend isn't running, or `BACKEND_URL` is wrong |
| `503 B4H box unreachable` | This PC can't reach the box (network, VPN, box rebooting) |
| `Box error on /auth/login` | Wrong `B4H_USER` / `B4H_PASS`. **5 wrong attempts lock the box account.** |
| Live view black / `ffmpeg not found` | Install ffmpeg, restart the backend from a new terminal, or set `FFMPEG_PATH` |
| `(b4h-portal-api)` in the terminal prompt | The backend's Python virtual environment; `deactivate` exits it |

More detail in [client/README.md](client/README.md) and [fastapi-app/README.md](fastapi-app/README.md).