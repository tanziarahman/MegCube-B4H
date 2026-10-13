# B4H Portal: How the Project Works

What the B4H Portal is, where its data comes from, and how that data moves. No prior knowledge needed.

---

## 1. What the project is

A site has **IP cameras** connected to a **MegCube B4H box**, a third-party AI device. The box watches the video, recognises known faces, and saves a record of everything it sees.

The box has its own web page, but it is hard to use. Its live video needs a Windows-only plugin, and it offers no alarm emails or people counting we could use.

**The B4H Portal is our own website built on top of the box.** It:

- shows the box's data more clearly (dashboard, records, live video)
- lets staff manage the box (people, cameras, schedules)
- adds new features: **alarm emails**, **people counting** and a **fast dashboard**

---

## 2. The parts

| Part | Its job |
|---|---|
| **Cameras** | Send video to the box |
| **B4H box** | Recognises faces and saves records and pictures. **The source of all original data.** |
| **Backend** (our server, Python) | The only part that talks to the box. Fetches data, runs background jobs, sends emails. |
| **Frontend** (our website) | The pages people use in their browser |
| **Database** (cloud) | Stores our own data: copies of box records, alarm rules, alarms, counting results, dashboard totals |
| **Cache** (optional) | Remembers recent Dashboard results briefly, so the page loads fast |
| **Email server** | Delivers alarm emails |

---

## 3. The big picture

```
 Cameras ──video──▶ B4H BOX ◀──────── requests ───────┐
                       │                               │
                       └── records, pictures, video ──▶ BACKEND ──▶ Database
                                                       │  ▲  │
 Browser ◀──── pages ────▶ Frontend ◀─────────────────┘  │  ├──▶ Cache
    ▲                                                     │  └──▶ Email server
    └──────────────────── live video ─────────────────────┘
```

Three rules:

1. The browser only talks to our website, never to the box.
2. Only the backend talks to the box. This keeps all passwords secret.
3. Live video is the exception: it goes straight from the backend to the browser.

---

## 4. Where the data comes from

**From the box** (original data):

| Data | Example |
|---|---|
| Recognition records | "Camera 2 saw Ada at 09:14, 96% match", or "saw a stranger" |
| Capture records | Every face or body picture the box saved |
| Pictures | Face, body and full-scene images (the box deletes old ones over time) |
| Face library | Known people, with photos and groups |
| Cameras | Names, addresses, online/offline |
| Schedules | Time plans, e.g. office hours |

Live video comes **from the cameras**, using addresses stored on the box.

**Created by the portal** (stored in our database):

- alarm rules and email recipients (entered by staff)
- alarms and email history
- copies of box records, and the walk-pasts and dashboard totals worked out from them

---

## 5. How the data flows

### Flow A: Viewing or changing box data

Used by **Recognition, Captures, People, Devices and Time plans**.

```
Page ─▶ Backend ─▶ Box ─▶ Backend tidies the answer ─▶ Page shows it
```

The backend logs in to the box once, asks for the data, hides passwords, fixes times, and sends it to the page. Changes go the other way. For example, adding a person sends the photo to the box, and the box starts recognising them. **Nothing is stored in our database for these pages.** Pictures are also fetched from the box through the backend.

### Flow B: Live video

```
Camera ─▶ Backend (converts the video) ─▶ Browser
```

The backend converts each camera's video into a format any browser can play. Each video link only works for one camera, for 12 hours. Up to 16 videos can play at once.

### Flow C: The background worker

This runs inside the backend **every 5 seconds**, even when nobody has the portal open. It powers alarms, people counting and the dashboard totals.

```
Box ─▶ 1. Read new records
       2. Save each one once in the database
       3. Group a person's records into one "walk-past"   (people counting)
       4. Update the day's totals                         (dashboard)
       5. Check alarm rules ─▶ match? ─▶ 6. Create alarm ─▶ 7. Email recipients
       8. Make face and clothing "fingerprints"           (people counting)
```

- **Steps 2–6 succeed or fail together**, so a record is never half-processed and an alarm is never sent twice.
- **Alarm rules** check three things: right camera, right person (anyone, strangers, known people, or chosen people/groups), right time.
- **Quiet period:** after an alarm, more detections join the same alarm for 5 minutes instead of sending more emails.
- **Emails** go out with the snapshot attached and are retried if they fail.
- **If the box goes offline**, the worker catches up when it's back. Late alarms are marked *delayed* and aren't emailed by default.

