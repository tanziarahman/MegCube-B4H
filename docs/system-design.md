# B4H Portal: System Design

How the B4H Portal is built: its layers, the parts inside each layer, how they're connected, and why it was designed this way. It is written in plain language for readers new to the project.

> Read the [Project overview](project-overview.md) first for what the project does and how data flows. This document covers **how it is built**.

---

## 1. Design goals

The design follows from five goals:

| Goal | What it means for the design |
|---|---|
| **Work with a closed box** | The B4H box has no public API documentation and some odd behaviour. All contact with it goes through **one** place in our code, so its quirks are handled once. |
| **Keep secrets safe** | Box and camera passwords never reach a browser. |
| **Add features the box lacks** | Alarms, people counting and fast dashboard totals need **our own database** and a **background worker**. |
| **Stay usable when parts fail** | If the box, Redis or the database is down, the rest of the portal keeps working where it can. |
| **Be simple to run** | One backend process, one website, one cloud database. Redis is optional. |

---

## 2. Layers

The system has four layers. Each layer talks only to the one next to it.

```
┌──────────────────────────────────────────────────────────────┐
│ 1. PRESENTATION      Browser + Frontend (Next.js website)    │   what people see
├──────────────────────────────────────────────────────────────┤
│ 2. APPLICATION       Backend (FastAPI, Python)               │   rules, logic, security
│                      • API routes  • background worker       │
├──────────────────────────────────────────────────────────────┤
│ 3. DATA              PostgreSQL database · Redis cache        │   our own data
├──────────────────────────────────────────────────────────────┤
│ 4. EXTERNAL          B4H box · cameras · email server         │   things we don't own
└──────────────────────────────────────────────────────────────┘
```

| Layer | Runs where | Technology |
|---|---|---|
| Presentation | User's browser, plus a small Next.js server on the portal PC | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Application | The portal PC (same network as the box) | Python, FastAPI, httpx, ffmpeg, OpenCV |
| Data | Neon (cloud PostgreSQL); Redis on the portal PC (optional) | PostgreSQL, SQLModel, Alembic, Redis |
| External | Site network; any SMTP mail server | B4H box firmware, IP cameras (RTSP) |

---

## 3. Components and how they connect

```
                         ┌───────────────────────────┐
   Browser ── HTTP ────▶ │ Next.js server (:3000)    │
      │                  │  • serves the pages       │
      │                  │  • forwards /api/* calls  │
      │                  │  • adds the secret API key│
      │                  └─────────────┬─────────────┘
      │                                │ HTTP + API key
      │  live video                    ▼
      │  (signed link)   ┌───────────────────────────────────────────────┐
      └────────────────▶ │ FastAPI backend (:8000)                       │
                         │                                               │
                         │  API routes ─────┐      Background worker     │
                         │  (one per page)  │      (every 5 s)           │
                         │                  ▼             │              │
                         │            ┌──────────┐        │              │
                         │            │Box client│◀───────┘              │
                         │            └────┬─────┘                       │
                         └─────────┬───────┼──────────┬──────────┬───────┘
                                   │       │ HTTPS    │          │ SMTP
                              ┌────┴───┐ ┌─┴─────┐ ┌──┴───┐ ┌────┴────────┐
                              │Database│ │B4H box│ │Redis │ │Email server │
                              └────────┘ └───┬───┘ └──────┘ └─────────────┘
                                             │ RTSP
                                         Cameras ◀── ffmpeg (live video) ── backend
```

| Connection | Protocol | Why this way |
|---|---|---|
| Browser → Next.js | HTTP | The browser sees only our website, so there are no cross-site security issues |
| Next.js → Backend | HTTP with a secret key header | The key stays on the server and only our website can call the backend |
| Browser → Backend (video only) | HTTP with a signed link | A video tag can't send a key header; the signed link works for one camera for 12 hours |
| Backend → Box | HTTPS, JSON | The box's own API, worked out by watching its web page |
| Backend → Cameras | RTSP, via ffmpeg | Converts camera video into a format any browser can play |
| Backend → Database | PostgreSQL protocol | Stores our own data |
| Backend → Redis | Redis protocol | Short-lived Dashboard cache |
| Backend → Email server | SMTP | Sends alarm emails |

---

## 4. Inside the frontend

The frontend is organised so that each page is self-contained and only one kind of file talks to the backend.

```
client/src/
├─ app/          one folder per page (the folder name is the web address)
├─ components/   what each page shows: tables, forms, charts, dialogs
├─ lib/          API clients: the ONLY code that calls the backend
├─ hooks/        small shared helpers (e.g. the sidebar alarm count)
├─ config/       sidebar menu
└─ middleware.ts adds the secret key to every /api call
```

