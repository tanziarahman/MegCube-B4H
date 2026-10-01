# MegCube B4H Portal

A web portal for the **MegCube B4H** AI analytics box. It brings live camera video, face recognition and capture records, the face library, camera management and time plans together in one browser app, and runs on a PC on the same network as the box.

```
Browser ──▶ Next.js frontend ──▶ FastAPI backend ──▶ B4H box
            localhost:3000       localhost:8000      HTTPS on the LAN
```

## Documentation

| Document | For |
|---|---|
| **[User Guide](docs/user-guide.md)** | How to use every page: step-by-step tasks, messages, FAQ |
| **[Architecture](docs/architecture.md)** | How the parts fit together, security model, known issues |
| **[Backend API reference](docs/backend-api.md)** | Every `/api/*` route: parameters, responses, errors, box calls behind it |
| **[Box API reference](docs/box-api.md)** | Every B4H box endpoint the backend calls, and what the box returns |
| [Contributions and challenges](docs/contributions.md) | Who built what, and the problems we solved |
| [client/README.md](client/README.md) | Frontend development and tests |
| [fastapi-app/README.md](fastapi-app/README.md) | Backend development, configuration and tests |

All of it is indexed in [docs/README.md](docs/README.md).

## Requirements

- **Node.js** 18.18+ (20 LTS recommended)
- **Python** 3.10+ and [**uv**](https://docs.astral.sh/uv/) (or pip)
- **ffmpeg** on the backend machine, for Live view only (Windows: `winget install ffmpeg`, then open a new terminal)
- The PC must be on the **same network as the box** and able to open its web UI (e.g. `https://192.168.90.200`)

## Quick start

Open two terminals in the project root.

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
uv run uvicorn main:app --reload        # http://localhost:8000  (interactive API docs at /docs)
```

**2. Frontend**

```bash
cd client
npm install
cp .env.example .env.local              # Windows PowerShell: copy .env.example .env.local
```

Set the same key in `client/.env.local`:

```env
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=a-long-random-string    # must equal API_KEY in fastapi-app/.env
```

```bash
npm run dev                             # http://localhost:3000
```

**3. Open http://localhost:3000** and sign in with any username and the password `admin` (demo sign-in).

> Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Without `API_KEY` the backend still works, but its API is open to anyone on the network, and it logs a warning.

> ⚠️ The sign-in is a demo and does not protect pages. Run the portal only on a trusted network. See [Architecture → Security model](docs/architecture.md#4-security-model).

## Configuration

Settings live in git-ignored env files. **Never commit real passwords or keys.**

| File | Variable | Default | Purpose |
|---|---|---|---|
| `fastapi-app/.env` | `B4H_BASE_URL` | `https://192.168.90.200` | Box address |
| | `B4H_USER` / `B4H_PASS` | `admin` / (empty) | Box login |
| | `API_KEY` | (empty = API open) | Key every `/api` request must carry |
| | `BOX_TIMEZONE` | `Asia/Dhaka` | Time zone of the box; used for all date filters |
| | `B4H_TIMEOUT` | `15` | Seconds to wait for the box before answering `504` |
| | `FFMPEG_PATH` / `MAX_STREAMS` | `ffmpeg` / `16` | Live view: ffmpeg location, most videos at once |
| | `RECOG_MAJOR`, `PEOPLE_CACHE_SECONDS`, `MAX_PHOTO_MB` | | See [backend README](fastapi-app/README.md#environment-variables) |
| `client/.env.local` | `BACKEND_URL` | `http://localhost:8000` | Where the Next.js server forwards `/api/*` |
| | `BACKEND_API_KEY` | (none) | Same value as the backend's `API_KEY` |
| | `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | Backend address **as the browser sees it** (live video). Change it when users open the portal from another PC. |

## Features and status

| Area | Page | Status |
|---|---|---|
| Dashboard | `/` | ✅ Today's recognitions, strangers, captures, people flow, camera readiness, attention queue (auto-refresh 45 s) |
| Live view | `/live` | ✅ Up to 9 live cameras; SD in the grid, HD on demand; latest recognitions |
| Recognition | `/recognition` | ✅ Search matched/strangers, details, delete |
| Captures | `/captures` | ✅ Face and body captures, grid/list, details |
| People (face library) | `/people` | ✅ Add, edit, delete people; groups |
| Devices | `/devices` | ✅ RTSP video cameras: status, add, edit, delete · ⏳ Picture / GB28181 devices |
| Time plans | `/timeplans` | ✅ Regular and festival plans: create, edit, delete; box clock |
| Alarms, People counting, Settings | | ⏳ Placeholder pages |

Known bugs and limitations are listed in [Architecture → Known issues](docs/architecture.md#9-known-issues-and-limitations).

## Testing

**No test needs the box**, except the optional live check.

| What | Where | Command | Needs |
|---|---|---|---|
| Backend unit/API tests | `fastapi-app/tests/` | `cd fastapi-app && uv run pytest` | Nothing; a `FakeBox` stands in for the box |
| Frontend unit/component tests | `client/src/**/*.test.tsx` | `cd client && npm test` | Nothing; MSW fakes the backend |
| Frontend end-to-end tests | `client/e2e/` | `cd client && npm run test:e2e` | Browsers (`npx playwright install` the first time) |
| Live check (read-only) | `fastapi-app/tests/live_check.py` | `uv run python tests/live_check.py` | A running backend **and the real box** |

Before pushing:

```bash
cd fastapi-app && uv run pytest
cd ../client && npx tsc --noEmit && npm run lint && npm test
```

## Repository layout

```
MegCube-B4H/
├─ README.md               ← you are here
├─ docs/                   ← user guide, architecture, API references (see docs/README.md)
├─ client/                 ← Next.js frontend  (client/README.md)
│  ├─ src/app/             ← pages (folder name = URL)
│  ├─ src/components/      ← page bodies
│  ├─ src/lib/             ← API clients: the only code that calls /api
│  ├─ src/mocks, src/test/ ← MSW fake backend + Vitest setup
│  └─ e2e/                 ← Playwright tests
└─ fastapi-app/            ← FastAPI backend  (fastapi-app/README.md)
   ├─ main.py, core.py, b4h.py
   ├─ routers/             ← one file per feature area
   └─ tests/               ← pytest suite + live_check.py
```

## Adding a feature from the box

The box's API isn't publicly documented; endpoints are found from its own web UI.

1. **Capture** the box request in DevTools and add it to [docs/box-api.md](docs/box-api.md#13-how-to-capture-a-new-endpoint).
2. **Backend:** add a route in `fastapi-app/routers/*.py` that calls `box.call(...)`, with pytest tests using `fake_box`. Document it in [docs/backend-api.md](docs/backend-api.md).
3. **Frontend:** add a function in `client/src/lib/*.ts` and an MSW handler in `src/mocks/handlers.ts`, then use it in the component.
4. **User Guide:** describe the new page or button in [docs/user-guide.md](docs/user-guide.md).

## Troubleshooting

| Symptom | Where to look |
|---|---|
| Pages show load errors / `ECONNREFUSED` in the frontend terminal | The backend isn't running, or `BACKEND_URL` is wrong |
| `401 Missing or wrong API key` | `BACKEND_API_KEY` (client) ≠ `API_KEY` (backend), or the frontend wasn't restarted after the change |
| `503 B4H box unreachable` | This PC can't reach the box (network, VPN, box rebooting) |
| `504 The box took too long` | Shorten the date range, or raise `B4H_TIMEOUT` |
| `B4H login refused` / `Login to the box is paused` | Wrong `B4H_USER` / `B4H_PASS`. Fix `.env` and **restart** the backend. **5 wrong attempts lock the box account**, so the backend stops trying after one refusal. |
| Live view black / `ffmpeg not found` | Install ffmpeg, restart the backend from a new terminal, or set `FFMPEG_PATH` |
| Live view works on the server PC but not on others | Set `NEXT_PUBLIC_BACKEND_URL` to an address other PCs can reach, and rebuild/restart the frontend |

More in [client/README.md](client/README.md#troubleshooting) and [fastapi-app/README.md](fastapi-app/README.md#troubleshooting).