### Flow D: Pages that read our database

- **Dashboard:** uses the cache if it has a recent answer. Otherwise it reads the day's totals from the database, or counts from the box for days the database doesn't have. Camera status always comes live from the box.
- **People counting:** reads walk-pasts from the database. It compares their fingerprints (clothing and face) and treats look-alikes as one person. The result is an estimate with a range, e.g. **≈ 7, likely 6–10**.
- **Alarms:** rules, recipients and alarms are all in the database. The box isn't involved.

---

## 6. Every feature: data source and API calls

**Our API** is what the website asks the backend. **Box API** is what the backend then asks the box. Full details: [Backend API](backend-api.md), [Box API](box-api.md).

| Feature | Our API | Box API / source | What comes back |
|---|---|---|---|
| **Sign in** | none (checked in the browser; demo password `admin`) | none | — |
| **Dashboard** | `GET /api/dashboard/summary` | Box: camera list, camera status, tasks, clock. Database: daily totals. | Today's recognitions, strangers and captures, compared with yesterday; hourly activity; match quality; top people; latest events; camera status; problems |
| **Live view** | `GET /api/preview/cameras`, `/api/preview/{id}/stream` | Box: camera list and status; then the camera's video | Camera list with video links; the live video |
| **Recognition** | `GET` / `DELETE /api/recognition`, `GET /api/people`, `GET /api/devices` | Box: `alarm_history`, face library, camera list | Matched or stranger records: camera, time, match %, name, group, pictures |
| **Captures** | `GET /api/capture` | Box: `alarm_history` | Face and body captures: camera, time, track, pictures |
| **People** | `GET` / `POST` / `PUT` / `DELETE /api/personnel`, `/api/personnel/groups` | Box: face library | People: name, photo, code, groups |
| **Devices** | `GET /api/devices/detail`, `POST` / `PUT` / `DELETE /api/devices` | Box: camera list and status | Cameras: name, address (password hidden), online |
| **Time plans** | `GET /api/timeplans/...`, `POST` / `PUT` / `DELETE /api/timeplans` | Box: schedules, clock | Plans with weekly time windows; box clock |
| **Pictures** | `GET /api/image` | Box: `get_image` | The picture (JPEG) |
| **Alarms** | `/api/alarms/rules`, `/contacts`, `/incidents`, `/status`, `/test-email` | Database only | Rules, recipients, alarms (with detections and email status), open-alarm count |
| **People counting** | `/api/counting/summary`, `/series`, `/heatmap`, `/sightings`, `/cameras` | Database only | Walk-pasts, different people (estimate), charts, busy times, the list of walk-pasts |
| **Background worker** | (no page) | Box: `alarm_history` every 5 s, camera list every 10 min, pictures. Email server. | Fills the database; sends alarm emails |
| **Settings** | not built yet | — | — |

---

## 7. Where data is stored

| Where | What | How long |
|---|---|---|
| **Box** | Records, pictures, face library, cameras, schedules | Until deleted or overwritten by the box |
| **Database** | Copies of records (no pictures), walk-pasts, totals, alarm rules, alarms, emails, a log of changes | Permanently |
| **Cache** | Recent Dashboard answers | 15 seconds to 1 hour |
| **Browser** | Filters, unsaved drafts, layout preferences | On that computer only |

Pictures are never copied. The database stores where each picture is on the box, and the picture is fetched when needed.

---

## 8. Security

- Box and camera passwords stay on the backend and never reach a browser.
- Only our website can call the backend (it uses a secret key).
- Video links work for one camera, for 12 hours.
- **Limitation:** the sign-in is a demo. Use the portal only on a trusted internal network until real accounts are added.

---

## 9. What the portal adds

| Feature | Box alone | With the portal |
|---|---|---|
| Live video | Windows-only plugin | Any browser, up to 9 cameras |
| Records | Hard-to-use lists | Search, filters, details |
| Alarms | Not available to us | Custom rules and emails |
| People counting | Not available to us | Walk-pasts, different people, busy times |
| Daily overview | None | Dashboard |
| Speed | One request at a time | Stored totals and caching |

---

## Further reading

- [System design](system-design.md): how it's built
- [User Guide](user-guide.md): how to use each page
- [Architecture](architecture.md): technical detail for developers
- [Contributions](contributions.md): who built what
