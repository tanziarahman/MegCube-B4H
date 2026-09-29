# B4H Portal: Frontend

Web portal for the MegCube B4H analytics box. It is built with Next.js 15 (App Router), React 19, TypeScript and Tailwind CSS.

The frontend never talks to the box directly. Every request to `/api/*` is forwarded to the FastAPI backend (`../fastapi-app`). The backend holds the box login session and keeps camera passwords out of the browser.

```
Browser  →  Next.js (localhost:3000)  →  middleware adds X-API-Key  →  /api/* rewrite  →  FastAPI (localhost:8000)  →  B4H box
Live video <img>  ─────────────────────── signed link (?exp=…&sig=…) ──────────────────▶  FastAPI
```

## Requirements

- Node.js 18.18 or newer (20 LTS recommended)
- The backend running (see `../fastapi-app/README.md`). Without it, data pages show a load error. The tests don't need it.

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
| `npm test` | Unit and component tests (Vitest), run once |
| `npm run test:watch` | Vitest in watch mode |
| `npm run test:e2e` | End-to-end tests (Playwright) |
| `npm run test:e2e:ui` | Playwright's interactive UI |

## Environment variables

Set these in `client/.env.local`, then restart `npm run dev`.

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Where the backend runs. Used by the `/api/*` rewrite in `next.config.ts` (server side). |
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | Backend address **as seen from the browser**, used for live video `<img>` URLs, which bypass the proxy so frames aren't buffered. |
| `BACKEND_API_KEY` | (none) | Must equal the backend's `API_KEY`. `src/middleware.ts` adds it as `X-API-Key` to every `/api` request on the Next.js server, so browsers never see it. |

> `.env.example` currently only lists `BACKEND_URL`. Add the other two when you use an API key or run the backend on another host or port.

## Pages

