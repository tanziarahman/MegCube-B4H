# Architecture

How the B4H Portal is put together, how a request travels from the browser to the box and back, and the design decisions behind it.

> **Audience:** developers and administrators. For how to *use* the portal, see the [User Guide](user-guide.md).

---

## Contents

1. [System overview](#1-system-overview)
2. [Components](#2-components)
3. [Request flow](#3-request-flow)
4. [Security model](#4-security-model)
5. [Talking to the box](#5-talking-to-the-box)
6. [Live video](#6-live-video)
7. [Time and time zones](#7-time-and-time-zones)
8. [Page → backend route → box endpoint map](#8-page--backend-route--box-endpoint-map)
9. [Known issues and limitations](#9-known-issues-and-limitations)
10. [Glossary](#10-glossary)

---

## 1. System overview

The **MegCube B4H** is an AI analytics box on the local network. It pulls video from IP cameras, recognises faces against a face library, and stores every recognition and capture as a record. It has its own web UI and an undocumented JSON API (the **box API**).

The **B4H Portal** is a friendlier web front end for that box. It has three parts:

```
┌──────────┐      ┌───────────────────────┐      ┌──────────────────────┐      ┌───────────────┐
│ Browser  │ ───▶ │ Next.js frontend      │ ───▶ │ FastAPI backend      │ ───▶ │ B4H box       │
│          │      │ client/  :3000        │      │ fastapi-app/  :8000  │      │ HTTPS, LAN    │
│          │      │ • pages & UI          │      │ • box login/session  │      │ • cameras     │
│          │      │ • /api/* proxy        │      │ • /api/* REST routes │      │ • face library│
│          │      │ • adds X-API-Key      │      │ • hides passwords    │      │ • records     │
│          │ ◀─── │                       │ ◀─── │ • RTSP → MJPEG       │ ◀─── │ • RTSP streams│
└──────────┘      └───────────────────────┘      └──────────────────────┘      └───────────────┘
      │                                                     ▲
      └──── live video <img> (signed link, no proxy) ───────┘
```

| Rule | Why |
|---|---|
| The browser talks **only** to Next.js (except live video). | No CORS setup; the API key never reaches the browser. |
| The backend is the **only** thing that talks to the box. | One box session, one place that handles the box's quirks and keeps camera passwords secret. |
| Live video goes **straight** from the browser to the backend. | The Next.js proxy would buffer the endless MJPEG stream. |

---

## 2. Components

| Component | Folder | Tech | Responsibility | Reference |
|---|---|---|---|---|
| Frontend | `client/` | Next.js 15 (App Router), React 19, TypeScript, Tailwind | Pages, forms, tables; maps backend JSON to UI types | [client/README.md](../client/README.md) |
| Backend | `fastapi-app/` | Python 3.10+, FastAPI, httpx, ffmpeg | REST API for the frontend; box login, session, validation, password masking, image proxy, video conversion | [fastapi-app/README.md](../fastapi-app/README.md), [Backend API](backend-api.md) |
| B4H box | (hardware) | Vendor firmware | Cameras, face library, records, schedules | [Box API](box-api.md) |
| Database | Neon (cloud) | PostgreSQL, SQLModel, Alembic | Alarm rules, recipients, incidents, email queue, copies of box records (optional: `DATABASE_URL`) | [backend README → Database and alarms](../fastapi-app/README.md#database-and-alarms) |

### Inside the backend

| File | Role |
|---|---|
| `main.py` | App entry: startup login, error → HTTP status mapping, API-key check on every router |
| `core.py` | Shared config from `.env`, the single box client, time-zone helpers, people cache, API-key and stream-link signing |
| `b4h.py` | `B4HClient`: challenge–response login, session renewal, one-at-a-time calls, uploads, binary downloads |
| `routers/*.py` | One file per feature area; each route validates input, calls the box, reshapes the answer |
| `db.py`, `models/` | Database connection and tables (SQLModel); migrations in `migrations/` (Alembic) |
| `alarms/` | Background workers: poll box records into the database, check alarm rules, send alarm emails |

### Inside the frontend

| Path | Role |
|---|---|
| `src/app/(portal)/*/page.tsx` | One folder per page; the folder name is the URL |
| `src/components/*` | Page bodies (tables, forms, dialogs) |
| `src/lib/*.ts` | **API clients**, the only code that calls `fetch('/api/…')` |
| `src/middleware.ts` | Adds `X-API-Key` to every `/api/*` request on the Next.js server |
| `next.config.ts` | Rewrites `/api/*` to `BACKEND_URL` |

---

## 3. Request flow

Example: the user opens **Devices**.

```
Browser                    Next.js server                 FastAPI                       Box
   │ GET /api/devices/detail   │                             │                             │
   │──────────────────────────▶│ middleware: + X-API-Key     │                             │
   │                           │ rewrite → BACKEND_URL       │                             │
   │                           │────────────────────────────▶│ check_access (key OK)       │
   │                           │                             │ ensure_session (login once) │
   │                           │                             │ POST /device_access/device_config ─▶│
   │                           │                             │◀──────────── {code:0, data:[…]} ────│
   │                           │                             │ POST /device_access/device_state ──▶│
   │                           │                             │◀──────────── {code:0, data:[…]} ────│
   │                           │                             │ merge + mask passwords      │
   │                           │◀──── 200 [ {device_id,…} ] ─│                             │
   │◀──────────────────────────│                             │                             │
   │ lib/devices.ts maps snake_case → camelCase, component renders the table                │
```

What happens on failure:

| Where it fails | What the browser gets |
|---|---|
| Wrong or missing API key | `401 {"detail": "Missing or wrong API key"}` |
| Bad input (date, page size, form field) | `422`, refused before anything is sent to the box |
| Box answers with a non-zero `code` | `502 {"detail": "Box error on <path>: <message> (code N)"}` |
| Box can't be reached | `503 {"detail": "B4H box unreachable (ConnectError)"}` |
| Box connected but too slow | `504 {"detail": "The box took too long to answer. …"}` |

The frontend's `lib/*.ts` clients turn any non-2xx answer into a JavaScript `Error` carrying `detail`, and the page shows it in a red message. Full list: [Backend API → Errors](backend-api.md#13-errors).

---

## 4. Security model

| Concern | How it's handled |
|---|---|
| **Box password** | Only in `fastapi-app/.env` (`B4H_PASS`). Sent to the box as `sha256(password + salt + challenge)`, never in plain text. |
| **Box account lockout** (5 wrong passwords lock it) | Only one login runs at a time. After the box refuses the credentials once, the backend makes **no more attempts until it is restarted**. |
| **Backend API access** | With `API_KEY` set, every `/api/*` route needs header `X-API-Key`. The Next.js server adds it from `BACKEND_API_KEY`; the browser never sees it. Without `API_KEY`, the API is open (a warning is logged). |
| **Live video links** | An `<img>` can't send headers, so `/api/preview/cameras` returns a per-camera **signed token** (`exp=…&sig=…`, HMAC-SHA256 of camera id + expiry with `API_KEY`, valid 12 h). A token opens only that camera and stops working if `API_KEY` changes. |
| **Camera passwords** | The box returns them in plain text. The backend strips them (`rtsp://user:****@host/…`) before any response leaves it, and never sends them to the browser. |
| **Image proxy** | `/api/image` only serves image files under known box folders (`./record_…`, `group/…`, `/home/appdata/…`) and refuses `..`. |
| **Box TLS** | The box uses a self-signed certificate, so certificate checking is turned off **for the box connection only**. |

> **⚠️ The portal sign-in is a demo.** It accepts any username with password `admin`, and it does **not** protect pages: anyone who can open the portal URL can use it. The FastAPI docs pages (`/docs`, `/openapi.json`) are also reachable without the API key. Run the portal only on a trusted network until real authentication is added.

---

## 5. Talking to the box

All box traffic goes through one `B4HClient` (`fastapi-app/b4h.py`). The box has several quirks, and the client handles each of them:

| Box behaviour | Client handling |
|---|---|
| Login is challenge–response | `GET /auth/login/challenge` → hash → `POST /auth/login`; session sent as `Cookie: sessionID=…` |
| Idle sessions expire after ~30 s (code `512`) | Log in again and retry the call **once**. Requests that hit the expired session at the same time share **one** re-login. |
| One query at a time per session (parallel calls fail with code `1073741825`) | All calls are serialised with a lock. |
| At most 30 records per page | Routes cap `size` at 30 (`422` above). Routes that need more (dashboard, `/api/people`) page through. |
| A page past the last record gives an error, not an empty list | `alarm_history_page()` checks `total_count` and returns an empty page instead. |
| Some firmware lacks the `/system/…` time endpoints (code `404`) | Treated as empty; the portal shows its own clock instead. |
| An unknown alarm `minor_type` crashes the box's web server | Routes only accept a fixed list of minor types. |

Box endpoint details: [Box API reference](box-api.md).

---

## 6. Live video

The box's own live view needs a Windows browser plugin. The portal works around this:

1. `GET /api/preview/cameras` lists cameras with a signed `stream_token` each.
2. The browser shows `<img src="{NEXT_PUBLIC_BACKEND_URL}/api/preview/{id}/stream?hd=…&width=…&{stream_token}">`.
3. The backend reads that camera's RTSP URL from the box and starts **ffmpeg**, which converts RTSP to MJPEG (`multipart/x-mixed-replace`).
4. When the browser closes the tile, the connection drops and ffmpeg is killed.

- **SD vs HD**: for Hikvision-style URLs ending in `/channels/<n>01` (main stream), SD swaps the ending to `…02` (sub-stream). Other URLs are used as they are.
- **Limits**: at most `MAX_STREAMS` (default 16) videos at once; each is one ffmpeg process. If no frame arrives within 20 s, the request fails with `502`.

---

## 7. Time and time zones

- The box stores times as **epoch milliseconds**.
- The portal sends times as `YYYY-MM-DD HH:mm:ss` **in the box's time zone** (`BOX_TIMEZONE`, default `Asia/Dhaka`). The backend converts them, whatever the server's own time zone is.
- The frontend **displays** record times in the **browser's** time zone. Use a PC set to the same time zone as the box, or the times on screen will look shifted.

---

## 8. Page → backend route → box endpoint map

| Portal page | Backend routes | Box endpoints |
|---|---|---|
| **Dashboard** `/` | `GET /api/dashboard/summary` | `device_config`, `device_state`, `task_list`, `get_system_time`, `get_time_info`, `alarm_history` (today + yesterday) |
| **Live view** `/live` | `GET /api/preview/cameras`, `GET /api/preview/{id}/stream`, `GET /api/recognition`, `GET /api/people`, `GET /api/image` | `device_config`, `device_state`, `task_list`, RTSP (ffmpeg), `alarm_history`, `person/query`, `get_image` |
| **Recognition** `/recognition` | `GET /api/recognition`, `DELETE /api/recognition/{id}`, `GET /api/people`, `GET /api/devices`, `GET /api/image` | `alarm_history` (query, delete), `person/query`, `device_config`, `get_image` |
| **Captures** `/captures` | `GET /api/capture`, `GET /api/devices`, `GET /api/image` | `alarm_history` (with `structure` entry), `device_config`, `get_image` |
| **People** `/people` | `GET/POST /api/personnel`, `PUT/DELETE /api/personnel/{id}`, `GET /api/personnel/groups`, `GET /api/image` | `face_manager/groups/query`, `face_manager/person[/query]`, `face_manager/person_bind`, `get_image` |
| **Devices** `/devices` | `GET /api/devices/detail`, `POST /api/devices`, `PUT/DELETE /api/devices/{id}` | `device_config` (read, update), `device_state`, `device` (add, delete) |
| **Time plans** `/timeplans` | `GET /api/timeplans/time`, `GET /api/timeplans/regular`, `GET /api/timeplans/festival`, `POST /api/timeplans`, `PUT/DELETE /api/timeplans/{id}` | `get_system_time`, `get_time_info`, `schedule_plan/query`, `schedule_plan` (create, update, delete) |
| **Alarms** `/alarms`, `/alarms/{id}` | `/api/alarms/*` (rules, contacts, incidents, status, test email) | none directly; the background worker uses `alarm_history` (recognition + capture queries) and `device_config`, and `get_image` for email snapshots |
| **People counting**, **Settings** | none (placeholder pages) | not captured yet |

---

## 9. Known issues and limitations

Found while verifying these docs against the code (2026-10-01). Each is a candidate for a ticket.

| # | Area | Issue | Effect |
|---|---|---|---|
| 1 | Security | The sign-in is a demo and doesn't guard pages; `/docs` and `/openapi.json` are open without the API key. | Anyone on the network who can reach the portal can use it. |
| 2 | People | An empty group selection leaves groups unchanged (as in the box's own UI), so a person can't be removed from **all** groups. The box request for "no groups" hasn't been captured. | Use the box UI to clear all groups. |
| 3 | People | `/api/personnel` is called with `get_feature=true`, so the box includes large face-feature data the page doesn't use. Not changed yet: it isn't confirmed that the photo path still comes back with `false`. | Slower People page. |
| 4 | Recognition / Captures | Camera and track-ID filters only filter the page already loaded; the box has no confirmed device filter. | Results can look incomplete; the page says so. |
| 5 | Top bar | Search only opens People; the **Demo data**, **Devices 20 / 24** and **Live** chips are fixed values. (The sidebar Alarms badge is real: open alarms, refreshed every minute.) | Not real data. |
| 6 | Devices | Picture devices and GB28181 cameras can't be added or edited; their box requests haven't been captured. | Use the box's own web UI. |

**Fixed on 2026-10-01:** `DELETE /api/timeplans/stream-subscriptions` was shadowed by the `{plan_id}` route (always `422`); Captures **Refresh** did nothing on page 1; Live view's "Latest recognitions" paged through the whole day every 5 s (now one request); editing a person reset their gender to `0`; misleading Time plans messages. The route-order and Refresh fixes have regression tests (`tests/test_timeplan.py`, `CapturesView.test.tsx`).

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **Box** | The MegCube B4H analytics device |
| **Alarm / record** | Anything the box logs: a recognition, a stranger, a face or body capture. All are stored as "alarms" with a `major_type` / `minor_type`. |
| **Recognition (matched)** | A face that matched someone in the face library (`face_comparison_successful`) |
| **Stranger** | A face that matched nobody in the library |
| **Capture** | A face or body crop the box saved, whether or not it was recognised |
| **Face library** | The box's list of known people, each with a reference photo, optionally in **groups** |
| **Track ID** | The id the box gives one person's continuous path through one camera's view |
| **Similarity** | How closely a face matches the library photo (0–100) |
| **Liveness / living fraction** | How likely the face is a real, live person rather than a photo or screen (0–100) |
| **Panoramic image** | The full camera frame the crop was taken from |
| **Main stream / sub-stream** | A camera's full-resolution video / its lighter, lower-resolution copy |
| **Task** | An analysis job on the box (e.g. face recognition) bound to one or more cameras |
| **Time plan** | A weekly schedule of time windows that says when the box's rules are active. **Regular** plans repeat weekly; **festival** plans cover special days. |
