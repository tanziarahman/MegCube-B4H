# Data and Selected ML Models

This document focuses on the three selected models and the data they use in the B4H Portal.

## Data available

When the portal database is enabled, the backend turns B4H box records into event rows and groups
related records into walk-pasts called **sightings**. The box also supplies snapshots, but the
database normally stores their paths, not the image files themselves.

| Data | Example fields and shape |
|---|---|
| **Events** — one normalized box record per row | `occurred_at` (event time), `received_at` (portal receipt time), `camera_id`, `kind` (`matched`, `stranger`, `face_capture`, `body_capture`), `face_track_id`, `body_track_id`, `person_uuid`, `group_names`, `match_score`, `liveness_score`, `attributes`, and image paths. |
| **Sightings** — grouped events for one walk-past | `camera_id`, `first_seen_at`, `last_seen_at`, `event_count`, face/body track IDs, recognition result, and optional face/body fingerprints. |
| **Count buckets** — counts per camera and 15-minute interval | `local_date`, `local_hour`, `iso_dow` (weekday), walk-past counts, event counts and counts split by event kind. |
| **Alarms and reviews** | Incident time, camera, rule, event count, delay, status (`open`, `acknowledged`, `resolved`, `false_alarm`) and optional staff note. A status is not automatically a verified label. |
| **Camera context** | Camera ID/name, current online/stream status, assigned analysis task, and regular/festival time plans. Some status is read live from the box rather than stored as a complete history. |
| **Images** | Face crop, body crop and full-scene image paths from box records. The backend can fetch existing images from the box, but old images may be rotated out. |

The normalizer uses the first face/body entry in each record. It retains the four event kinds above;
vehicle, plate and other structure detections are not currently saved as normalized event rows.
Match and liveness scores may be absent and are box scores, not guaranteed probabilities. Face and
body fingerprints are already calculated by pretrained models for the existing approximate
people-counting feature; they are not labels for suspicious objects.

---

## 1. Isolation Forest: unusual activity in event/count data

**Purpose:** Find camera activity that differs from that camera's usual pattern. “Unusual” does not
mean unsafe or suspicious by itself.

### Data used to fit it

Build one feature row for each **camera and time window** (recommended: 15 minutes) from the event
and count tables:

- Camera: `camera_id` (and optionally camera name as a display label).
- Time: local hour, weekday (`iso_dow`), and optionally month/season.
- Counts in that window: total walk-pasts, total events, and counts of `matched`, `stranger`,
  `face_capture`, and `body_capture`.
- Optional context: whether the time is inside a configured time plan; recent counts for that same
  camera.

Example training row:

```text
camera_id=2 | hour=2 | weekday=2 | walk_pasts=14 | matched=1 | strangers=8
face_captures=3 | body_captures=2 | scheduled_time=false
```

Use historical rows that represent normal operation to fit the Isolation Forest. Exclude or
separately review known outages, test periods and bad/incomplete ingest so the model does not learn
those as normal. Identity fields such as names, person IDs and camera passwords are not needed.

### Expected output

For a new camera/time-window feature row, the model returns an **anomaly score** (and a flag based on
a chosen threshold). The portal can display:

- camera and time window;
- observed event/walk-past counts and event-kind breakdown;
- anomaly score or low/medium/high category;
- comparison with the camera's normal pattern for that hour and weekday.

Example:

> **Unusual activity — Camera 2, Tuesday 02:00–02:15**
> 14 walk-pasts; this camera usually has 2–5 at this time.
> **Anomaly:** high. Review the camera/event records.

The Isolation Forest itself scores rows; the “usual range” and plain-language reason should be
calculated from historical counts and shown as supporting context. Validate false-alert rates on
later data that was not used to fit the model.

---

## 2. Gradient-boosted-tree regressor: forecast walk-pasts

**Purpose:** Estimate how many people are likely to pass a camera in a future time window.

### Data used to fit it

Use historical count-bucket rows (or aggregate sightings into fixed windows). Each example has:

- **Target to predict:** number of walk-pasts in the next time window for a camera.
- **Camera:** `camera_id`.
- **Calendar features:** local hour, weekday (`iso_dow`), date/season and holiday/festival indicator
  if that information is available.
- **Recent activity:** walk-past counts in previous windows and the same time window on recent days.
- **Optional context:** time-plan/scheduled status and separate face/body or event-kind counts.

Example training example:

```text
camera_id=2 | hour=08:00 | weekday=1 | previous_window=6
same_hour_previous_week=21 | scheduled_time=true | target_next_hour_walk_pasts=18
```

The target must be in the future relative to the input features. Split training and evaluation by
time (train on earlier dates, test on later dates) to avoid accidentally testing on patterns the
model has already seen.

### Expected output

For each camera and requested future window, the fitted model returns a **predicted walk-past
count**. A regressor gives a point prediction; a likely range can be added by measuring prediction
errors on held-out historical periods.

Example:

> **Camera 2, next hour:** predicted 18 walk-pasts; likely range 13–24.

The output supports staffing and capacity planning. It is a forecast, not a promise; show the
prediction range and evaluate it against a simple baseline such as “same hour last week.”

---

## 3. Vision model: suspicious-object detection in images

**Purpose:** Find selected, clearly defined objects in event images so staff can review them.
The model should report visible objects, not decide whether a person has bad intent.

### Data used to train or adapt it

Use **saved image files**, not just the database's image paths. Candidate sources are full-scene
images and, where appropriate, body crops fetched from the box when an event arrives. Because the
box rotates older images out, copy approved images to access-controlled storage promptly and apply a
retention policy.

For each image, prepare a human-checked label set for the exact objects in scope. For object
detection, each labelled example needs:

- image file;
- object category (for example, a narrowly specified item approved for the use case);
- bounding box around each labelled object;
- optionally, camera and capture time for analysis and evaluation.

The current portal does **not** document an existing labelled suspicious-object image dataset.
Start by evaluating a suitable pretrained object detector on reviewed examples. Fine-tuning requires
enough representative images with verified category labels and bounding boxes; do not assume the
existing face/body fingerprints provide these labels.

### Expected output

For each analyzed image, the model returns zero or more detected objects, each with:

- object label;
- confidence score;
- bounding-box coordinates locating it in the image.

Example:

```json
{
  "detections": [
    { "label": "backpack", "confidence": 0.86, "box": [120, 45, 310, 260] }
  ]
}
```

The portal can show the image with boxes and a **“please review”** flag when a chosen category is
detected. Confidence is a model score, not proof that an object is suspicious or unauthorized.
Measure missed and incorrect detections on separate, human-labelled images before relying on the
model.

---

## Important limits

- Confirm actual row counts, history length, missing fields and image availability before training;
  this document describes the schema, not live database measurements.
- The image pipeline must save selected images before box rotation removes them.
- Define access, retention and permitted use for face images, fingerprints and event records.
- Treat anomaly scores, forecasts, object detections and identity estimates as decision support.
  Keep human review for consequential actions.