| Design choice | Why |
|---|---|
| Only `lib/` calls the backend | One place to change if an API changes; pages stay simple |
| `lib/` converts backend data into page-friendly shapes | Pages don't depend on the box's odd field names |
| Small preferences live in the browser (filters, drafts, sidebar state) | No server needed for personal settings |
| Pages refresh themselves where it matters (Dashboard 45 s, Alarms 30 s, Live recognitions 5 s, Counting 1 min) | Near-live data without the extra complexity of push connections |

---

## 5. Inside the backend

The backend is one Python program with two jobs running side by side:

1. **Answering requests** from the website (API routes).
2. **Background work** that runs on its own (the worker and the email sender).

```
fastapi-app/
├─ main.py          starts everything; turns errors into clear messages
├─ core.py          settings, shared helpers, security checks
├─ b4h.py           BOX CLIENT: the only code that talks to the box
├─ routers/         one file per page: checks input, calls the box or database, shapes the answer
├─ alarms/          background worker: read box records, check rules, send emails
├─ counting/        build walk-pasts and people-counting numbers
├─ faces/           face and clothing fingerprints, and grouping walk-pasts into people
├─ dashboard_data/  dashboard totals from the database, or from the box as a fallback
├─ cache.py         optional Redis cache
├─ db.py, models/   database connection and table definitions
└─ migrations/      step-by-step database changes (Alembic)
```

### The box client (`b4h.py`)

All box traffic goes through this one class. It deals with the box's quirks:

| Box behaviour | How the client handles it |
|---|---|
| Login uses a challenge (password is never sent as plain text) | Does the challenge once, then reuses the session |
| Sessions expire after about 30 seconds of idle time | Logs in again automatically and retries once |
| The box can only handle one request at a time | Queues requests so only one runs at a time |
| Five wrong passwords lock the box account | After one refused login, stops trying until restarted |
| The box returns at most 30 records per request | Routes page through results when they need more |

### The background worker (`alarms/worker.py`)

Started with the backend when a database is configured. It has two loops:

| Loop | Every | Does |
|---|---|---|
| **Ingest loop** | 5 s | Reads new box records → saves them → builds walk-pasts and dashboard totals → checks alarm rules → queues emails. Then makes fingerprints for new walk-pasts. Re-syncs the camera list every 10 minutes. |
| **Mail loop** | 5 s | Sends queued emails with the snapshot attached; retries failures (up to 5 tries, waiting longer each time) |

Because the worker runs inside the backend, **the backend must run as a single process**. Two copies would process every record twice.

---

## 6. Data design

### Where the truth lives

| Data | Source of truth | Copy kept by us? |
|---|---|---|
| People, cameras, schedules | **Box** | No. Always read live from the box. |
| Recognition and capture records | **Box** | Yes. A copy goes in the database for alarms, counting and the dashboard. |
| Pictures | **Box** | No. Only their location is stored; pictures are fetched when needed. |
| Alarm rules, recipients, alarms, emails | **Database** | n/a (ours) |
| Walk-pasts, fingerprints, totals | **Database** | n/a (worked out from the copied records) |

### Database tables, by purpose

| Group | Tables | Holds |
|---|---|---|
| **Reference** | `boxes`, `cameras`, `contacts` | The box, a copy of its camera list (with counting settings), email recipients |
| **Copied records** | `events`, `ingest_cursors` | Every box record, saved once; where reading left off for each record type |
| **Alarms** | `alarm_rules` (+ `_cameras`, `_windows`, `_targets`, `_recipients`, `_state`), `incidents`, `incident_events`, `notifications` | Rules and their parts; alarms that fired; which records belong to each alarm; the email queue and its delivery status |
| **People counting** | `sightings`, `count_buckets` | Walk-pasts (with fingerprints); totals per camera per 15 minutes |
| **Dashboard** | `daily_stats` (+ extra columns in `count_buckets`) | Per-day numbers that can't simply be added up, such as different people recognised |
| **Admin** | `audit_log` | Who changed what (rules, alarms, settings) |
| **Reserved for later** | `push_inbox`, `stranger_profiles`, `app_settings` | Created but not used yet: for receiving records pushed by the box, remembering strangers, and editable settings |

Database changes are made with **migrations** (Alembic): each change is a small script, applied in order with one command. This keeps every copy of the database in step with the code.

### Keeping numbers correct

- Each box record has a unique key, so **re-reading it never creates a duplicate**.
- Saving a record, building its walk-past, updating totals and creating its alarm happen in **one transaction**: either all of it is saved, or none of it is.
- Totals are **recounted** from the records rather than added to, so they can't drift over time.

