# Backend API Reference

Every endpoint the FastAPI backend (`fastapi-app/`) exposes to the frontend: what you send, what you get back, what can go wrong, and which box calls happen behind it.

> **Audience:** frontend and backend developers, and anyone scripting against the portal.
> For the box's own endpoints, see the [Box API reference](box-api.md). For the big picture, see [Architecture](architecture.md).

The backend also generates interactive docs at **`http://localhost:8000/docs`** (Swagger UI). This file adds what Swagger can't show: response shapes, the box calls behind each route, and the reasons behind the behaviour.

---

## Contents

1. [Conventions](#1-conventions)
2. [Endpoint summary](#2-endpoint-summary)
3. [Health](#3-health)
4. [Dashboard](#4-dashboard)
5. [Devices (cameras)](#5-devices-cameras)
6. [Live preview](#6-live-preview)
7. [Recognition records](#7-recognition-records)
8. [Capture records](#8-capture-records)
9. [Face library: people list](#9-face-library-people-list)
10. [Face library: personnel management](#10-face-library-personnel-management)
11. [Time plans](#11-time-plans)
12. [Images](#12-images)
13. [Errors](#13-errors)
14. [Frontend client map](#14-frontend-client-map)
15. [Alarms](#15-alarms)
16. [People counting](#16-people-counting)

---

## 1. Conventions

| Item | Value |
|---|---|
| Base URL (direct) | `http://localhost:8000` |
| Base URL (from the browser) | Same origin as the frontend, e.g. `http://localhost:3000/api/…`. Next.js forwards it to the backend. |
| Format | JSON in and out, except: `POST/PUT /api/personnel` take `multipart/form-data`, `/api/image` returns image bytes, `/api/preview/{id}/stream` returns MJPEG. |
| Field names | `snake_case` |
| Times sent **to** the backend | `"YYYY-MM-DD HH:mm:ss"` in the **box's time zone** (`BOX_TIMEZONE`) |
| Times **returned** | Epoch milliseconds (number or numeric string, as the box sent it), or `"YYYY-MM-DD HH:mm:ss"` where noted |
| Paging | `page` (1-based, default `1`) and `size` (default `10`, **max `30`**: the box refuses more) |

### Authentication

When `API_KEY` is set in `fastapi-app/.env`, every `/api/*` request must include:

```http
X-API-Key: <API_KEY>
```

- The browser never sends this itself. `client/src/middleware.ts` adds it on the Next.js server.
- **Exception:** `GET /api/preview/{id}/stream` also accepts a signed link (`?exp=…&sig=…`) instead of the header. See [6.2](#62-get-apipreviewdevice_idstream).
- Missing or wrong key → `401 {"detail": "Missing or wrong API key"}`.
- `GET /` (health) needs no key.

Calling the backend directly with curl:

```bash
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/api/devices/detail"
```

---

## 2. Endpoint summary

| Method | Path | Purpose | Used by page |
|---|---|---|---|
| GET | [`/`](#3-health) | Health check | — |
| GET | [`/api/dashboard/summary`](#41-get-apidashboardsummary) | Today's activity, camera health, attention list | Dashboard |
| GET | [`/api/devices/detail`](#51-get-apidevicesdetail) | Cameras with type, masked address and status | Devices |
| GET | [`/api/devices`](#52-get-apidevices) | Camera id + name only | Recognition, Captures |
| POST | [`/api/devices`](#53-post-apidevices) | Add a camera | Devices |
| PUT | [`/api/devices/{device_id}`](#54-put-apidevicesdevice_id) | Edit a camera | Devices |
| DELETE | [`/api/devices/{device_id}`](#55-delete-apidevicesdevice_id) | Remove a camera | Devices |
| GET | [`/api/preview/cameras`](#61-get-apipreviewcameras) | Cameras for live view + signed stream tokens | Live view |
| GET | [`/api/preview/{device_id}/stream`](#62-get-apipreviewdevice_idstream) | Live MJPEG video | Live view |
| GET | [`/api/recognition`](#71-get-apirecognition) | One page of matched or stranger records | Recognition, Live view |
| DELETE | [`/api/recognition/{alarm_id}`](#72-delete-apirecognitionalarm_id) | Delete one recognition record | Recognition |
| GET | [`/api/capture`](#81-get-apicapture) | One page of face/body captures | Captures |
| GET | [`/api/people`](#91-get-apipeople) | Whole face library (id + name), cached | Recognition, Live view |
| GET | [`/api/personnel/groups`](#101-get-apipersonnelgroups) | Face-library groups | People |
| GET | [`/api/personnel`](#102-get-apipersonnel) | One page of people with details | People |
| POST | [`/api/personnel`](#103-post-apipersonnel) | Add a person (multipart, with photo) | People |
| PUT | [`/api/personnel/{person_id}`](#104-put-apipersonnelperson_id) | Edit a person (multipart, photo optional) | People |
| DELETE | [`/api/personnel/{person_id}`](#105-delete-apipersonnelperson_id) | Delete a person | People |
| GET | [`/api/timeplans/time`](#111-get-apitimeplanstime) | Box clock and time settings | Time plans |
| GET | [`/api/timeplans/regular`](#112-get-apitimeplansregular-and-apitimeplansfestival) | Regular (weekly) plans | Time plans |
| GET | [`/api/timeplans/festival`](#112-get-apitimeplansregular-and-apitimeplansfestival) | Festival plans | Time plans |
| POST | [`/api/timeplans`](#113-post-apitimeplans) | Create a plan | Time plans |
| PUT | [`/api/timeplans/{plan_id}`](#114-put-apitimeplansplan_id) | Update a plan | Time plans |
| DELETE | [`/api/timeplans/{plan_id}`](#115-delete-apitimeplansplan_id) | Delete a plan | Time plans |
| DELETE | [`/api/timeplans/stream-subscriptions`](#116-delete-apitimeplansstream-subscriptions) | Close box stream subscriptions | — (not used yet) |
| GET | [`/api/image`](#121-get-apiimage) | Proxy a record or face-library image | All pages with pictures |
| GET | [`/api/alarms/status`](#151-get-apialarmsstatus) | Alarm workers, email setup, open-alarm count | Alarms, sidebar badge |
| GET | [`/api/alarms/cameras`](#152-get-apialarmscameras) | Cameras rules can watch | Alarms |
| GET/POST/PUT/DELETE | [`/api/alarms/contacts[/{id}]`](#153-recipients) | Email recipients | Alarms |
| POST | [`/api/alarms/test-email`](#153-recipients) | Send a test email | Alarms |
| GET/POST/PUT/PATCH/DELETE | [`/api/alarms/rules[/{id}]`](#154-rules) | Alarm rules | Alarms |
| GET | [`/api/alarms/incidents`](#155-get-apialarmsincidents) | Alarms that fired | Alarms |
| GET | [`/api/alarms/incidents/{ref}`](#156-get-apialarmsincidentsref) | One alarm with detections and emails | Alarm detail |
| PATCH | [`/api/alarms/incidents/{id}`](#157-patch-apialarmsincidentsid) | Acknowledge, resolve, note | Alarms, Alarm detail |
| GET | [`/api/counting/summary`](#162-get-apicountingsummary) | Walk-pasts, visits, different people, per camera | People counting |
| GET | [`/api/counting/series`](#163-get-apicountingseries) | Walk-pasts over time | People counting |
| GET | [`/api/counting/heatmap`](#164-get-apicountingheatmap) | Busy times (weekday × hour) | People counting |
| GET | [`/api/counting/sightings`](#165-get-apicountingsightings) | The walk-pasts behind the numbers | People counting |
| GET/PATCH | [`/api/counting/cameras[/{id}]`](#166-camera-settings) | Which cameras count, and how | People counting |

---

## 3. Health

### `GET /`

No API key needed. Use it to check that the backend process is up. It does **not** check the box.

**Response `200`**

```json
{ "message": "Hello World" }
```

---

## 4. Dashboard

### 4.1 `GET /api/dashboard/summary`

Everything the Dashboard page shows, in one response: today's totals, comparisons with yesterday, trends, camera readiness and an attention list.

**Query parameters**

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `date` | `YYYY-MM-DD` | no | today in `BOX_TIMEZONE` | The box-local day to summarise |

**Response `200`**

```json
{
  "date": "2026-09-29",
  "generated_at": "2026-09-29T14:30:00",
  "period": {
    "start": "2026-09-29 00:00:00", "end": "2026-09-29 23:59:59",
    "previous_start": "2026-09-28 00:00:00", "previous_end": "2026-09-28 23:59:59"
  },
  "health": {
    "devices_total": 2, "devices_online": 1, "devices_offline": 1,
    "streams_pulling": 1, "tasks_total": 1,
    "clock": { "time": "2026-09-29 14:30:00", "time_zone": "Asia/Dhaka", "source": "box" }
  },
  "activity": {
    "matched": 12, "strangers": 3, "captures": 30,
    "face_captures": 20, "body_captures": 10, "capture_breakdown_limited": false,
    "previous_matched": 8, "previous_strangers": 4, "previous_captures": 25
  },
  "insights": {
    "peak_hour": 14,
    "busiest_device_id": "1", "busiest_device": "Entrance camera",
    "average_match_score": 91.2,
    "low_confidence_count": 1, "low_liveness_count": 0,
    "tracked_encounters": 30, "face_encounters": 20, "body_encounters": 10,
    "unique_recognized_people": 4, "recognized_encounters": 12, "stranger_encounters": 3,
    "recognized_capture_tracks": 12, "recognition_coverage_percent": 60.0,
    "busiest_capture_device": "Entrance camera",
    "analysis_sampled": 15, "analysis_limited": false,
    "top_people": [ { "name": "Ada Lovelace", "count": 8 } ],
    "hourly_activity": [ { "hour": 0, "count": 0 }, "… 24 entries, hours 0–23 …" ],
    "events": [
      { "id": "101", "type": "matched", "person": "Ada Lovelace", "device_id": "1",
        "device": "Entrance camera", "time_ms": 1760000000000, "score": 98.0 }
    ]
  },
  "devices": [
    { "id": 1, "name": "Entrance camera", "online": true,  "state_code": 0, "pulling_stream": true,  "task": "FR" },
    { "id": 2, "name": "Loading bay",     "online": false, "state_code": 3, "pulling_stream": false, "task": null }
  ],
  "attention": [
    { "severity": "critical", "type": "offline_camera", "message": "Loading bay is offline", "device_id": 2 }
  ]
}
```

**Field reference**

| Field | Meaning |
|---|---|
| `health.clock.source` | `"box"` if both box time endpoints answered, otherwise `"unavailable"` (then `time` / `time_zone` may be `null`) |
| `activity.matched` / `strangers` / `captures` | **Exact** totals for the day, from the box's `total_count` |
| `activity.face_captures` / `body_captures` | Counted from the records read (see `capture_breakdown_limited`) |
| `activity.capture_breakdown_limited` | `true` if there were more than 5,000 captures, so the face/body split covers only the first 5,000 |
| `activity.previous_*` | Yesterday's totals, for "vs yesterday" |
| `insights.peak_hour` | Hour (0–23, box time) with most matched + stranger records; `null` if none |
| `insights.average_match_score` | Mean similarity of matched + stranger records (0–100); `null` if none had a score |
| `insights.low_confidence_count` | Records with similarity **< 70** |
| `insights.low_liveness_count` | Records with liveness **< 80** (a possible photo or screen held up to the camera) |
| `insights.top_people` | Up to 5 most-recognised names |
| `insights.events` | The 8 latest matched/stranger events. `type` is `"matched"` or `"stranger"`. |
| `insights.tracked_encounters` | Unique captures, counted once per **camera + track id** |
| `insights.unique_recognized_people` | Distinct face-library people matched (by person id, else name) |
| `insights.recognized_encounters` / `stranger_encounters` | Unique camera + track pairs among matched / stranger records |
| `insights.recognition_coverage_percent` | Share of face-capture tracks that were also recognised; `null` if no face captures |
| `insights.analysis_sampled` | How many records the trend figures are based on |
| `insights.analysis_limited` | `true` if any category hit the 5,000-record cap: trend figures use a sample, totals stay exact |
| `devices[]` | One row per camera: `online` = box state `0`; `pulling_stream` = any channel pulling; `task` = analysis task name or `null` |
| `attention[]` | Problems, critical first. `type` is one of `offline_camera` (critical), `stream_not_pulling`, `no_task`, `clock_unavailable` (all warning). |

Scores the box sends as fractions (0–1) are converted to 0–100.

**Errors**

| Status | When |
|---|---|
| `422` | `date` isn't `YYYY-MM-DD`. Nothing is sent to the box. |
| `502` / `503` / `504` | See [Errors](#13-errors) |

**Box calls (in order):** `device_config`, `device_state`, `task_list`, `get_system_time`, `get_time_info`; then `alarm_history` paged (30 per call, up to 5,000 records) for today's matched, strangers and captures; then one `alarm_history` call (size 1) each for yesterday's totals.

> **Performance:** the box answers one request at a time, so a busy day can mean hundreds of box calls. This is the slowest endpoint. The Dashboard page refreshes it every 45 s.

---

## 5. Devices (cameras)

### 5.1 `GET /api/devices/detail`

Every camera configured on the box, with its status. **Passwords are masked.**

**Response `200`**: an array

```json
[
  {
    "device_id": 1,
    "device_name": "Hikvision",
    "device_type": "Video",
    "protocol": "rtsp",
    "manufacturer": "unknown",
    "address": "rtsp://camuser:****@192.168.90.24:554/ISAPI/Streaming/channels/201",
    "online": true,
    "state_code": 0,
    "pulling_stream": true
  }
]
```

| Field | Meaning |
|---|---|
| `device_type` | `"Video"` (box `channel_type` 1), `"Picture"` (2, assumed), otherwise `"Type N"` |
| `address` | RTSP URL with the password replaced by `****` |
| `online` | `true` when the box's `state` is `0` |
| `state_code` | Raw box state; kept so unknown values can be identified later. `null` if the box didn't report one. |
| `pulling_stream` | `true` if any of the camera's channels has `pull_stream: true` |

**Box calls:** `POST /device_access/device_config`, `POST /device_access/device_state` (each `{offset: 0, size: 100}`).

### 5.2 `GET /api/devices`

Lightweight list (id + name) used to show camera names next to records.

**Response `200`**

```json
[ { "device_id": 1, "device_name": "Hikvision" }, { "device_id": 2, "device_name": "IPCAM-D3" } ]
```

**Box calls:** `POST /device_access/device_config`.

### 5.3 `POST /api/devices`

Add an RTSP video camera. The backend gives it the **lowest free device id**, as the box's own UI does.

**Request body** (`application/json`)

| Field | Type | Required | Rules |
|---|---|---|---|
| `name` | string | yes | 1–64 characters; must be unique (case-insensitive) |
| `type` | `"video"` \| `"picture"` | no (default `"video"`) | Only `"video"` is supported; `"picture"` → `501` |
| `protocol` | `"rtsp"` | no (default `"rtsp"`) | Only RTSP is supported |
| `url` | string | yes | 8–512 characters, must look like `rtsp://host[:port]/path` |
| `user` | string | no | ≤ 64 characters |
| `password` | string | no | ≤ 128 characters |

Credentials can be in `user` / `password`, inside the URL (`rtsp://user:pass@host/…`), or both; the separate fields win. Special characters are percent-encoded when they're put into the URL.

```json
{ "name": "Entrance", "type": "video", "protocol": "rtsp",
  "url": "rtsp://192.168.1.30:554/stream1", "user": "camuser", "password": "secret" }
```

**Response `201`**

```json
{ "device_id": 4 }
```

**Errors**

| Status | `detail` |
|---|---|
| `409` | `A device named '<name>' already exists` |
| `422` | `RTSP address must look like rtsp://host:port/path`, or a field-validation list |
| `501` | `Adding Picture devices isn't supported yet` |

**Box calls:** `POST /device_access/device_config` (to find used ids and names), then `POST /device_access/device`. Adds run one at a time, so two simultaneous adds can't get the same id.

### 5.4 `PUT /api/devices/{device_id}`

Change a camera's name, address or credentials.

**Path parameter:** `device_id` (integer ≥ 1)

**Request body**: same as [5.3](#53-post-apidevices) without `type`. **An empty `password` keeps the current one**: the backend reads it from the box and sends it back, because the browser never sees it.

```json
{ "name": "Gate", "protocol": "rtsp", "url": "rtsp://192.168.1.24:554/ISAPI/Streaming/channels/301",
  "user": "camuser", "password": "" }
```

**Response `200`**

```json
{ "updated": 2 }
```

**Errors:** `404` `Device #N is not configured on the box`; `409` duplicate name; `422` bad URL or fields.

**Box calls:** `POST /device_access/device_config`, then `PUT /device_access/device_config` with the full config.

### 5.5 `DELETE /api/devices/{device_id}`

Remove a camera. **Permanent**: the box stops analysing it.

**Response `200`**

```json
{ "deleted": 4 }
```

**Errors:** `404` `Device #N is not configured on the box` (checked first, so a stale page can't send a bad delete).

**Box calls:** `POST /device_access/device_config`, then `DELETE /device_access/device`.

---

## 6. Live preview

### 6.1 `GET /api/preview/cameras`

Cameras for the Live view, each with a signed token for its video link. **No RTSP addresses or passwords are returned.**

**Response `200`**

```json
[
  { "id": 1, "name": "Hikvision", "online": true,  "task": "FR", "stream_token": "exp=1790000000&sig=3f2a…" },
  { "id": 3, "name": "CAM3-D4",   "online": false, "task": null, "stream_token": "exp=1790000000&sig=91bc…" }
]
```

| Field | Meaning |
|---|---|
| `task` | Name of the analysis task bound to the camera, or `null` |
| `stream_token` | Append to the stream URL. Valid **12 hours**, for **this camera only**. `null` if the box gave a non-integer id. |

**Box calls:** `device_config`, `device_state`, `intelli_manager/task_list` (each `size: 50`).

### 6.2 `GET /api/preview/{device_id}/stream`

Live video as **MJPEG** (`Content-Type: multipart/x-mixed-replace; boundary=frame`). Meant to be the `src` of an `<img>`.

**Query parameters**

| Name | Type | Default | Description |
|---|---|---|---|
| `hd` | bool | `false` | `true` = main stream (full resolution); `false` = sub-stream (lighter) |
| `width` | int 160–1920 | `960` | Maximum frame width; smaller frames are not upscaled |
| `fps` | int 1–25 | `10` | Frames per second |
| `exp`, `sig` | | | The signed `stream_token` from [6.1](#61-get-apipreviewcameras); needed when `API_KEY` is set (an `<img>` can't send the header) |

The frontend builds the URL as:

```
{NEXT_PUBLIC_BACKEND_URL}/api/preview/1/stream?hd=false&width=640&r=0&exp=…&sig=…
```

(`r` is a retry counter that only defeats the browser cache; the backend ignores it.)

**Errors**

| Status | `detail` |
|---|---|
| `401` | Missing/wrong key **and** missing/expired/invalid signature |
| `404` | `Camera N not found or has no RTSP address` |
| `500` | `ffmpeg not found (…)`: install ffmpeg or set `FFMPEG_PATH` |
| `502` | `No video from camera N: <ffmpeg error or "no frames within 20 s">` |
| `503` | `Too many live videos open (16). Close some tiles or tabs and retry.` |

**Box calls:** `POST /device_access/device_config` (to read the RTSP URL); then ffmpeg connects to the camera over RTSP.

---

## 7. Recognition records

### 7.1 `GET /api/recognition`

One page of recognition records, **passed through from the box unchanged**. The frontend (`client/src/lib/recognition.ts`) maps the fields.

**Query parameters**

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `start` | `YYYY-MM-DD HH:mm:ss` | yes | | Start of range, box time |
| `end` | `YYYY-MM-DD HH:mm:ss` | yes | | End of range, box time; must not be before `start` |
| `minor` | `face_comparison_successful` \| `stranger` | no | `face_comparison_successful` | Matched people or strangers |
| `page` | int ≥ 1 | no | `1` | |
| `size` | int 1–30 | no | `10` | |

**Response `200`**: the box's `data` object

```json
{
  "total_count": 123,
  "return_count": 10,
  "list": [
    {
      "additional":  { "alarm_id": 101, "alarm_minor": "face_comparison_successful", "device_id": 1 },
      "global_info": { "time_ms": "1727600000000" },
      "faces": [ {
        "track_id": 5610081,
        "image_data": { "image_data_format": 2, "value": "./record_CHN0/…/face.jpg" },
        "age": 31, "gender": 2, "wear_hat": 2, "wear_glasses": 2, "wear_respirator": 2,
        "hair_style": 13, "beard_class": 2,
        "recognition_info": [ {
          "person_uuid": "17", "person_name": "Ada Lovelace", "face_score": 96,
          "image_data": { "image_data_format": 2, "value": "/home/appdata/…/17.jpg" },
          "group_info": [ { "group_name": "Staff" } ]
        } ]
      } ],
      "full_images": [ { "image_data": { "image_data_format": 2, "value": "./record_CHN0/…/full.jpg" } } ]
    }
  ]
}
```

The record layout is described in [Box API §4.4](box-api.md#44-record-structure). Past the last page, the response is `{"total_count": N, "return_count": 0, "list": []}`, not an error.

**Errors:** `422` for a bad time format, `start` after `end`, unknown `minor`, or `size` > 30. These are refused before the box is called.

**Box calls:** `POST /device_alarm/alarm_history` with `alarm_type: [{major_type: RECOG_MAJOR, minor_type: [minor]}]` and `ext: {query_type: 0, de_dup: 0}`.

> **How the frontend uses it:** in **Matched** mode, the Recognition page pulls **every** record in the range (30 at a time, up to 5,000), drops records of people no longer in the face library (`/api/people`), then pages the rest itself. In **Stranger** mode it asks for one page at a time.

### 7.2 `DELETE /api/recognition/{alarm_id}`

Permanently delete one recognition record.

**Path parameter:** `alarm_id` (integer ≥ 1): the record's `additional.alarm_id`

**Response `200`**

```json
{ "deleted": 101 }
```

**Box calls:** `DELETE /device_alarm/alarm_history` with `type: "alarm_id"` and both recognition minor types.

---

## 8. Capture records

### 8.1 `GET /api/capture`

One page of face and body captures, **flattened by the backend** into simple rows.

**Query parameters**

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `start`, `end` | `YYYY-MM-DD HH:mm:ss` | yes | | Range, box time |
| `target_type` | `all` \| `face` \| `body` | no | `all` | Which captures |
| `page` | int ≥ 1 | no | `1` | |
| `size` | int 1–30 | no | `10` | |

**Response `200`**

```json
{
  "total_count": 57,
  "return_count": 10,
  "list": [
    {
      "alarm_id": 2201,
      "track_id": 5610081,
      "target_type": "face",
      "device_id": 1,
      "capture_time_ms": "1727600000000",
      "target_image": "./record_CHN0/…/face.jpg",
      "panoramic_image": null,
      "attributes": { "age": 31, "gender": 2, "wear_glasses": 2 }
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `target_type` | `"face"` for `face_capture`, `"body"` for everything else |
| `target_image` | Box path of the cropped face/body (`faces[0]` or `pedestrians[0]`), or `null`. Load it with [`/api/image`](#121-get-apiimage). |
| `panoramic_image` | Box path of the full frame, or `null` when the box has none |
| `attributes` | Every field of the target except bookkeeping keys (`image_data`, `link_info`, `alarm_linkage`, `track_id`, `track_id_times`). Values are the box's **raw codes**. |

**Errors:** as for [7.1](#71-get-apirecognition).

**Box calls:** `POST /device_alarm/alarm_history` with two `alarm_type` entries: the capture minor types **and** a `structure` entry (the box refuses the query without it). There is no confirmed device filter, so the frontend filters by camera on the loaded page.

---

## 9. Face library: people list

### 9.1 `GET /api/people`

Everyone in the face library, **id and name only**. The frontend uses it to hide records of people who have been deleted (the box keeps their records).

**Response `200`**

```json
{ "total_count": 2, "person_list": [ { "person_id": "0", "name": "P0" }, { "person_id": "1", "name": "P1" } ] }
```

- The backend pages through the whole library (30 per box call).
- The result is **cached for `PEOPLE_CACHE_SECONDS`** (default 60 s). Adding, editing or deleting a person through the portal clears the cache immediately.

**Box calls:** `POST /face_manager/person/query` with `get_feature: false`, repeated until all people are read.

---

## 10. Face library: personnel management

### 10.1 `GET /api/personnel/groups`

**Response `200`**

```json
{ "groups": [ { "group_id": "1", "group_name": "Staff" } ] }
```

Groups are passed through from the box; `[]` if none. **Box calls:** `POST /face_manager/groups/query`.

### 10.2 `GET /api/personnel`

One page of people with their full profile.

**Query parameters:** `page` (≥ 1, default 1), `size` (1–30, default 10), `get_feature` (bool, default `true`: include face-feature data; large, and not needed for display).

**Response `200`**

```json
{
  "page": 1,
  "size": 10,
  "total_count": 57,
  "person_list": [
    {
      "person_id": "17",
      "person_info": { "name": "Ada Lovelace", "code": "ADA-1", "birthday": "1815-12-10", "gender": 0, "remarks": "Visitor" },
      "groups": [ { "group_id": "1", "group_name": "Staff" } ],
      "face_image1": "/home/appdata/…/17.jpg"
    }
  ]
}
```

Each person is passed through from the box, plus one normalised field: **`face_image1`**, the reference photo path. The box puts it under different keys depending on firmware; the backend copies the first one it finds here.

**Box calls:** `POST /face_manager/person/query`.

### 10.3 `POST /api/personnel`

Add a person with a reference photo.

**Request** (`multipart/form-data`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | text | yes | At least 1 character |
| `photo` | file | yes | Must be an image (`image/*`), at most `MAX_PHOTO_MB` (default 5 MB) |
| `group_ids` | text | no | JSON array of group ids, e.g. `["1","3"]` (default `[]`) |
| `birthday` | text | no | e.g. `1990-05-01` |
| `gender` | integer | no | Box code, default `0` |
| `code` | text | no | Employee or visitor code |
| `person_id` | text | no | Sent to the box as `person_info.id` |
| `remarks` | text | no | |
| `person_type` | text | no | Sent as `person_info.type` |

```bash
curl -H "X-API-Key: $API_KEY" -F name="Jane Doe" -F photo=@jane.jpg -F 'group_ids=["1"]' \
     http://localhost:8000/api/personnel
```

**Response `201`**: the box's `data` for the new person (shape not documented), or `{"message": "created"}` if the box returned none.

**Errors**

| Status | `detail` |
|---|---|
| `413` | `photo is too large (max 5 MB)` |
| `415` | `photo must be an image` |
| `422` | `a reference photo is required`, `group_ids must be a JSON array`, or a missing `name` |

**Box calls:** `POST /face_manager/person` (multipart: `face1` = photo, `person_info` = JSON). Clears the `/api/people` cache.

### 10.4 `PUT /api/personnel/{person_id}`

Edit a person. Same fields as [10.3](#103-post-apipersonnel) except `person_id` and `person_type`, and **`photo` is optional**: leave it out (or empty) to keep the current photo.

**Group behaviour:** a non-empty `group_ids` **replaces** the person's groups. An empty `group_ids` leaves them **unchanged**, as the box's own UI does.

**Response `200`**: the box's `data`, or `{"message": "updated"}`.

**Errors:** as for [10.3](#103-post-apipersonnel), plus `502 Person details were saved, but changing the groups failed: …` when the second box call fails. The details **are** saved at that point; only the groups aren't.

**Box calls:** `PUT /face_manager/person` (multipart), then `PUT /face_manager/person_bind` if groups were given. Clears the `/api/people` cache.

### 10.5 `DELETE /api/personnel/{person_id}`

Delete a person from the face library. Their old recognition records stay on the box; the portal hides them.

**Response `200`**: the box's `data` (often `null`).

**Box calls:** `DELETE /face_manager/person` with `{force: true, all: false, person_id_list: [id]}`. Clears the `/api/people` cache.

---

## 11. Time plans

A plan has a name, a type (`1` = regular/weekly, `2` = festival) and a `week_schedule`: keys `"1"` (Monday) … `"7"` (Sunday), each a list of `"HH:MM:SS-HH:MM:SS"` windows. An empty list means "off all day".

### 11.1 `GET /api/timeplans/time`

The box's clock and time settings.

**Response `200`**

```json
{
  "system_time":  { "time_zone": "…", "time_mode": "…", "time_dst": { "dst_enable": 0, "offset": 0 } },
  "current_time": { "time": "2026-09-29 14:07:00" },
  "clock_source": "box"
}
```

If the box's time endpoints are missing (box code `404`), `system_time` is `{}`, `current_time` is the **backend's** clock with `"source": "backend_fallback"`, and `clock_source` is `"backend_fallback"`.

**Box calls:** `POST /system/get_system_time`, `POST /system/get_time_info`.

### 11.2 `GET /api/timeplans/regular` and `/api/timeplans/festival`

The box's plans of type 1 (`size: 100`) or type 2 (`size: 50`), **passed through unchanged**.

**Response `200`** (as read by the frontend)

```json
{
  "schedule_plans": [
    {
      "schedule_plan_id": "1",
      "schedule_plan_name": "All day",
      "schedule_plan_type": 1,
      "week_schedule": { "1": ["00:00:00-23:59:59"], "2": ["00:00:00-23:59:59"], "…": [] },
      "ext": { "default": 1 }
    }
  ]
}
```

`ext.default: 1` marks the box's built-in default plan.

**Box calls:** `POST /device_rules/schedule_plan/query`.

### 11.3 `POST /api/timeplans`

Create a plan.

**Request body**

| Field | Type | Required | Rules |
|---|---|---|---|
| `schedule_plan_name` | string | yes | 1–128 characters |
| `schedule_plan_type` | `1` \| `2` | yes | |
| `week_schedule` | object | yes | `{ "1": ["09:00:00-17:00:00"], … }` |
| `bind_schedule_plan` | array | no | Passed through as-is (meaning not documented yet); the frontend sends `[]` |

```json
{ "schedule_plan_name": "Office hours", "schedule_plan_type": 1,
  "week_schedule": { "1": ["09:00:00-17:00:00"], "2": ["09:00:00-17:00:00"], "3": [], "4": [], "5": [], "6": [], "7": [] },
  "bind_schedule_plan": [] }
```

**Response `201`**

```json
{ "data": {}, "schedule_plan_name": "Office hours" }
```

The new plan's id isn't returned; reload the list to get it. **Box calls:** `POST /device_rules/schedule_plan`.

### 11.4 `PUT /api/timeplans/{plan_id}`

Update a plan. Body = [11.3](#113-post-apitimeplans) **plus** `schedule_plan_id`, which must equal `{plan_id}` (else `422 plan_id must match schedule_plan_id`).

**Response `200`**

```json
{ "schedule_plan_id": "3", "data": {} }
```

**Box calls:** `PUT /device_rules/schedule_plan`.

### 11.5 `DELETE /api/timeplans/{plan_id}`

**Request body** (a JSON body on a DELETE)

```json
{ "schedule_plan_id": "3", "schedule_plan_type": 1 }
```

`schedule_plan_id` must equal `{plan_id}`.

**Response `200`**

```json
{ "deleted": "3", "data": {} }
```

**Box calls:** `DELETE /device_rules/schedule_plan`.

### 11.6 `DELETE /api/timeplans/stream-subscriptions`

Meant to close live subscriptions the box's own time-plan page opens.

**Request body:** `{ "handles": [12], "device_alarm_handles": [7] }` (at least one id; each ≥ 1; either list may be empty, not both).

**Response `200`**

```json
{ "media_video_handles": [12], "device_alarm_handles": [7] }
```

**Errors:** `422 At least one stream handle is required`. No frontend code calls this route yet.

**Box calls:** `DELETE /media_video/subscribe_stream` per handle, `DELETE /device_alarm/subscribe_stream` per device-alarm handle.

---

## 12. Images

### 12.1 `GET /api/image`

Streams an image stored on the box. The browser can't fetch these directly because it doesn't have the box session.

**Query parameters**

| Name | Required | Description |
|---|---|---|
| `uri` | yes | Box image path from a record or person, e.g. `./record_CHN0/…/face.jpg` or `/home/appdata/…/17.jpg` |
| `v` | no | Ignored by the backend; the frontend adds it to bust the browser cache after a photo change |

Allowed paths start with `./record_`, `record_`, `./group/`, `group/` or `/home/appdata/`, end in `.jpg`, `.jpeg`, `.png`, `.bmp` or `.webp`, and contain no `..`.

**Response `200`:** the image bytes with an `image/*` content type and `Cache-Control: max-age=86400`.

**Errors:** `400 Not an image path`; `404 Image not found on the box`.

**Box calls:** `GET /device_storage/get_image?image_uri=<uri>`, falling back to `GET /<uri>` (absolute paths) and `GET /web/<uri>`. If the session expired, it logs in again and retries once.

---

## 13. Errors

Every error body is JSON with a `detail` field.

```json
{ "detail": "Box error on /device_alarm/alarm_history: general (code 1073741825)" }
```

For request-validation errors, FastAPI returns `detail` as a **list**:

```json
{ "detail": [ { "type": "less_than_equal", "loc": ["query", "size"], "msg": "Input should be less than or equal to 30", "input": "50" } ] }
```

| Status | Meaning | Typical `detail` | What to do |
|---|---|---|---|
| `400` | Bad image path | `Not an image path` | Use a path from a record |
| `401` | Access refused | `Missing or wrong API key` | Match `BACKEND_API_KEY` (client) to `API_KEY` (backend); restart the frontend |
| `404` | Unknown id or image | `Device #9 is not configured on the box` | Refresh the page |
| `409` | Duplicate | `A device named 'Gate' already exists` | Pick another name |
| `413` | Photo too large | `photo is too large (max 5 MB)` | Use a smaller photo |
| `415` | Not an image | `photo must be an image` | Upload a JPEG/PNG |
| `422` | Invalid input | `Bad time '…', expected YYYY-MM-DD HH:mm:ss`, `start must be before end`, or a list | Fix the request; the box was **not** called |
| `500` | Backend fault | `ffmpeg not found (…)` or `Internal Server Error` | Check the backend log |
| `501` | Not implemented | `Adding Picture devices isn't supported yet` | Use the box UI |
| `502` | The box refused | `Box error on <path>: <message> (code N)` · `No video from camera N: …` | See [Box error codes](box-api.md#10-error-codes) |
| `503` | Box or database unreachable / no database / too many streams | `B4H box unreachable (ConnectError)` · `Too many live videos open (16)…` | Check the network; close video tiles |
| `504` | Box too slow | `The box took too long to answer. Try a shorter date range, or try again.` | Shorten the range or raise `B4H_TIMEOUT` |

If the box refused the login, every call fails with `502` and a message saying login is paused: fix `B4H_USER` / `B4H_PASS` and **restart** the backend.

---

## 14. Frontend client map

Which frontend function calls which route (`client/src/lib/`):

| File | Function | Route |
|---|---|---|
| `dashboard.ts` | `fetchDashboardSummary(date?)` | `GET /api/dashboard/summary` |
| `devices.ts` | `fetchDeviceDetails()` | `GET /api/devices/detail` |
| | `createDevice(d)` | `POST /api/devices` |
| | `updateDevice(id, d)` | `PUT /api/devices/{id}` |
| | `deleteDevice(id)` | `DELETE /api/devices/{id}` |
| `preview.ts` | `fetchPreviewCameras()` | `GET /api/preview/cameras` |
| | `streamUrl(camera, hd, retry)` | builds the `GET /api/preview/{id}/stream` URL (SD width 640, HD width 1920) |
| `recognition.ts` | `fetchRecognition(q)` | `GET /api/people` + `GET /api/recognition` (one or many pages) |
| | `deleteRecognition(alarmId)` | `DELETE /api/recognition/{alarm_id}` |
| | `fetchDevices()` | `GET /api/devices` |
| | `fetchLatestRecognitions(q)` | `GET /api/people` + one `GET /api/recognition` page (Live view) |
| | `fetchPeople()` | `GET /api/people` |
| `captures.ts` | `fetchCaptures(q)` | `GET /api/capture` + `GET /api/devices` |
| `personnel.ts` | `fetchPersonnel(page, size)` | `GET /api/personnel?get_feature=true` |
| | `fetchPersonnelGroups()` | `GET /api/personnel/groups` |
| | `createPersonnel(form)` | `POST /api/personnel` |
| | `updatePersonnel(id, form)` | `PUT /api/personnel/{id}` |
| | `deletePersonnel(id)` | `DELETE /api/personnel/{id}` |
| `timeplans.ts` | `fetchTimeContext()` | `GET /api/timeplans/time` |
| | `fetchTimePlans(kind)` | `GET /api/timeplans/{regular\|festival}` |
| | `createTimePlan(plan)` | `POST /api/timeplans` |
| | `updateTimePlan(plan)` | `PUT /api/timeplans/{id}` |
| | `deleteTimePlan(plan)` | `DELETE /api/timeplans/{id}` |
| `alarms.ts` | `fetchAlarmStatus()` | `GET /api/alarms/status` (also the sidebar badge, every 60 s) |
| | `fetchAlarmCameras()` | `GET /api/alarms/cameras` |
| | `fetchContacts()`, `saveContact(c)`, `deleteContact(id)`, `sendTestEmail(to)` | `/api/alarms/contacts`, `/api/alarms/test-email` |
| | `fetchRules()`, `createRule(r)`, `updateRule(id, version, r)`, `setRuleEnabled(id, on)`, `deleteRule(id)` | `/api/alarms/rules` |
| | `fetchIncidents(f)`, `fetchIncident(ref)`, `updateIncident(id, change)` | `/api/alarms/incidents` |
| `counting.ts` | `fetchCountingSummary(f)` | `GET /api/counting/summary` |
| | `fetchCountingSeries(f, granularity)` | `GET /api/counting/series` |
| | `fetchCountingHeatmap(f)` | `GET /api/counting/heatmap` |
| | `fetchSightings(f, page, size)` | `GET /api/counting/sightings` |
| | `fetchCountingCameras()`, `updateCountingCamera(id, change)` | `/api/counting/cameras` |
| (all with images) | `imageUrl(uri)` helpers | `GET /api/image?uri=…` |

---

## 15. Alarms

Rules, recipients and incidents live in the portal's **own database** (`DATABASE_URL`, PostgreSQL on Neon), not on the box. A background worker reads the box's recognition and capture records every few seconds and checks them against the rules; see [backend README → Database and alarms](../fastapi-app/README.md#database-and-alarms).

Without `DATABASE_URL`, every route below answers `503 The database isn't configured…`, except `GET /api/alarms/status` (which reports `database: false`).

Ids: `camera_ids` are the portal's camera ids from 15.2 (not the box `device_id`). Times in responses are ISO 8601 with time zone (UTC).

### 15.1 `GET /api/alarms/status`

Health of the alarm feature, and the open-alarm count for the sidebar badge.

```json
{
  "database": true,
  "workers": { "ingest": { "running": true, "last_ok": "2026-09-28T17:05:00+00:00", "last_error": null },
               "mailer": { "running": true, "last_ok": "…", "last_error": null } },
  "smtp": { "configured": true, "host": "smtp.gmail.com", "sender": "alarms@example.org" },
  "timezone": "Asia/Dhaka",
  "max_recipients": 5,
  "ingest": [ { "stream": "recognition", "read_until": "…", "last_success_at": "…", "consecutive_failures": 0,
                "last_error": null, "events_ingested": 1520 } ],
  "open_incidents": 3,
  "notifications": { "pending": 0, "failed": 1 }
}
```

### 15.2 `GET /api/alarms/cameras`

Cameras a rule can watch: the box's device list, copied into the database first (if the box is unreachable, the last copy is returned). Cameras removed from the box stay, with `deleted: true`.

```json
[ { "id": 2, "device_id": 2, "name": "IPCAM-D3", "deleted": false } ]
```

### 15.3 Recipients

| Method | Path | Body / result |
|---|---|---|
| GET | `/api/alarms/contacts` | `[ { "id", "name", "email", "is_active", "rule_count" } ]` |
| POST | `/api/alarms/contacts` | `{ "name", "email", "is_active": true }` → `201` the recipient. The email is stored lower-case; a duplicate → `409` |
| PUT | `/api/alarms/contacts/{id}` | same body → the recipient |
| DELETE | `/api/alarms/contacts/{id}` | removes them from every rule → `{ "deleted": id }` |
| POST | `/api/alarms/test-email` | `{ "to": "you@example.org" }` → `{ "sent_to" }`. Sends immediately. `409` if SMTP isn't set up, `502` with the SMTP server's message if it refuses |

`is_active: false` pauses a recipient: rules keep them, but no emails are queued for them.

### 15.4 Rules

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/alarms/rules` | All rules (with cameras, windows, targets, recipients, `last_fired_at`) |
| POST | `/api/alarms/rules` | Create → `201` |
| GET | `/api/alarms/rules/{id}` | One rule |
| PUT | `/api/alarms/rules/{id}` | Replace (body + `version`) |
| PATCH | `/api/alarms/rules/{id}/enabled` | `{ "is_enabled": false }` |
| DELETE | `/api/alarms/rules/{id}` | Delete; its past alarms are kept (`rule_id` becomes `null`, `rule_name` stays) |

**Body** (POST; PUT adds `"version"`):

```json
{
  "name": "Night watch D3",
  "description": null,
  "is_enabled": true,
  "severity": "critical",
  "event_kinds": ["stranger", "matched"],
  "match_mode": "anyone",
  "min_match_score": null,
  "min_liveness": null,
  "timezone": "Asia/Dhaka",
  "cooldown_seconds": 300,
  "dedupe_scope": "camera",
  "max_delay_seconds": 300,
  "email_delayed": false,
  "attach_snapshot": true,
  "camera_ids": [2],
  "windows": [ { "iso_dow": 1, "start": "22:00", "end": "06:00" } ],
  "targets": [ { "type": "group", "value": "1", "label": "Staff" } ],
  "recipient_ids": [1, 4]
}
```

| Field | Meaning |
|---|---|
| `event_kinds` | Which detections count: `stranger`, `matched` (recognised person), `face_capture`, `body_capture` |
| `match_mode` | `anyone`; `strangers` (needs `stranger`); `known` = anyone in the face library (needs `matched`); `targets` = only the people/groups in `targets` (needs `matched`) |
| `targets` | `type` `person` (box `person_id`) or `group` (box `group_id`); `label` is the name, also used to match records that only carry group names |
| `min_match_score` | Recognised people need at least this similarity (0–100). Not applied to strangers |
| `min_liveness` | Ignore detections below this liveness (0–100). Records without a liveness score pass |
| `windows` | When the rule is active, per weekday (`iso_dow` 1 = Monday), box time zone (`timezone`). `end` before `start` runs past midnight and belongs to the day it starts. **No windows = always active** |
| `cooldown_seconds` | Quiet period: after an alarm, more detections on that camera join it (`event_count`) instead of raising new alarms and emails |
| `dedupe_scope` | `camera`: one alarm per camera per quiet period. `track`: one alarm per person track (each person walking by) |
| `max_delay_seconds` / `email_delayed` | A detection that reaches the portal later than this is saved as a **delayed** alarm, and only emailed with `email_delayed: true` |
| `recipient_ids` | Up to `ALARM_MAX_RECIPIENTS` (5) |

**Errors:** `422` for inconsistent rules (e.g. `strangers` without the `stranger` kind, `targets` without targets, a window starting and ending at the same time, more than 5 recipients, an unknown or removed camera); `409` for a duplicate name, or a `version` that isn't the current one (someone else saved first: reload and edit again).

### 15.5 `GET /api/alarms/incidents`

Alarms, newest first.

| Param | Default | Notes |
|---|---|---|
| `status` | all | Repeatable: `open`, `acknowledged`, `resolved`, `false_alarm` |
| `rule_id`, `camera_id` | | |
| `start`, `end` | | `YYYY-MM-DD HH:mm:ss` in the box's time zone |
| `page` / `size` | `1` / `20` | `size` ≤ 100 |

```json
{
  "total": 1, "page": 1, "size": 20,
  "items": [ {
    "id": 41, "public_id": "0b5c6c1e-…", "rule_id": 7, "rule_name": "Night watch D3", "severity": "critical",
    "camera_id": 2, "camera_name": "IPCAM-D3", "track_id": 5727190, "person_uuid": null, "person_name": null,
    "is_stranger": true, "occurred_at": "…", "detected_at": "…", "delay_seconds": 4, "is_delayed": false,
    "event_count": 3, "last_event_at": "…", "status": "open", "acknowledged_by": null, "acknowledged_at": null,
    "note": null, "snapshot_path": "./record_CHN0/…/face.jpg"
  } ]
}
```

`snapshot_path` is a box image path: show it through [`GET /api/image`](#121-get-apiimage).

### 15.6 `GET /api/alarms/incidents/{ref}`

`ref` is the alarm `id`, or its `public_id` (used in email links). Returns the item above plus `rule_snapshot` (the rule as it was when it fired), `events` (up to 50 detections: `kind`, `occurred_at`, track ids, person, scores, image paths) and `notifications` (`to_address`, `status` `pending|sending|sent|failed`, `attempts`, `last_error`, `sent_at`). `404` if unknown.

### 15.7 `PATCH /api/alarms/incidents/{id}`

```json
{ "status": "acknowledged", "note": "Checked the camera", "by": "Nishat" }
```

All fields optional. Moving away from `open` records `acknowledged_at` and `acknowledged_by` (`by`, or `portal`); back to `open` clears them. Every change is written to the audit log.

---

## 16. People counting

How many people walked past each camera, and how many different people that was. Built from the box records the alarm worker already stores (no extra box calls): each record is put into a **sighting**, one person passing one camera once, as it arrives. The box never puts a face and a body in one record, but numbers them from one counter, so face track `F` and body track `F − 1` on the same camera (first records at most `COUNT_PAIR_MAX_SECONDS` apart) are merged into one sighting.

Like Alarms, this needs the **database**: without `DATABASE_URL` every route answers `503`. Sightings for records saved before this feature existed are built once with `uv run python -m counting.backfill` (see the [backend README](../fastapi-app/README.md#database-and-alarms)).

### 16.1 Terms and shared parameters

| Term | Meaning | Accuracy |
|---|---|---|
| `walk_pasts` | Sightings: one person passing one camera once | Very good |
| `visits` | Sightings of the same **identified** person on the same camera within `COUNT_VISIT_GAP_SECONDS` (120) count once | Equals walk-pasts until people are identified |
| `unique_people` | `COUNT(DISTINCT person_key)`: different people in the cameras and period | Exact for recognised people; an **upper bound** for everyone else |
| `known_people` | Different face-library people | Exact |
| `stranger_walk_pasts` | Walk-pasts the box compared and found no match for. Strangers aren't grouped, so these aren't different people | Exact as a walk-past count |

Today the box sends no face-recognition results, so nobody can be identified and `unique_people` = `visits` = `walk_pasts`. `identity_available` (summary) says whether that has changed.

**Different people by face and clothing (`face_estimate`).** After each poll the backend fingerprints the face picture (OpenCV YuNet + SFace) and the whole-body picture (YouTu ReID: mostly clothing) of every new walk-past; see the [backend README](../fastapi-app/README.md#database-and-alarms). For a request, the walk-pasts in the chosen cameras and period are grouped: recognised people by their library id, everyone else by similarity (60 % body, 40 % face; bodies only within the same day, since clothes change; two walk-pasts on one camera at the same moment are never one person). The answer is a range: `people` at `PEOPLE_MATCH_THRESHOLD` (0.35), `low` at 0.05 looser, `high` at 0.05 stricter. Walk-pasts with no usable face or body picture aren't in it. Across several days only faces can link a person, so multi-day counts run higher than the truth.

Every route except the camera settings takes:

| Param | Default | Rules |
|---|---|---|
| `camera_id` | every camera with `count_enabled` | Repeatable. Portal camera ids (16.6). Unknown or removed → `422` |
| `start`, `end` | today 00:00:00 → now | `YYYY-MM-DD HH:mm:ss` in the box's time zone; `start` must be before `end`; at most 366 days |
| `hours` | all day | `9-17` (inclusive local hours 0–23) or `22-5` (past midnight) |
| `days` | every day | ISO weekdays, `1,2,3,4,5` = Monday–Friday |

A sighting belongs to the time, hour and weekday of its **first** record (box clock). Each camera's `count_basis` decides which of its sightings count: `merged` all, `face` only those with a face track, `body` only those with a body track.

### 16.2 `GET /api/counting/summary`

```json
{
  "period": { "start": "2026-10-04T00:00:00+06:00", "end": "2026-10-04T15:12:03+06:00", "timezone": "Asia/Dhaka" },
  "totals": { "walk_pasts": 120, "visits": 118, "unique_people": 118, "known_people": 0, "stranger_walk_pasts": 0,
              "not_compared_walk_pasts": 120, "paired": 104, "face_only": 9, "body_only": 7,
              "face_estimate": { "people": 7, "low": 6, "high": 10, "fingerprinted": 69, "unusable": 1,
                                 "pending": 0, "too_many": false } },
  "by_camera": [ { "camera_id": 2, "name": "IPCAM-D3", "count_basis": "merged", "walk_pasts": 120, "visits": 118,
                   "face_estimate": { "…": "…" }, "…": "…" } ],
  "identity_available": false,
  "face_matching": { "available": true, "reason": null },
  "last_sighting_at": "2026-10-04T09:12:03+00:00"
}
```

`paired` have both a face and a body track, `face_only` no body, `body_only` no face. `face_estimate`: `fingerprinted` walk-pasts are in the estimate, `unusable` aren't (nothing to compare), `pending` haven't been processed yet; `too_many: true` (more than `PEOPLE_MAX_GROUPING`, 2000, walk-pasts) leaves `people`/`low`/`high` `null`: pick a shorter period. `face_matching.available` is false (with a `reason`) when the models aren't installed or `FACE_MATCHING=0`. `identity_available`: any recognised or stranger record on these cameras in the last 7 days. `last_sighting_at`: latest sighting on these cameras, whatever the period.

### 16.3 `GET /api/counting/series`

`granularity` = `15m` (range ≤ 7 days), `hour` (default, ≤ 62 days) or `day` (≤ 366 days); a longer range → `422` naming the granularity to use. Points are zero-filled and skip slots outside `hours` / `days`. `face` / `body` are the walk-pasts with a face / body track.

```json
{ "granularity": "hour", "points": [ { "start": "2026-10-04T09:00:00+06:00", "walk_pasts": 4, "face": 3, "body": 4, "new_people": 2 } ] }
```

`new_people`: people seen for the **first time in the period**, counted in the slot of their first walk-past; someone who comes back later in the period isn't counted again. They add up to `face_estimate.people` (summary). `null` when the period has too many fingerprints to group.

Read from 15-minute totals: a bucket that starts before `start` but overlaps it is included.

### 16.4 `GET /api/counting/heatmap`

Busy times: walk-pasts per weekday × local hour, **averaged per day** (divided by how many of that weekday the range covers), so a range with three Mondays doesn't look three times busier. Only cells with walk-pasts are listed.

```json
{ "cells": [ { "iso_dow": 1, "hour": 9, "walk_pasts": 7, "avg_walk_pasts": 3.5 } ],
  "days_in_range": { "1": 2, "2": 1, "3": 1, "4": 1, "5": 1, "6": 1, "7": 1 } }
```

### 16.5 `GET /api/counting/sightings`

The walk-pasts behind the numbers, newest first. `page` / `size` (default `1` / `20`, `size` ≤ 100).

```json
{ "total": 120, "page": 1, "size": 20, "items": [ {
    "id": 881, "camera_id": 2, "camera_name": "IPCAM-D3", "first_seen_at": "…", "last_seen_at": "…",
    "duration_seconds": 1.3, "face_track_id": 5735752, "body_track_id": 5735751, "person_source": "unidentified",
    "person_name": null, "recognition_result": null, "event_count": 3,
    "face_image_path": "./record_CHN0/…", "body_image_path": "./record_CHN0/…",
    "person_no": 5, "new_person": false, "person_first_seen_at": "2026-10-04T03:44:52+00:00" } ] }
```

Each item also has `person_no` (the n-th different person in the period, in order of first appearance), `new_person` (`true` on that person's first walk-past in the period, `false` when they came back) and `person_first_seen_at`; all three are `null` when the walk-past had no usable face or body picture. `person_source`: `recognized` / `stranger` / `unidentified`. `recognition_result`: `matched`, `stranger` or `null` (not compared). Images go through [`GET /api/image`](#121-get-apiimage).

### 16.6 Camera settings

| Method | Path | Body → response |
|---|---|---|
| GET | `/api/counting/cameras` | `[ { "id", "device_id", "name", "deleted", "count_enabled", "count_basis" } ]` (the alarm worker keeps the list in sync with the box) |
| PATCH | `/api/counting/cameras/{id}` | `{ "count_enabled"?: false, "count_basis"?: "merged" \| "face" \| "body" }` → the camera. `404` if unknown. Written to the audit log |

`count_enabled: false` leaves a camera out of the default camera list; its sightings are still built, and asking for it by `camera_id` still shows them.
