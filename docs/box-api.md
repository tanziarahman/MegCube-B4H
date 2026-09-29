# B4H Box WebAPI Reference

The MegCube B4H box has no public API documentation. Everything here was worked out by watching the box's own web UI in browser DevTools, and it is the reference the backend (`fastapi-app/`) is built on.

**Legend**

| Mark | Meaning |
|---|---|
| ✅ | Confirmed: seen in a captured request or response and working in the backend (payloads are checked by the backend's pytest suite) |
| ⚠️ | Assumed or partly known: works, but the meaning of some values is a guess |
| ❓ | Unknown: not captured yet |

> Samples below use placeholder IPs and passwords. Never paste real camera or box passwords into this file.

---

## Contents

1. [General conventions](#1-general-conventions)
2. [Authentication](#2-authentication)
3. [Devices (cameras)](#3-devices-cameras)
4. [Alarm history (recognition and captures)](#4-alarm-history-recognition-and-captures)
5. [Face library](#5-face-library)
6. [Tasks](#6-tasks)
7. [Time plans and system time](#7-time-plans-and-system-time)
8. [Images](#8-images)
9. [Live video](#9-live-video)
10. [Error codes](#10-error-codes)
11. [Not captured yet](#11-not-captured-yet)
12. [How to capture a new endpoint](#12-how-to-capture-a-new-endpoint)
13. [Testing against the box](#13-testing-against-the-box)

---

## 1. General conventions

| Item | Value |
|---|---|
| Base URL | `https://<box-ip>` (default `https://192.168.90.200`) |
| TLS | Self-signed certificate: clients must skip verification for the box only |
| Auth | Cookie header `sessionID=<session_id>` on every request |
| Body | JSON (`Content-Type: application/json`), except face-library writes, which are multipart |
| Queries | Most "get" operations are **POST** with a JSON filter body |
| Paging | `offset` + `size`. Record queries allow **at most 30** per request. |
| Timestamps | Epoch **milliseconds**, sent as **strings** in queries (`"1727582400000"`), computed in the **box's time zone** (the backend's `BOX_TIMEZONE`, default `Asia/Dhaka`) |

**Response envelope** (every JSON endpoint):

```json
{ "code": 0, "message": "success", "data": { } }
```

`code: 0` means success. Anything else is an error (see [§10](#10-error-codes)). `data` is missing on some write calls.

**Session rules** ✅
- An idle session expires after **about 30 seconds**, after which calls return code `512`. Log in again and retry.
- A session can run **only one query at a time**. Parallel calls fail with code `1073741825`, so serialise requests.
- **5 wrong passwords in a row lock the account.** The backend runs only one login at a time, and after the box refuses the credentials it makes **no further attempts until it is restarted**.
- Asking for a record page **past the last record** returns code `1073741825` (`general`), not an empty list. The backend checks `total_count` and turns this into an empty page.
- Some queries (e.g. a long date range) can take many seconds. The backend waits `B4H_TIMEOUT` seconds (default 15) and then answers `504`.

---

## 2. Authentication

A challenge–response login. The password is never sent in plain text.

### 2.1 Get a challenge ✅

`GET /auth/login/challenge?username=admin`

```json
{
  "code": 0,
  "data": { "session_id": "…", "salt": "…", "challenge": "…" }
}
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

Response: `code: 0`. `data.session_id`, if present, replaces the one from step 2.1. Send it as `Cookie: sessionID=…` from then on.

---

## 3. Devices (cameras)

### 3.1 List device configuration ✅

`POST /device_access/device_config`

```json
{ "offset": 0, "size": 100 }
```

Response `data` is an **array**:

```json
[
  {
    "device_id": 1,
    "device_name": "Hikvision",
    "proto": "rtsp",
    "channel_type": 1,
    "manufacturer": "…",
    "rtsp_param": {
      "user": "camuser",
      "password": "********",
      "url": "rtsp://camuser:********@192.168.1.24:554/ISAPI/Streaming/channels/201"
    }
  }
]
```

| Field | Notes |
|---|---|
| `device_id` | Integer, chosen by the client when adding (the box UI uses the lowest free id) |
| `proto` | `"rtsp"` ✅ · `"gb28181"` ❓ (payload not captured) |
| `channel_type` | `1` = Video ✅ · `2` = Picture ⚠️ (assumed) |
| `rtsp_param.url` | Contains the credentials as `user:password@host`. **The password is in plain text in this response**, so never forward it to a browser. |

### 3.2 Device status ✅ / ⚠️

`POST /device_access/device_state`

```json
{ "offset": 0, "size": 100 }
```

```json
[
  {
    "device_id": 1,
    "state": 0,
    "channels": [
      { "channel_id": 0, "channel_type": 1, "pull_stream": true, "stream_state": 0 }
    ]
  }
]
```

| Field | Notes |
|---|---|
| `state` | `0` = online ✅ (shown as "Online" by the box UI). Other values mean offline or error ⚠️; their exact meanings are unknown. |
| `channels[].pull_stream` | `true` while the box is pulling the camera's stream ⚠️ |
| `channels[].stream_state` | `0` = stream OK ⚠️ |

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

- `device_id` must not already be in use.
- Credentials go **both** in `user`/`password` **and** inside `url`. Percent-encode special characters in the URL part (`@` → `%40`).

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

Response: `{"code": 0, "message": "success"}`

- The whole config is sent, not just the changed fields. To "keep the current password", read it from [3.1](#31-list-device-configuration-) and send it back. The backend's `PUT /api/devices/{id}` does this when the password field is empty.
- As with add, credentials go both in `user`/`password` and inside `url`.

### 3.5 Delete a device ✅

`DELETE /device_access/device` (a JSON body on a DELETE)

```json
{ "device_id": 4 }
```

---

## 4. Alarm history (recognition and captures)

Recognition results and face/body captures are all stored as **alarms**. They are told apart by `major_type` / `minor_type`.

| major_type | minor_type | Meaning |
|---|---|---|
| `face_basic_business` | `face_comparison_successful` | Recognised person (matched the face library) ✅ |
| `face_basic_business` | `stranger` | Face not in the library ✅ |
| `face_basic_business` | `face_capture` | Face capture ✅ |
| `face_basic_business` | `body_capture` | Body capture ✅ |
| `structure` | `face`, `pedestrian`, `vehicle`, `non_motor`, `plate` | Structured detections (required alongside captures, see 4.2) ⚠️ |

> ⚠️ **Only use minor types listed by `GET /device_alarm/alarm_cap`.** An unknown `minor_type` **crashes the box's web server**.

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

- `ext` is sent by the box's own Records page. With `de_dup: 0`, every record comes back un-merged. Without `ext`, records may come back trimmed.
- `size` can be at most **30**.

Response `data`:

```json
{ "total_count": 123, "return_count": 10, "list": [ { "additional": { }, "global_info": { }, "faces": [ ] } ] }
```

### 4.2 Query capture records ✅

Same endpoint and shape as 4.1, but `alarm_type` **must contain a second `structure` entry**. Otherwise the box answers code `1073741831` (`not_support`).

```json
"alarm_type": [
  { "major_type": "face_basic_business", "minor_type": ["face_capture", "body_capture"] },
  { "major_type": "structure", "minor_type": ["face", "pedestrian", "vehicle", "non_motor", "plate"] }
]
```

Useful record fields:

| Path | Meaning |
|---|---|
| `additional.alarm_id` | Record id (used for delete) |
| `additional.alarm_minor` | `face_capture` / `body_capture` |
| `additional.device_id` | Camera that produced it |
| `global_info.time_ms` | Capture time (epoch ms) |
| `faces[0]` / `pedestrians[0]` | Target and its attributes; `.image_data.value` is the crop image path, `.track_id` the track |
| `full_images[0].image_data.value` | Panoramic image path (`""` if none) |

❓ Filtering by `device_id` inside `query_condition` hasn't been confirmed.

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

Deletion is permanent.

---

## 5. Face library

### 5.1 List groups ✅

`POST /face_manager/groups/query` (no body)

Response `data`: `{ "groups": [ { "group_id": "…", … } ] }`

### 5.2 List people ✅

`POST /face_manager/person/query`

```json
{ "offset": 0, "size": 30, "get_feature": false }
```

Response `data`: `{ "total_count": 57, "person_list": [ { "person_id": "…", "person_info": { "name": "…" }, … } ] }`

- `get_feature: true` includes the face feature data, which is **large**. Use `false` unless you need it.
- The face image path appears under varying keys (`face_image1`, `face_image`, `face_data`, `image_data`, or nested in `person_info`) ⚠️. The backend checks all of them.
- The box **keeps alarm history after a person is deleted**, so recognition records can refer to people who no longer exist.

### 5.3 Add a person ✅ (multipart)

`POST /face_manager/person` with `multipart/form-data`:

| Part | Content |
|---|---|
| `face1` | The face photo file (jpeg/png) |
| `person_info` | JSON string, below |

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

`data_size` is the byte length of the uploaded photo. `groups` is optional.

### 5.4 Update a person ✅ (multipart)

`PUT /face_manager/person`, with the same parts as 5.3. `face1` is optional and is only sent when replacing the photo.

```json
{
  "person_id": "…",
  "person_info": { "name": "Jane Doe", "birthday": "", "code": "", "gender": 0, "remarks": "" },
  "face_data": {
    "data_type": 0, "save_image": true,
    "data": [ { "data_size": 48213, "image_type": "jpeg" } ]
  }
}
```

Include `face_data` only when a new photo is attached. Even without a photo, send it as multipart with just the `person_info` part.

### 5.5 Set a person's groups ✅

`PUT /face_manager/person_bind`

```json
{ "person_id": "…", "face_groups": [ { "group_id": "1" }, { "group_id": "3" } ] }
```

The box UI skips this call when no group is selected, which leaves the current groups unchanged.

### 5.6 Delete people ✅

`DELETE /face_manager/person`

```json
{ "force": true, "all": false, "person_id_list": ["…"] }
```

---

## 6. Tasks

### 6.1 List analysis tasks ✅

`POST /intelli_manager/task_list`

```json
{ "offset": 0, "size": 50, "condition": {} }
```

Response `data`: `{ "list": [ { "task_name": "…", "device_list": [ { "device_id": 1 } ] } ] }`

Used to show which task each camera runs.

---

## 7. Time plans and system time

Time plans (schedules) say when rules are active. There are two kinds: **regular** (`schedule_plan_type: 1`, weekly) and **festival** (`schedule_plan_type: 2`).

### 7.1 Box time settings ✅ / ⚠️

`POST /system/get_system_time` (no body): time zone, time mode and DST settings.

```json
{ "time_zone": "…", "time_mode": "…", "time_dst": { "dst_enable": 0, "offset": 0 } }
```

`POST /system/get_time_info` (no body): the box's current clock.

```json
{ "time": "2026-09-29 14:07:00" }
```

⚠️ Some firmware doesn't have these endpoints (the box answers code `404`). The backend then treats them as empty and falls back to its own clock (`clock_source: "backend_fallback"`).

### 7.2 List plans ✅

`POST /device_rules/schedule_plan/query`

```json
{ "offset": 0, "size": 100, "schedule_plan_type": 1 }
```

The box UI asks for `size: 100` for regular plans and `size: 50` for festival plans. Each plan has `schedule_plan_id`, `schedule_plan_name`, `schedule_plan_type` and `week_schedule`. `ext.default: 1` marks the built-in default plan ⚠️.

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

- `week_schedule` keys are the days `"1"`…`"7"` ⚠️ (the portal treats 1 as the first day of its week). Each value is a list of `"HH:MM:SS-HH:MM:SS"` windows. An empty list means "off all day".
- `bind_schedule_plan`: what the plan is attached to. It is passed through unchanged; its contents haven't been documented yet ❓.

### 7.4 Update a plan ✅

`PUT /device_rules/schedule_plan`, with the same body as 7.3 plus `"schedule_plan_id": "<id>"`.

### 7.5 Delete a plan ✅

`DELETE /device_rules/schedule_plan`

```json
{ "schedule_plan_id": "<id>", "schedule_plan_type": 1 }
```

### 7.6 Close stream subscriptions ✅

The box UI's time-plan page opens live subscriptions. These close them again:

`DELETE /media_video/subscribe_stream` with `{ "handle": 12 }`
`DELETE /device_alarm/subscribe_stream` with `{ "handle": 7 }`

Send one request per handle. Opening a subscription (`media_video/subscribe_stream`) hasn't been captured ❓.

---

## 8. Images

### 8.1 Get an image ✅

`GET /device_storage/get_image?image_uri=<path>` with the session cookie.

Returns the raw image bytes. Paths come from records and the face library, for example:

- `./record_…/….jpg` (alarm and capture images)
- `/home/appdata/…/….jpg` or `group/…` (face-library images)

⚠️ Some images are also reachable at `/<absolute path>` or `/web/<path>`. The backend tries these as fallbacks. On errors the box returns JSON or HTML instead of an image, so check the body. An expired session here also returns JSON code `512`.

---

## 9. Live video

The box's Preview page uses `media_video/subscribe_stream` plus a **Windows browser plugin** ❓. A normal browser can't use it, so the portal reads each camera's RTSP URL from [3.1](#31-list-device-configuration-) and has the backend convert it with ffmpeg:

```
ffmpeg -rtsp_transport tcp -i <rtsp url> -an -vf "scale='min(960,iw)':-2" -r 10 -q:v 7 -f mjpeg pipe:1
```

- **Sub-stream vs main stream** ⚠️ (Hikvision cameras): the stored URL ends in `/channels/<n>01` (main stream). Replacing the ending with `…02` gives the lighter sub-stream, e.g. `/channels/201` → `/channels/202`. The portal uses the sub-stream for grid tiles and the main stream for HD or full screen. Other URL formats are left unchanged.
- Each open video is one ffmpeg process. The backend caps them with `MAX_STREAMS` (default 16).

---

## 10. Error codes

| code | message | Meaning / what to do |
|---|---|---|
| `0` | `success` | OK |
| `512` | | Session expired (idle for ~30 s). Log in again and retry once. ✅ |
| `1073741825` | `general` | Catch-all. Seen with two requests at once on one session (serialise calls), and when asking for a record page past the end (treat as empty) ✅ |
| `1073741831` | `not_support` | Request shape not supported, e.g. a capture query without the `structure` entry ✅ |
| `404` | | Endpoint not available on this firmware (seen for the optional `/system/…` time calls) ⚠️ |
| other | | Unknown ❓. Record it here when you find out. |

---

## 11. Not captured yet

| Feature | What's needed |
|---|---|
| Add or edit **Picture** devices (`channel_type` 2) | Capture "New device" with type Picture |
| **GB28181** devices | Capture "New device" with protocol GB28181 |
| Meaning of `device_state.state` ≠ 0 | Unplug a camera and watch the value |
| Device filter for alarm history | Filter by camera on the box's Records page |
| Contents of `bind_schedule_plan` | Attach a time plan to a rule or camera in the box UI |
| Opening a stream subscription (`media_video/subscribe_stream`) | Open the box's Preview page |
| People counting, alarms, box settings | Capture the relevant pages |

---

## 12. How to capture a new endpoint

1. Log in to the box's web UI (`https://<box-ip>`) in Chrome or Edge.
2. Press **F12**, open **Network**, and turn on **Preserve log**. Filter by **Fetch/XHR**.
3. Do the action once in the box UI (add, edit, delete, search…).
4. Click the request that appears and copy:
   - **Headers**: the request URL and method
   - **Payload**: use *view source* for the exact JSON (for multipart, note each part's name)
   - **Response**: the full JSON
5. Add it to this file with a ✅, **replacing any real passwords with placeholders**.
6. Implement it in `fastapi-app/routers/…` with `box.call(...)`, then add the frontend client in `client/src/lib/`.
7. Add a pytest test that uses the captured response as `fake_box` data and asserts the backend sends **exactly** the captured payload (see below).

---

## 13. Testing against the box

**Automated tests never touch the box.** `fastapi-app/tests/conftest.py` replaces the box with a `FakeBox`:

```python
def test_edit_keeps_password(client, fake_box):
    fake_box.replies[("POST", "/device_access/device_config")] = DEVICE_CONFIG   # captured sample
    fake_box.replies[("PUT", "/device_access/device_config")] = None
    client.put("/api/devices/2", json={"name": "Gate", "url": "rtsp://192.168.1.24:554/x",
                                       "user": "camuser", "password": ""})
    sent = fake_box.sent("PUT", "/device_access/device_config")[0]
    assert sent["rtsp_param"]["password"] == "s3cret!"   # the stored one, not ""
```

- Keep sample responses (`DEVICE_CONFIG`, `DEVICE_STATE`, `TASK_LIST` in `conftest.py`) copied from real captures, with passwords replaced.
- A call to a box endpoint that the test didn't set up **fails the test**, so every box request is intentional.
- Box quirks that are tested include session expiry (`512`) with exactly one re-login, no second login after a refused password, the `general` error on pages past the end, capture queries always including the `structure` entry (without it the box answers `1073741831`), and invalid `minor_type` values being refused before they reach the box.

**Checking against the real box:** `fastapi-app/tests/live_check.py` runs about 25 **read-only** checks through the running backend (records, people, captures, devices, images, one live video frame, input validation, API key). Run it after a box firmware update to catch changes in the API described here. See the backend README for how to run it.