---

## 7. Performance design

| Problem | Design |
|---|---|
| The box is slow: one request at a time, at most 30 records each | Daily totals are worked out in the background and stored, so the Dashboard reads a few rows instead of thousands of records |
| Many people refreshing the Dashboard | Results are kept in Redis: 15 s for today and camera status, 1 hour for past days |
| Grouping walk-pasts into people takes processing time | It runs in a separate thread, so other requests aren't held up; very long periods (over 2,000 walk-pasts) are refused |
| Fingerprinting pictures is slow | Done in the background, about 40 walk-pasts per cycle, oldest first (the box deletes old pictures) |
| Live video uses a lot of resources | At most 16 streams at once; grids use the lighter sub-stream |

---

## 8. Reliability: what happens when something fails

| If this fails… | The portal… |
|---|---|
| **Box** unreachable | Shows a clear error on box pages. The worker waits and retries, then catches up on missed records. Alarms for late records are marked *delayed*. |
| **Box** login refused | Stops trying (to avoid locking the account) and shows a message until an admin fixes the password and restarts. |
| **Database** not set up or down | Box pages still work. Alarms and People counting show a "needs the database" message. The Dashboard falls back to the box. |
| **Redis** not set up or down | Treated as "nothing cached": everything still works, just slower. After an error, Redis is skipped for 30 s. |
| **Email server** refuses | Alarms are still saved. Emails are retried, and failures are shown on the alarm. |
| **Face models** not installed | People counting still counts walk-pasts. "Different people" then equals walk-pasts, with a note on the page. |
| The backend **crashes** mid-way | Nothing half-saved: the transaction is undone and the records are re-read on the next cycle. |

Errors are turned into clear messages with standard status codes. For example, `503` with *"B4H box unreachable"*, shown in red on the page.

---

## 9. Security design

| Threat | Protection |
|---|---|
| Someone calls the backend directly | Every `/api` route needs the secret key, which only the Next.js server has |
| Box password leaks | Stored only in the backend's settings file; sent to the box as a hash, never as plain text |
| Camera passwords leak | Removed from every answer before it leaves the backend |
| Someone shares a video link | Links are signed, limited to one camera and expire after 12 hours |
| Someone fetches arbitrary files through the picture route | Only known picture folders on the box are allowed |
| **Not yet protected** | The sign-in page is a demo and doesn't guard pages. Use the portal only on a trusted network until real accounts are added. |

---

## 10. Testing design

| Level | Tool | Needs the box? |
|---|---|---|
| Backend logic and routes | pytest, with a **fake box** that answers like the real one and records what was asked | No |
| Database logic (alarms, counting) | pytest against a throwaway test database | No |
| Frontend pages and components | Vitest + Testing Library, with **MSW** faking the backend | No |
| Whole website in a real browser | Playwright | No |
| Real-box check | A read-only script that only reads from the box | Yes (read-only) |

The fake box and fake backend let the tests run anywhere, at any time, without touching the shared real box.

---

## 11. Running it

```
Portal PC (on the site network)                 Cloud
┌──────────────────────────────────────┐        ┌──────────────────┐
│ Next.js website      :3000           │        │ Neon PostgreSQL  │
│ FastAPI backend      :8000  (1 copy) │ ─────▶ │ database         │
│ ffmpeg (for live video)              │        └──────────────────┘
│ Redis (optional)     :6379           │
└──────────────┬───────────────────────┘
               │ site network
        B4H box ── cameras
```

- Settings (box address and password, API key, database address, email server) live in `.env` files, never in the code.
- The backend must run as **one process**, because the background worker runs inside it.
- Setup steps: [main README](../README.md) and [backend README](../fastapi-app/README.md).

---

## 12. Known limits and possible next steps

| Limit | Possible next step |
|---|---|
| Demo sign-in, no user accounts | Add real accounts and roles |
| One backend process only | Move the background worker into its own service |
| One box | The database already has a `boxes` table, so more boxes could be added |
| Records are read every 5 s (polling) | Let the box push records to us (`push_inbox` is ready for this) |
| "Different people" is an estimate | Better camera angles, or more face-library enrolment |
| Some box features not worked out (Picture/GB28181 cameras, Settings) | Capture those box requests and add them |

---

## Further reading

- [Project overview](project-overview.md): what the project does and how data flows
- [Architecture](architecture.md): technical detail for developers
- [Backend API](backend-api.md) and [Box API](box-api.md): every endpoint
- [User Guide](user-guide.md): how to use each page
