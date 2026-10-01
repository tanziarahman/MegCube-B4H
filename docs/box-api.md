# B4H Box API Reference

The endpoints of the MegCube B4H box that the portal backend calls: what it sends, what the box returns, and the box's quirks.

> **Audience:** backend developers.
> The box has **no public API documentation**. Everything here was worked out by watching the box's own web UI in browser DevTools. For the portal's own API (what the backend exposes to the frontend), see the [Backend API reference](backend-api.md).

**Confidence legend**

| Mark | Meaning |
|---|---|
| ✅ | Confirmed: seen in a captured request/response and working in the backend (payloads are checked by the pytest suite) |
| ⚠️ | Partly known: works, but some field names or values are inferred (e.g. the code tries several keys) |
| ❓ | Unknown: not captured yet |

> Samples use placeholder IPs and passwords. **Never paste real camera or box passwords into this file.**

---

## Contents

1. [General conventions](#1-general-conventions)
2. [Authentication](#2-authentication)
3. [Devices (cameras)](#3-devices-cameras)
4. [Alarm history (recognition and captures)](#4-alarm-history-recognition-and-captures)
5. [Face library](#5-face-library)
6. [Analysis tasks](#6-analysis-tasks)
7. [Time plans and system time](#7-time-plans-and-system-time)
8. [Images](#8-images)
9. [Live video](#9-live-video)
10. [Error codes](#10-error-codes)
11. [Endpoint index](#11-endpoint-index)
12. [Not captured yet](#12-not-captured-yet)
13. [How to capture a new endpoint](#13-how-to-capture-a-new-endpoint)

---

## 1. General conventions

| Item | Value |
|---|---|
| Base URL | `https://<box-ip>` (default `https://192.168.90.200`, set with `B4H_BASE_URL`) |
| TLS | Self-signed certificate: skip verification **for the box only** |
| Auth | Header `Cookie: sessionID=<session_id>` on every request (see [§2](#2-authentication)) |
| Body | JSON (`Content-Type: application/json`), except face-library writes, which are `multipart/form-data` |
| Reads | Most "get" operations are **POST** with a JSON filter body |
| Deletes | Usually **DELETE with a JSON body** |
| Paging | `offset` + `size`. Record queries allow **at most 30** per request. |
| Timestamps | Epoch **milliseconds**. In queries they are sent as **strings** (`"1727582400000"`), computed in the **box's time zone** (`BOX_TIMEZONE`). |

### Response envelope

Every JSON endpoint answers with the same wrapper, **always with HTTP 200**, even on errors:

```json
{ "code": 0, "message": "success", "data": { } }
```

- `code: 0` = success. Anything else is an error ([§10](#10-error-codes)).
- `data` is the payload. It is missing or `null` on some write calls.
- The backend's `box.call()` returns `data` on success and raises `B4HError(code, message, path)` otherwise, which the frontend sees as **HTTP 502**.

### Session rules ✅

| Rule | Backend handling |
|---|---|
| An idle session expires after **~30 s**; calls then return code `512`. | Log in again and retry **once**; parallel requests share one re-login. |
| A session runs **one query at a time**; parallel calls fail with `1073741825`. | All calls are serialised with a lock. |
| **5 wrong passwords in a row lock the account.** | One login at a time; after a refusal, **no more attempts until restart**. |
| A record page **past the last record** returns `1073741825` (`general`), not an empty list. | The backend checks `total_count` and returns an empty page. |
| Long queries (e.g. a wide date range) can take many seconds. | Waits `B4H_TIMEOUT` s (default 15), then answers `504`. |

---

## 2. Authentication

A challenge–response login. The password is never sent in plain text.

### 2.1 Get a challenge ✅

`GET /auth/login/challenge?username=admin`

**Response**

```json
{ "code": 0, "data": { "session_id": "…", "salt": "…", "challenge": "…" } }
```

### 2.2 Log in ✅

`POST /auth/login`
Header: `Cookie: sessionID=<session_id from 2.1>`

```json
{
  "session_id": "<session_id from 2.1>",
  "username": "admin",
  "password": "<sha256_hex(password + salt + challenge)>"
}
```

**Response:** `code: 0` on success. If `data.session_id` is present it replaces the one from 2.1. Send it as `Cookie: sessionID=…` from then on. A non-zero `code` means wrong credentials or a locked account.

---

## 3. Devices (cameras)

### 3.1 List device configuration ✅

`POST /device_access/device_config`

```json
{ "offset": 0, "size": 100 }
```

**Response `data`**: an **array**

```json
[
  {
    "device_id": 1,
    "device_name": "Hikvision",
    "proto": "rtsp",
    "channel_type": 1,
    "manufacturer": "unknown",
    "rtsp_param": {
      "user": "camuser",
      "password": "s3cret!",
      "url": "rtsp://camuser:s3cret!@192.168.1.24:554/ISAPI/Streaming/channels/201"
    }
  }
]
```

| Field | Notes |
|---|---|
| `device_id` | Integer, chosen by the client when adding (the box UI uses the lowest free id) ✅ |
| `proto` | `"rtsp"` ✅ · `"gb28181"` ❓ |
| `channel_type` | `1` = Video ✅ · `2` = Picture ⚠️ (assumed) |
| `rtsp_param.url` | Contains credentials as `user:password@host`. **The password is in plain text here**, so never forward it to a browser. |

**Used by:** `GET /api/devices/detail`, `GET /api/devices`, `POST /api/devices`, `PUT/DELETE /api/devices/{id}`, `GET /api/preview/cameras`, `GET /api/preview/{id}/stream`, `GET /api/dashboard/summary`.

### 3.2 Device status ✅

`POST /device_access/device_state`

```json
{ "offset": 0, "size": 100 }
```

**Response `data`**

```json
[
  {
    "device_id": 1,
    "state": 0,
    "channels": [ { "channel_id": 0, "channel_type": 1, "pull_stream": true, "stream_state": 0 } ]
  }
]
```

| Field | Notes |
|---|---|
| `state` | `0` = online ✅. Other values (e.g. `3`) mean offline or error ⚠️; exact meanings unknown. |
| `channels[].pull_stream` | `true` while the box is pulling the camera's stream ⚠️ |
| `channels[].stream_state` | `0` = stream OK ⚠️ (not used by the portal) |

**Used by:** `GET /api/devices/detail`, `GET /api/preview/cameras`, `GET /api/dashboard/summary`.

### 3.3 Add a device ✅ (RTSP video only)

`POST /device_access/device`

```json
{
  "device_id": 4,
  "device_name": "Entrance",
  "proto": "rtsp",
  "rtsp_param": {
    "user": "camuser",
    "password": "secret",
    "url": "rtsp://camuser:secret@192.168.1.30:554/stream1"
  }
}
```

**Response:** `{ "code": 0, "message": "success" }`

- `device_id` must not already be in use.
- Credentials go **both** in `user` / `password` **and** inside `url`. Percent-encode special characters in the URL (`@` → `%40`).

**Used by:** `POST /api/devices`.

### 3.4 Update a device ✅

`PUT /device_access/device_config`

```json
{
  "device_id": 2,
  "device_name": "IPCAM-D3",
  "proto": "rtsp",
  "rtsp_param": {
    "user": "camuser",
    "password": "secret",
    "url": "rtsp://camuser:secret@192.168.1.24:554/ISAPI/Streaming/channels/301"
  }
}
```

**Response:** `{ "code": 0, "message": "success" }`

- Send the **whole** config, not just the changed fields. To "keep the current password", read it from [3.1](#31-list-device-configuration-) and send it back.

**Used by:** `PUT /api/devices/{id}`.

### 3.5 Delete a device ✅

`DELETE /device_access/device`

```json
{ "device_id": 4 }
```

**Used by:** `DELETE /api/devices/{id}`.

---

## 4. Alarm history (recognition and captures)

Recognition results and face/body captures are all stored as **alarms**, told apart by `major_type` / `minor_type`:

| major_type | minor_type | Meaning |
|---|---|---|
| `face_basic_business` | `face_comparison_successful` | Recognised person (matched the face library) ✅ |
| `face_basic_business` | `stranger` | Face not in the library ✅ |
| `face_basic_business` | `face_capture` | Face capture ✅ |
| `face_basic_business` | `body_capture` | Body capture ✅ |
| `structure` | `face`, `pedestrian`, `vehicle`, `non_motor`, `plate` | Structured detections; required alongside capture queries (4.2) ⚠️ |

`face_basic_business` is configurable in the backend as `RECOG_MAJOR`.

> ⚠️ **Only use minor types listed by `GET /device_alarm/alarm_cap`.** An unknown `minor_type` **crashes the box's web server**. The backend only accepts a fixed list.

### 4.1 Query recognition records ✅

`POST /device_alarm/alarm_history`

```json
{
  "offset": 0,
  "size": 10,
  "query_condition": {
    "start_time": "1727546400000",
    "end_time": "1727632799000",
    "alarm_type": [
      { "major_type": "face_basic_business", "minor_type": ["face_comparison_successful"] }
    ],
    "ext": { "query_type": 0, "de_dup": 0 }
  }
}
```

- `ext` is what the box's own Records page sends. With `de_dup: 0`, every record comes back un-merged; without `ext`, records may be trimmed.
- `size` ≤ **30**.

**Response `data`**

```json
{ "total_count": 123, "return_count": 10, "list": [ { "…record, see 4.4…": "" } ] }
```

**Used by:** `GET /api/recognition`, `GET /api/dashboard/summary`.

### 4.2 Query capture records ✅

Same endpoint and response as 4.1, but `alarm_type` **must include a second `structure` entry**, or the box answers code `1073741831` (`not_support`). No `ext` is sent.

```json
"alarm_type": [
  { "major_type": "face_basic_business", "minor_type": ["face_capture", "body_capture"] },
  { "major_type": "structure", "minor_type": ["face", "pedestrian", "vehicle", "non_motor", "plate"] }
]
```

For "Face only" or "Body only", the first entry has just `["face_capture"]` or `["body_capture"]`; the `structure` entry is kept as-is.

❓ Filtering by `device_id` inside `query_condition` hasn't been confirmed.

**Used by:** `GET /api/capture`, `GET /api/dashboard/summary`.

### 4.3 Delete records ✅

`DELETE /device_alarm/alarm_history`

```json
{
  "condition": {
    "type": "alarm_id",
    "id_list": [12345],
    "alarm_type": [
      { "major_type": "face_basic_business", "minor_type": ["face_comparison_successful", "stranger"] }
    ]
  }
}
```

Deletion is permanent. **Used by:** `DELETE /api/recognition/{alarm_id}`.

### 4.4 Record structure

What one entry of `data.list` looks like. Paths marked ✅ are read directly by the code; ⚠️ means the code searches several possible keys because the exact one isn't confirmed.

```json
{
  "additional": {
    "alarm_id": 12345,
    "alarm_minor": "face_comparison_successful",
    "device_id": 1
  },
  "global_info": { "time_ms": "1727600000000" },
  "faces": [
    {
      "track_id": 5610081,
      "image_data": { "image_data_format": 2, "value": "./record_CHN0/…/face.jpg" },
      "age": 31, "gender": 2, "wear_hat": 2, "wear_glasses": 2, "wear_respirator": 2,
      "hair_style": 13, "beard_class": 2,
      "recognition_info": [
        {
          "person_uuid": "17",
          "person_name": "Ada Lovelace",
          "face_score": 96,
          "image_data": { "image_data_format": 2, "value": "/home/appdata/…/17.jpg" },
          "group_info": [ { "group_name": "Staff" } ]
        }
      ]
    }
  ],
  "pedestrians": [ { "track_id": 5610090, "image_data": { "value": "./record_CHN0/…/body.jpg" } } ],
  "full_images": [ { "image_data": { "image_data_format": 2, "value": "./record_CHN0/…/full.jpg" } } ]
}
```

| Path | Meaning | |
|---|---|---|
| `additional.alarm_id` | Record id, used for delete | ✅ |
| `additional.alarm_minor` | The minor type of this record | ✅ |
| `additional.device_id` | Camera that produced it | ✅ |
| `global_info.time_ms` | Event time (epoch ms) | ✅ |
| `faces[0]` | The face (recognition and face captures) | ✅ |
| `pedestrians[0]` | The body (body captures) | ✅ |
| `faces[0].image_data.value` | Face crop image path (`image_data_format: 2` = a path) | ✅ |
| `faces[0].track_id` | The person's track through this camera | ✅ |
| `faces[0].age`, `gender`, `wear_hat`, `wear_glasses`, `wear_respirator`, `hair_style`, `beard_class` | Face attributes as numeric codes (table below) | ✅ |
| `faces[0].recognition_info[]` | Library candidates, **best match first**. The box pads it with empty entries. | ✅ |
| `recognition_info[].person_uuid` | Library person id (same value as `person_id` in [5.2](#52-list-people-)) | ⚠️ |
| `recognition_info[].person_name` / `name` | Library person's name | ⚠️ |
| `recognition_info[].face_score` | Similarity, 0–100 (sometimes 0–1) | ✅ |
| `recognition_info[].image_data.value` | Library (base) photo path | ✅ |
| `recognition_info[].group_info[].group_name` | Groups of that person | ✅ |
| liveness | Searched under `liveness_score`, `living_score`, `liveness`, `live_score`, `living_fraction`; 0–1 or 0–100 | ⚠️ |
| `full_images[0].image_data.value` | Panoramic image path (`""` if none) | ✅ |

**Face attribute codes** (from the box web UI's language file):

| Code | `gender` | `wear_hat` / `wear_glasses` / `wear_respirator` (mask) |
|---|---|---|
| 1 | Unknown | Unknown |
| 2 | Male | Not wearing |
| 3 | Female | Wearing |

`hair_style`: 1 Unknown, 2 Flat top, 3 Middle part, 4 Side part, 5 Frontal baldness, 6 Top baldness, 7 Baldness, 8 Curly, 9 Waves, 10 Braid, 11 Updo, 12 Shoulder-length, 13 Short, 14 Long.
`beard_class`: 1 Unknown, 2 No beard, 3 Walrus moustache, 4 Whiskers, 5 Toothbrush moustache, 6 Becoming moustache, 7 Goatee, 8 White beard, 9 Imperial.

Body-capture (`pedestrians[0]`) attribute codes have **no known legend** yet ❓; the Captures page shows them raw.

---

## 5. Face library

### 5.1 List groups ✅

`POST /face_manager/groups/query` (no body)

**Response `data`**

```json
{ "groups": [ { "group_id": "1", "group_name": "Staff" } ] }
```

⚠️ The portal displays `group_name`; check the box's actual key if names appear blank.
**Used by:** `GET /api/personnel/groups`.

### 5.2 List people ✅

`POST /face_manager/person/query`

```json
{ "offset": 0, "size": 30, "get_feature": false }
```

**Response `data`**

```json
{
  "total_count": 57,
  "person_list": [
    {
      "person_id": "17",
      "person_info": { "name": "Ada Lovelace", "code": "ADA-1", "birthday": "1815-12-10", "gender": 0, "remarks": "" },
      "groups": [ { "group_id": "1", "group_name": "Staff" } ],
      "face_image1": "/home/appdata/…/17.jpg"
    }
  ]
}
```

- `get_feature: true` adds face-feature data, which is **large**. Use `false` unless you need it.
- Some firmware returns `count` instead of `total_count` ⚠️.
- The face image path appears under **varying keys** ⚠️: `face_image1`, `face_image`, `face_images`, `face_data`, `image_data`, or nested in `person_info` / `face_info` / `face_spec`, either as a string or an object with `image_uri` / `uri` / `url` / `value`. The backend normalises it to `face_image1`.
- The box **keeps alarm history after a person is deleted**, so records can refer to people who no longer exist.

**Used by:** `GET /api/people` (`get_feature: false`, all pages), `GET /api/personnel`.

### 5.3 Add a person ✅ (multipart)

`POST /face_manager/person` with `multipart/form-data`:

| Part | Content |
|---|---|
| `face1` | The face photo file (JPEG/PNG) |
| `person_info` | JSON string (below) |

```json
{
  "person_info": {
    "name": "Jane Doe", "birthday": "", "code": "", "gender": 0,
    "id": "", "remarks": "", "type": ""
  },
  "face_data": {
    "data_type": 0, "save_image": true, "feature_version": "",
    "data": [ { "data_size": 48213 } ]
  },
  "groups": [ { "group_id": "1" } ]
}
```

`data_size` is the photo's byte length. `groups` is optional. The response `data` shape isn't documented ❓.
**Used by:** `POST /api/personnel`.

### 5.4 Update a person ✅ (multipart)

`PUT /face_manager/person`, with the same parts as 5.3. `face1` is only sent when replacing the photo.

```json
{
  "person_id": "17",
  "person_info": { "name": "Jane Doe", "birthday": "", "code": "", "gender": 0, "remarks": "" },
  "face_data": {
    "data_type": 0, "save_image": true,
    "data": [ { "data_size": 48213, "image_type": "jpeg" } ]
  }
}
```

Include `face_data` only with a new photo. Without a photo, still send multipart with just the `person_info` part.
**Used by:** `PUT /api/personnel/{id}`.

### 5.5 Set a person's groups ✅

`PUT /face_manager/person_bind`

```json
{ "person_id": "17", "face_groups": [ { "group_id": "1" }, { "group_id": "3" } ] }
```

The box UI skips this call when no group is selected, which leaves the groups unchanged.
**Used by:** `PUT /api/personnel/{id}`.

### 5.6 Delete people ✅

`DELETE /face_manager/person`

```json
{ "force": true, "all": false, "person_id_list": ["17"] }
```

**Used by:** `DELETE /api/personnel/{id}`.

---

## 6. Analysis tasks

### 6.1 List analysis tasks ✅

`POST /intelli_manager/task_list`

```json
{ "offset": 0, "size": 50, "condition": {} }
```

**Response `data`**

```json
{ "list": [ { "task_name": "FR", "device_list": [ { "device_id": 1 } ] } ] }
```

Shows which task runs on each camera. **Used by:** `GET /api/preview/cameras`, `GET /api/dashboard/summary`.

---

## 7. Time plans and system time

Time plans (schedules) say when rules are active. **Regular** = `schedule_plan_type: 1` (weekly); **festival** = `2`.

### 7.1 Box time settings ✅

`POST /system/get_system_time` (no body): time zone, time mode, DST.

```json
{ "time_zone": "…", "time_mode": "…", "time_dst": { "dst_enable": 0, "offset": 0 } }
```

`POST /system/get_time_info` (no body): the box's current clock.

```json
{ "time": "2026-09-29 14:07:00" }
```

⚠️ Some firmware lacks these endpoints (box code `404`). The backend treats that as empty and falls back to its own clock.
**Used by:** `GET /api/timeplans/time`, `GET /api/dashboard/summary`.

### 7.2 List plans ✅

`POST /device_rules/schedule_plan/query`

```json
{ "offset": 0, "size": 100, "schedule_plan_type": 1 }
```

The box UI asks for `size: 100` for regular plans and `size: 50` for festival plans.

**Response `data`**

```json
{
  "schedule_plans": [
    {
      "schedule_plan_id": "1",
      "schedule_plan_name": "All day",
      "schedule_plan_type": 1,
      "week_schedule": { "1": ["00:00:00-23:59:59"], "2": [], "3": [], "4": [], "5": [], "6": [], "7": [] },
      "ext": { "default": 1 }
    }
  ]
}
```

`ext.default: 1` marks the built-in default plan ⚠️.
**Used by:** `GET /api/timeplans/regular`, `GET /api/timeplans/festival`.

### 7.3 Create a plan ✅

`POST /device_rules/schedule_plan`

```json
{
  "schedule_plan_name": "Office hours",
  "schedule_plan_type": 1,
  "week_schedule": {
    "1": ["09:00:00-17:00:00"],
    "2": ["09:00:00-17:00:00"],
    "3": [], "4": [], "5": [], "6": [], "7": []
  },
  "bind_schedule_plan": []
}
```

- `week_schedule` keys `"1"`…`"7"`; the portal treats `"1"` as **Monday** ⚠️. Each value is a list of `"HH:MM:SS-HH:MM:SS"` windows; an empty list means off all day.
- `bind_schedule_plan`: what the plan is attached to. Passed through unchanged; contents undocumented ❓.
- The response doesn't include the new id; re-query to find it.

**Used by:** `POST /api/timeplans`.

### 7.4 Update a plan ✅

`PUT /device_rules/schedule_plan`: same body as 7.3 plus `"schedule_plan_id": "<id>"`.
**Used by:** `PUT /api/timeplans/{id}`.

### 7.5 Delete a plan ✅

`DELETE /device_rules/schedule_plan`

```json
{ "schedule_plan_id": "<id>", "schedule_plan_type": 1 }
```

**Used by:** `DELETE /api/timeplans/{id}`.

### 7.6 Close stream subscriptions ✅

The box UI's time-plan page opens live subscriptions; these close them. Send one request per handle.

`DELETE /media_video/subscribe_stream` with `{ "handle": 12 }`
`DELETE /device_alarm/subscribe_stream` with `{ "handle": 7 }`

Opening a subscription (`media_video/subscribe_stream`) hasn't been captured ❓.
**Used by:** `DELETE /api/timeplans/stream-subscriptions`.

---

## 8. Images

### 8.1 Get an image ✅

`GET /device_storage/get_image?image_uri=<path>` with the session cookie.

Returns the **raw image bytes**. Paths come from records and the face library, e.g.:

- `./record_CHN0/…/….jpg` (alarm and capture images)
- `/home/appdata/…/….jpg` or `group/…` (face-library images)

⚠️ Some images are also reachable at `/<absolute path>` or `/web/<path>`; the backend tries these as fallbacks. On errors the box returns **JSON or HTML instead of an image** (still HTTP 200), so check the body. An expired session here returns JSON code `512`.
**Used by:** `GET /api/image`.

---

## 9. Live video

The box's Preview page uses `media_video/subscribe_stream` plus a **Windows browser plugin** ❓. A normal browser can't use that, so the backend reads each camera's RTSP URL from [3.1](#31-list-device-configuration-) and converts it with ffmpeg:

```
ffmpeg -loglevel error -rtsp_transport tcp -i <rtsp url> -an -vf "scale='min(<width>,iw)':-2" -r <fps> -q:v 7 -f mjpeg pipe:1
```

- **Sub-stream vs main stream** ⚠️ (Hikvision): stored URLs end in `/channels/<n>01` (main stream). Replacing the ending with `…02` gives the lighter sub-stream (`/channels/201` → `/channels/202`). Other URL formats are left unchanged.
- One ffmpeg process per open video, capped by `MAX_STREAMS` (default 16).

**Used by:** `GET /api/preview/{id}/stream`.

---

## 10. Error codes

| code | message | Meaning / what to do |
|---|---|---|
| `0` | `success` | OK |
| `512` | | Session expired (idle ~30 s). Log in again and retry once. ✅ |
| `1073741825` | `general` | Catch-all. Seen with two requests at once on one session (serialise calls), and on a record page past the end (treat as empty). ✅ |
| `1073741831` | `not_support` | Request shape not supported, e.g. a capture query without the `structure` entry. ✅ |
| `404` | | Endpoint not on this firmware (seen for the optional `/system/…` time calls). ⚠️ |
| other | | Unknown ❓. Record it here when you find out. |

The backend turns any non-zero code into **HTTP 502** with `detail: "Box error on <path>: <message> (code N)"`.

---

## 11. Endpoint index

| Method | Box endpoint | Section | Portal route(s) |
|---|---|---|---|
| GET | `/auth/login/challenge` | [2.1](#21-get-a-challenge-) | (login, internal) |
| POST | `/auth/login` | [2.2](#22-log-in-) | (login, internal) |
| POST | `/device_access/device_config` | [3.1](#31-list-device-configuration-) | devices, preview, dashboard |
| POST | `/device_access/device_state` | [3.2](#32-device-status-) | devices/detail, preview/cameras, dashboard |
| POST | `/device_access/device` | [3.3](#33-add-a-device--rtsp-video-only) | `POST /api/devices` |
| PUT | `/device_access/device_config` | [3.4](#34-update-a-device-) | `PUT /api/devices/{id}` |
| DELETE | `/device_access/device` | [3.5](#35-delete-a-device-) | `DELETE /api/devices/{id}` |
| POST | `/device_alarm/alarm_history` | [4.1](#41-query-recognition-records-), [4.2](#42-query-capture-records-) | recognition, capture, dashboard |
| DELETE | `/device_alarm/alarm_history` | [4.3](#43-delete-records-) | `DELETE /api/recognition/{id}` |
| POST | `/face_manager/groups/query` | [5.1](#51-list-groups-) | `GET /api/personnel/groups` |
| POST | `/face_manager/person/query` | [5.2](#52-list-people-) | `GET /api/people`, `GET /api/personnel` |
| POST | `/face_manager/person` (multipart) | [5.3](#53-add-a-person--multipart) | `POST /api/personnel` |
| PUT | `/face_manager/person` (multipart) | [5.4](#54-update-a-person--multipart) | `PUT /api/personnel/{id}` |
| PUT | `/face_manager/person_bind` | [5.5](#55-set-a-persons-groups-) | `PUT /api/personnel/{id}` |
| DELETE | `/face_manager/person` | [5.6](#56-delete-people-) | `DELETE /api/personnel/{id}` |
| POST | `/intelli_manager/task_list` | [6.1](#61-list-analysis-tasks-) | preview/cameras, dashboard |
| POST | `/system/get_system_time` | [7.1](#71-box-time-settings-) | timeplans/time, dashboard |
| POST | `/system/get_time_info` | [7.1](#71-box-time-settings-) | timeplans/time, dashboard |
| POST | `/device_rules/schedule_plan/query` | [7.2](#72-list-plans-) | timeplans/regular, timeplans/festival |
| POST | `/device_rules/schedule_plan` | [7.3](#73-create-a-plan-) | `POST /api/timeplans` |
| PUT | `/device_rules/schedule_plan` | [7.4](#74-update-a-plan-) | `PUT /api/timeplans/{id}` |
| DELETE | `/device_rules/schedule_plan` | [7.5](#75-delete-a-plan-) | `DELETE /api/timeplans/{id}` |
| DELETE | `/media_video/subscribe_stream` | [7.6](#76-close-stream-subscriptions-) | `DELETE /api/timeplans/stream-subscriptions` |
| DELETE | `/device_alarm/subscribe_stream` | [7.6](#76-close-stream-subscriptions-) | `DELETE /api/timeplans/stream-subscriptions` |
| GET | `/device_storage/get_image` | [8.1](#81-get-an-image-) | `GET /api/image` |

---

## 12. Not captured yet

| Feature | What's needed |
|---|---|
| Add or edit **Picture** devices (`channel_type` 2) | Capture "New device" with type Picture |
| **GB28181** devices | Capture "New device" with protocol GB28181 |
| Meaning of `device_state.state` ≠ 0 | Unplug a camera and watch the value |
| Device filter for alarm history | Filter by camera on the box's Records page |
| Body-capture attribute legend | Find the box web UI's language strings for pedestrian attributes |
| Contents of `bind_schedule_plan` | Attach a time plan to a rule or camera in the box UI |
| Opening a stream subscription (`media_video/subscribe_stream`) | Open the box's Preview page |
| Alarms (rule events), people counting, box settings | Capture the relevant pages |
| Response `data` of add/update/delete person | Capture the responses |

---

## 13. How to capture a new endpoint

1. Log in to the box's web UI (`https://<box-ip>`) in Chrome or Edge.
2. Press **F12**, open **Network**, turn on **Preserve log**, and filter by **Fetch/XHR**.
3. Do the action once in the box UI (add, edit, delete, search…).
4. Click the request and copy:
   - **Headers**: request URL and method
   - **Payload**: use *view source* for the exact JSON (for multipart, note each part's name)
   - **Response**: the full JSON
5. Add it to this file with a ✅, **replacing any real passwords with placeholders**.
6. Implement it in `fastapi-app/routers/…` with `box.call(...)`, document the new route in [backend-api.md](backend-api.md), and add the frontend client in `client/src/lib/`.
7. Add a pytest test that uses the captured response as `fake_box` data and asserts the backend sends **exactly** the captured payload. See [fastapi-app/README.md → Testing](../fastapi-app/README.md#testing).

After a box firmware update, run `fastapi-app/tests/live_check.py` (read-only, against the real box) to catch changes to anything described here.