| URL | Page | Status |
|---|---|---|
| `/login` | Login | Demo login |
| `/` | Dashboard | Connected (today's security activity, camera health, attention queue, and 45-second refresh) |
| `/live` | Live view | Connected (MJPEG streams, sub-stream in the grid, main stream in HD) |
| `/alarms`, `/alarms/:id` | Alarms | Placeholder |
| `/recognition` | Recognition records | Connected (list, filter, delete) |
| `/recognition/:id` | Recognition detail | Placeholder |
| `/captures` | Face and body captures | Connected |
| `/counting` | People counting | Placeholder |
| `/people` | Face library | Connected (list, add, edit, delete) |
| `/devices` | Cameras | Connected (list, status, add, edit, delete; RTSP video only) |
| `/timeplans` | Time plans | Connected (regular and festival plans: list, add, edit, delete) |
| `/settings` | Settings | Placeholder |

## Project structure

```
client/
├─ src/
│  ├─ app/
│  │  ├─ layout.tsx              # root HTML, fonts, global CSS
│  │  ├─ login/page.tsx          # login (no sidebar/navbar)
│  │  └─ (portal)/               # route group: every page here gets the app shell
│  │     ├─ layout.tsx           # wraps pages in <AppShell>
│  │     ├─ page.tsx             # /  Dashboard
│  │     └─ live/ alarms/ recognition/ captures/ counting/ people/ devices/ timeplans/ settings/
│  ├─ components/
│  │  ├─ layout/                 # AppShell, Sidebar/, Navbar/
│  │  ├─ common/                 # PageHeader, Placeholder
│  │  ├─ dashboard/ devices/ people/ recognition/ captures/ timeplans/
│  │  └─ **/*.test.tsx           # component tests sit next to the component
│  ├─ lib/                       # API clients: the ONLY place that calls fetch('/api/...')
│  │  ├─ dashboard.ts devices.ts personnel.ts recognition.ts captures.ts preview.ts timeplans.ts
│  │  └─ paths.ts                # every page URL in one place
│  ├─ mocks/handlers.ts          # MSW fake backend responses for tests
│  ├─ test/setup.ts              # Vitest setup: jest-dom matchers + MSW server
│  ├─ middleware.ts              # adds X-API-Key to /api requests
│  ├─ config/navigation.ts       # sidebar sections and links
│  └─ hooks/useLocalStorage.ts
├─ e2e/                          # Playwright end-to-end tests
├─ vitest.config.mts
└─ playwright.config.ts
```

## Conventions

- **API calls live in `src/lib/*.ts`.** Components import functions such as `fetchDeviceDetails()` and never call `fetch` themselves. Each client maps the backend's snake_case fields to camelCase types and throws an `Error` carrying the backend's `detail` message.
- **URLs come from `lib/paths.ts`.** Don't type page paths as strings.
- **Feature flags for unfinished box writes.** Flags like `CREATE_READY` / `UPDATE_READY` / `DELETE_READY` in `components/devices/DeviceModals.tsx` keep a button disabled, with a "not connected yet" note, until the box request behind it exists in the backend. All three are `true` now. Picture and GB28181 devices are still blocked in the form.
- **Client vs server components.** Pages stay server components. Anything with state, effects or browser APIs starts with `'use client'`.
- **Images from the box** go through the backend: `/api/image?uri=<box image path>`.
- **Styling** uses Tailwind with the project colour tokens (`pri`, `line`, `mute`, `ground`, `crit`, …) from `tailwind.config.js`.

## Testing

No test needs the backend or the box.

### Unit and component tests (Vitest + Testing Library + MSW)

```bash
npm test               # run once
npm run test:watch     # re-run on save
```

- Tests are `src/**/*.test.ts(x)` files, next to the code they test. The runner is jsdom (`vitest.config.mts`).
- **MSW** (`src/mocks/handlers.ts`) fakes the backend at the network level, so components call their real `lib/` clients. `src/test/setup.ts` starts the MSW server, and `onUnhandledRequest: 'error'` makes any request without a handler fail the test.
- `handlers.ts` also exports ready-made scenarios to swap in with `server.use(...)`:
  `serverErrorHandlers` (503/500/504), `emptyHandlers` (empty lists) and `networkFailureHandlers` (connection lost).

| Test file | Covers |
|---|---|
| `app/login/page.test.tsx` | Valid and invalid sign-in, keyboard and password-field accessibility |
| `components/dashboard/DashboardView.test.tsx` | Summary cards, camera readiness and the attention queue render from the dashboard summary |
| `components/devices/DevicesTable.test.tsx` | Online/offline status, filters and reset, loading skeleton, empty state, RTSP validation, Escape to close, submitting the add form |
| `components/people/PeopleView.test.tsx` | List, profile details, loading and empty states, required name and photo on add |
| `components/recognition/RecognitionTable.test.tsx` | Records, detail drawer, loading and empty states, delete confirmation, focus handling |

**Adding a test:** put `Foo.test.tsx` next to `Foo.tsx`, and add a handler to `mocks/handlers.ts` for any new `/api` endpoint it calls. Copy sample data from a real backend response (`http://localhost:8000/docs`) so the fakes stay realistic.

### End-to-end tests (Playwright)

```bash
npx playwright install   # first time only: downloads the browsers
npm run test:e2e         # all browsers
npx playwright test --project=chromium   # one browser
npm run test:e2e:ui      # interactive runner
```

- Tests live in `e2e/`. Playwright starts its own dev server on **http://127.0.0.1:3100** (`playwright.config.ts`), or reuses one already running there.
- Runs in Chromium, Firefox and WebKit. On CI it retries failed tests twice and records a trace.
- `e2e/auth-navigation.spec.ts` covers the login (wrong and right password), moving between pages, and the keyboard-operated user menu with sign-out.
- To test a data page without the backend, fake its API inside the test with `page.route('**/api/...', r => r.fulfill({ json: … }))`.

### Before pushing

```bash
npx tsc --noEmit && npm run lint && npm test
```

## Adding a page

1. Create `src/app/(portal)/foo/page.tsx`. The folder name becomes the URL.
2. Add `foo: '/foo'` to `lib/paths.ts`.
3. Add a sidebar link in `config/navigation.ts` if it should appear there.
4. If it needs data, add a client in `src/lib/foo.ts` that calls a backend `/api/...` endpoint.
5. Add MSW handlers and a `*.test.tsx` for the new component.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Pages show "Request failed (500)" or `ECONNREFUSED` in the terminal | Backend isn't running, or `BACKEND_URL` is wrong |
| Every page says "Missing or wrong API key" (401) | `BACKEND_API_KEY` in `.env.local` doesn't match the backend's `API_KEY`, or wasn't set before `npm run dev` started |
| Errors mentioning "Box error" or "unreachable" | The backend can't reach or log in to the box (see the backend README) |
| Dashboard is slow to load on a busy day | It reads up to 5,000 of today's records from the box. The page says when trend figures are based on a sample; totals stay complete. |
| Dashboard shows "Box clock unavailable" | The box's time endpoints didn't answer; the backend's clock is used instead |
| Live view tiles stay black | ffmpeg isn't installed on the backend machine, or `NEXT_PUBLIC_BACKEND_URL` isn't reachable from the browser |
| "Too many live videos open" | The backend's `MAX_STREAMS` limit; close tiles or tabs |
| A test fails with "request without a matching handler" | Add a handler for that `/api` call in `src/mocks/handlers.ts` |
| Playwright: "Executable doesn't exist" | Run `npx playwright install` |