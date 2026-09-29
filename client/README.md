# B4H Portal: Frontend

Web portal for the MegCube B4H analytics box. It is built with Next.js 15 (App Router), React 19, TypeScript and Tailwind CSS.

The frontend never talks to the box directly. Every request to `/api/*` is forwarded to the FastAPI backend (`../fastapi-app`). The backend holds the box login session and keeps camera passwords out of the browser.

```
Browser  →  Next.js (localhost:3000)  →  /api/* rewrite  →  FastAPI (localhost:8000)  →  B4H box
```

## Requirements

- Node.js 18.18 or newer (20 LTS recommended)
- The backend running (see `../fastapi-app/README.md`). Without it, data pages show a load error.

## Setup and run

```bash
cd client
npm install
cp .env.example .env.local     # Windows PowerShell: copy .env.example .env.local
npm run dev                    # http://localhost:3000
```

Demo login: any username, password `admin`.

| Command | What it does |
|---|---|
| `npm run dev` | Development server with hot reload |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Lint the code |

## Environment variables

Set these in `client/.env.local`.

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Where the FastAPI backend runs. Used by the `/api/*` rewrite in `next.config.ts`. |

Restart `npm run dev` after changing it.

## Pages

| URL | Page | Status |
|---|---|---|
| `/login` | Login | Demo login |
| `/` | Dashboard | Placeholder |
| `/live` | Live view | Connected (MJPEG stream from the backend) |
| `/alarms`, `/alarms/:id` | Alarms | Placeholder |
| `/recognition` | Recognition records | Connected (list, filter, delete) |
| `/recognition/:id` | Recognition detail | Placeholder |
| `/captures` | Face and body captures | Connected |
| `/counting` | People counting | Placeholder |
| `/people` | Face library | Connected (list, add, edit, delete) |
| `/devices` | Cameras | Connected (list, status, add, delete). Edit is off until `UPDATE_READY` is turned on. |
| `/settings` | Settings | Placeholder |

## Project structure

```
src/
├─ app/
│  ├─ layout.tsx               # root HTML, fonts, global CSS
│  ├─ login/page.tsx           # login (no sidebar/navbar)
│  └─ (portal)/                # route group: every page here gets the app shell
│     ├─ layout.tsx            # wraps pages in <AppShell>
│     ├─ page.tsx              # /  Dashboard
│     └─ live/ alarms/ recognition/ captures/ counting/ people/ devices/ settings/
├─ components/
│  ├─ layout/                  # AppShell, Sidebar/, Navbar/
│  ├─ common/                  # PageHeader, Placeholder
│  ├─ devices/                 # DevicesTable, DeviceModals
│  ├─ people/                  # PeopleView
│  ├─ recognition/             # RecognitionTable, RecognitionDrawer
│  └─ captures/                # CapturesView
├─ lib/                        # API clients: the ONLY place that calls fetch('/api/...')
│  ├─ devices.ts  personnel.ts  recognition.ts  captures.ts  preview.ts
│  └─ paths.ts                 # every page URL in one place
├─ config/navigation.ts        # sidebar sections and links
└─ hooks/useLocalStorage.ts
```

## Conventions

- **API calls live in `src/lib/*.ts`.** Components import functions such as `fetchDeviceDetails()` and never call `fetch` themselves. Each client maps the backend's snake_case fields to camelCase types and throws an `Error` carrying the backend's `detail` message.
- **URLs come from `lib/paths.ts`.** Don't type page paths as strings.
- **Feature flags for unfinished box writes.** A flag like `UPDATE_READY` in `components/devices/DeviceModals.tsx` keeps a button disabled, with a "not connected yet" note, until the box request behind it has been captured and implemented in the backend. Flip the flag to `true` only after the backend endpoint exists.
- **Client vs server components.** Pages stay server components. Anything with state, effects or browser APIs starts with `'use client'`.
- **Images from the box** go through the backend: `/api/image?uri=<box image path>`.
- **Styling** uses Tailwind with the project colour tokens (`pri`, `line`, `mute`, `ground`, `crit`, …) from `tailwind.config.js`.

## Adding a page

1. Create `src/app/(portal)/foo/page.tsx`. The folder name becomes the URL.
2. Add `foo: '/foo'` to `lib/paths.ts`.
3. Add a sidebar link in `config/navigation.ts` if it should appear there.
4. If it needs data, add a client in `src/lib/foo.ts` that calls a backend `/api/...` endpoint.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Pages show "Request failed (500)" or `ECONNREFUSED` in the terminal | Backend isn't running, or `BACKEND_URL` is wrong |
| Errors mentioning "Box error" or "unreachable" | The backend can't reach or log in to the box (see the backend README) |
| Live view is black | ffmpeg isn't installed on the backend machine |
| A Save button stays disabled with "…isn't connected yet" | That box write isn't implemented yet (see the feature flags above) |