# B4H Portal: Data and Useful ML Models

## Executive summary

The portal already has useful camera-event data for understanding **when and where people are
detected**, **how often**, and **how reliably the cameras recognize them**. It also has event
snapshots available from the B4H box and pretrained models that create face and clothing
fingerprints for the existing people-counting estimate.

The most practical first steps are:

1. Find activity that is unusual for a particular camera, time and day.
2. Forecast how busy each camera is likely to be.
3. Spot cameras whose streams or recognition quality are getting worse.
4. Later, prioritize alarms using the outcomes recorded by staff.
5. Later still, add image analysis after images are retained safely and examples are labelled.

These models can identify **unusual patterns**. They cannot determine that a person is dangerous,
guilty or acting with bad intent. A human should review consequential alerts.

> **What this analysis is based on:** the six-page `camera.pdf` proposal, the repository documentation,
> and the FastAPI schemas and processing code. This is a review of data shapes and system behaviour,
> not a query of the live PostgreSQL database. Actual row counts, history length, missing-data rates
> and image quality must be measured before estimating model accuracy.

---

## 1. What data is in the system?

There are two related sources:

- **The B4H box** creates camera records, captures, face-library matches, images and camera status.
- **The portal** reads those box records and, when its database is configured, saves selected records
  and creates walk-pasts, alarm history and summary counts.

The box is the original source of camera events. The portal database is a useful working copy and
contains portal-created information too.

### 1.1 Box record: the raw shape

The box returns a JSON record. A simplified example, based on the documented response format:

```json
{
  "additional": {
    "alarm_id": 12345,
    "alarm_minor": "face_comparison_successful",
    "device_id": 1
  },
  "global_info": { "time_ms": "1727600000000" },
  "faces": [{
    "track_id": 5610081,
    "image_data": { "value": "./record_CHN0/.../face.jpg" },
    "age": 31,
    "gender": 2,
    "wear_glasses": 2,
    "recognition_info": [{
      "person_uuid": "17",
      "person_name": "Example person",
      "face_score": 96,
      "group_info": [{ "group_name": "Staff" }]
    }]
  }],
  "pedestrians": [{
    "track_id": 5610090,
    "image_data": { "value": "./record_CHN0/.../body.jpg" }
  }],
  "full_images": [{
    "image_data": { "value": "./record_CHN0/.../full.jpg" }
  }]
}
```

In plain English: **which record**, **which kind**, **which camera**, **when**, **which track**, optional
recognition details and attributes, and paths to a face crop, body crop or full-scene image.
Fields can be missing, box firmware may vary, and some field meanings are not fully confirmed.

The portal currently keeps these four event kinds:

| Stored kind | Meaning |
|---|---|
| `matched` | A face was matched to a person in the box's face library. |
| `stranger` | A face was not matched to someone in that library. |
| `face_capture` | The box captured a face; it need not be recognized. |
| `body_capture` | The box captured a body; the face may not be visible. |

The box also has record types for structures such as vehicles, non-motor vehicles and plates.
Although those types appear in a capture query, the portal's event normalizer currently discards
them. They are **not a dependable vehicle or plate dataset in the portal today**.

### 1.2 What one portal event row looks like

The `events` table turns a box record into a simpler database row. Its main fields are:

| Field | What it means |
|---|---|
| `occurred_at` | Time the box says the event happened, stored as a timestamp. |
| `received_at` | Time the portal received it; the difference helps measure delays. |
| `camera_id`, `box_id` | Portal camera and box identifiers. The camera also has the box's `device_id` and name. |
| `kind` | Matched, stranger, face capture or body capture. |
| `face_track_id`, `body_track_id` | Box tracking numbers used to connect records from one pass. |
| `person_uuid`, `person_name`, `group_ids`, `group_names` | Best library match and its group, for a successful match. These can be empty. |
| `match_score` | Match similarity, normalized to 0–100; not a guaranteed probability. |
| `liveness_score` | Box liveness signal, normalized to 0–100 when supplied; may be missing. |
| `attributes` | Box-detected face/body details in JSON; many are raw numeric codes. |
| `face_image_path`, `body_image_path`, `panorama_path` | Paths to images on the box, not image bytes stored in this row. |

An illustrative database-shaped row:

```text
kind=matched | camera=Entrance | time=09:14 | track=5610081
person=17 | group=Staff | match_score=96 | liveness_score=95
face_image_path=./record_CHN0/.../face.jpg
```

This row has structured, table-like values that can be filtered, counted and compared over time.
The image itself must still be fetched from the box.

### 1.3 Walk-pasts and counts

One person can create multiple box records during a pass. The portal's `sightings` table groups
related records into a **walk-past**. It can hold:

- the camera and first/last seen times;
- face and body track IDs, event count and detected recognition result;
- the recognized person ID/name, when available;
- links to the best face/body images;
- optional face and body fingerprint vectors.

Face and body tracks can be paired into a single walk-past. Track numbers are not global identity:
they can be reused, and the pairing logic is scoped by camera and time.

`count_buckets` stores activity by camera and 15-minute interval: walk-pasts, face/body sightings,
event counts and per-kind recognition/capture counts. Dashboard daily statistics include distinct
encounters and recognized people. These tables make trends and forecasts much easier than repeatedly
asking the box for old records.

The portal already estimates the number of different people by comparing fingerprints. It returns an
estimate and a range because two people may look alike, lighting changes, and clothing changes.
Body/clothing comparisons are intended for the same day, not reliable identification across days.

### 1.4 Alarms and staff feedback

The portal database contains alarm rules and incidents. A rule can describe:

- which cameras and event kinds to watch;
- whether it applies to anyone, strangers, known people or selected people/groups;
- active days and times;
- minimum match/liveness scores, severity, quiet period and recipients.

An incident records the triggering camera/person or stranger, event time and processing time,
delivery delay, number of related events, snapshot path, and status. Staff can mark incidents open,
acknowledged, resolved or false alarm and add a note. Notifications record email delivery attempts
and errors.

This is useful operational history, but **alarm status is not automatically a verified truth label**.
For example, “resolved” does not necessarily mean the event was confirmed, and older incidents may
not have a staff review at all.

### 1.5 Images and live video

Images available from a box record can include:

| Image | Typical use |
|---|---|
| Face crop | Inspect a captured face; create a face fingerprint. |
| Body crop | Inspect clothing/body; create a body fingerprint. |
| Full-scene/panorama | See the wider camera view around the event. |
| Face-library photo | Reference photo used by the box for matching. |

**Important:** database rows store image paths, not durable image copies. The backend fetches image
bytes from the box on request. The box may rotate old images out. Live video is converted from RTSP
for viewing, but the portal does not document a continuous video archive.

The existing image-processing worker downloads available pictures for new walk-pasts and stores
pretrained-model fingerprints. This supports the current approximate people grouping; it does not
mean the portal has a labelled image-training set.

### 1.6 Camera, schedule and face-library data

The box also provides information useful as context:

- **Camera configuration:** box camera ID, name, protocol/type and RTSP configuration. Passwords are
  secret and should never be used as model features or exposed to the browser.
- **Camera state:** online/offline and channel stream state. Some raw state codes are not fully
  explained.
- **Analysis tasks:** task names assigned to cameras, for example face recognition.
- **Time settings:** box clock/time zone when supported.
- **Time plans:** weekly or festival schedules.
- **Face library:** person ID, name, optional code/birthday/remarks, groups and reference-photo path.

People, camera status and schedules are primarily read from the box; they are not all maintained as
complete historical snapshots in the database.

### 1.7 What is not available or should not be assumed

| Do not assume… | Why |
|---|---|
| That the portal has video recordings for every event | It serves live video, but does not document an archived video store. |
| That old image paths still work | The box can rotate images out. |
| That every person in a panorama has an event row | The normalizer uses the first face/body entry from a record. |
| That a stranger's nearest library candidate is their identity | The box can include the closest face even when it did not match; the portal avoids treating it as the stranger's identity. |
| That scores are probabilities or verified facts | Match/liveness are box scores and may be missing or firmware-dependent. |
| That age, gender, clothing or other box attributes are ground truth | They are estimates/codes, and body attribute codes are not fully documented. |
| That visits can be traced between arbitrary cameras | There is no confirmed camera map, zone layout, entry/exit direction or badge-swipe data in the documented schema. |
| That alarm outcomes are labelled examples | Staff statuses/notes exist, but their meaning and completeness need a review process. |
| That vehicle/plate records are available for training | They are not retained as the portal's four normalized event kinds. |

---

## 2. What ML models can provide genuinely useful insights?

“Training” means learning patterns from historical examples. A model does not become useful just
because it is sophisticated: it needs enough representative data, dependable labels for supervised
tasks, and a way to check whether its output is right.

### Model 1 — Unusual activity for a camera and time

**Recommended first model.**

**Question it answers:** “Is the number or mix of detections unusual for this camera at this time?”

**Data used:** 15-minute walk-past/event counts by camera; weekday and time; event kind; optional
known/stranger breakdown; schedules; recent history.

**Approach:** First create a simple seasonal baseline for each camera and time-of-week, with robust
ranges. If enough history exists, compare it with an Isolation Forest or another anomaly model.
Compare only like with like (for example, a Monday 09:00 period with other Mondays at 09:00).

**Example output:**

> **Unusual activity — Loading Bay camera, Tuesday 02:00**  
> Observed: 14 walk-pasts. Usual range: 2–5.  
> Stranger events were also above this camera's usual level.  
> **Anomaly score:** 0.91 (high). Unusual compared with history; not proof of a threat.

**Training/evaluation output:** a saved baseline/model and, for each camera/time window, an expected
range and anomaly score. Verify it on later weeks not used to fit it; report false-alert rates.

**Why it is useful:** it gives context beyond a fixed rule, while using data the portal already stores.
It can help staff notice a sudden change without claiming to know its cause.

### Model 2 — Footfall forecast

**Question it answers:** “How busy is this camera likely to be soon?”

**Data used:** historical walk-pasts/count buckets, camera, time of day, weekday, season and
optionally schedule context.

**Approach:** Start with a seasonal forecast or a gradient-boosted-tree regressor. A deep neural
network is not the first choice unless there is a large amount of history and it clearly beats a
simple baseline.

**Example output:**

> **Entrance camera, next hour:** expected 12 walk-pasts; likely range 8–17.  
> **Expected busy period:** 16:00–17:00.

**Training/evaluation output:** a fitted forecasting model and future count predictions with
prediction intervals. Measure forecast error on future days; compare against “same hour last week.”

**Why it is useful:** staffing and capacity planning, and understanding whether observed traffic is
above or below the expected level.

### Model 3 — Camera and recognition-quality drift

**Question it answers:** “Has this camera's useful output changed over time?”

**Data used:** camera online/stream state when available; event volume; usable/pending/unusable
fingerprint counts; match-score and liveness-score distributions; alarm ingest delay.

**Approach:** Use rolling statistics and change-point detection. Treat online status, stream state,
and recognition-score changes as separate signals rather than assuming one explains another.

**Example output:**

> **Camera 2 — quality change detected**  
> Median match score fell from 88 to 61 over 7 days; event volume is similar.  
> **Suggested check:** review focus, lighting, camera angle or recent configuration changes.

**Training/evaluation output:** per-camera trend estimates and change alerts with supporting
measurements. It might point to a camera to inspect; it cannot diagnose the physical cause.

**Why it is useful:** finding degrading image quality or a stream problem before staff depend on
recognition results.

### Model 4 — Alarm review-priority score

**Good later model, after collecting reliable review labels.**

**Question it answers:** “Which alarms may deserve a person's attention first?”

**Data used:** event kind, camera, time/schedule, match/liveness scores, repeated events during a
quiet period, delay, rule and **consistent human review outcome**.

**Approach:** Begin with a calibrated logistic-regression or gradient-boosted-tree classifier.
Only train a “false-alarm likelihood” model if there are enough reviewed examples of both confirmed
and false alarms. Otherwise show a transparent priority score based on the configured rules.

**Example output:**

> **Review priority: high**  
> Reason: outside the selected schedule; low liveness score; repeated event.  
> **Estimated review category:** needs review (not an automatic decision).

**Training/evaluation output:** a classifier artifact and a probability/priority category for new
alarms, plus a short explanation. Measure precision/recall on a later, human-reviewed set. Do not
automatically suppress alarms based on an unvalidated score.

### Model 5 — Image analysis of retained snapshots

**Possible later model; first solve image retention and labelling.**

**Question it answers:** “What visible objects or scene conditions are present in a saved image?”

**Data used:** locally retained, access-controlled face/body/full-scene snapshots; camera/time; and
human-verified labels for a specific, narrowly defined task.

**Approach:** Evaluate a small pretrained object detector or image classifier first. Fine-tune only
when a suitable labelled dataset exists and the evaluation shows a clear improvement.

**Example output:**

```json
{
  "camera": "Entrance",
  "time": "02:14",
  "detections": [
    { "label": "person", "confidence": 0.94, "box": [120, 40, 310, 420] },
    { "label": "bag", "confidence": 0.78, "box": [280, 300, 390, 410] }
  ],
  "review_required": true
}
```

This is an example output shape, not a result from the current system. A detector can describe
visible objects; it cannot establish intent or whether an object is unauthorized without reliable
context and human review.

**Training/evaluation output:** a fine-tuned model file (if fine-tuning is justified) and per-image
labels, confidence scores and object locations. Track missed detections and false detections on
held-out, human-labelled images.

**Before building it:** copy images before box retention removes them; define the purpose and labels;
set retention/access rules; check image quality and class balance. Do not assume CLIP/zero-shot scores
are verified evidence.

### Model 6 — Better stranger/walk-past grouping

**Useful refinement, not verified identity.**

**Question it answers:** “Which walk-pasts may show the same unrecognized person?”

**Data used:** the existing SFace face fingerprints and YouTu ReID body/clothing fingerprints,
camera/time overlap and carefully reviewed same/different-person pairs.

**Approach:** The portal already has pretrained fingerprint models and similarity-based grouping.
The practical work is to evaluate and calibrate thresholds on reviewed examples; training a new
deep identity model should wait until there are enough consented, labelled examples and a clear
privacy/legal basis.

**Example output:**

> **Estimated distinct strangers:** about 7 (likely range 6–10).  
> 69 walk-pasts had usable fingerprints; 1 had no usable image.

**Training/evaluation output:** at most, an improved matching threshold/model and similarity scores
for candidate pairs, with an uncertainty range. The current estimate is approximate. Similar clothing
can merge different people; lighting or appearance changes can split the same person.

---

## 3. Proposed outputs for the portal

A useful **AI Insights** view can combine outputs without hiding how they were produced:

| Insight | Show to staff |
|---|---|
| Unusual activity | Camera/time, observed count, usual range, anomaly score and the signals that contributed. |
| Expected activity | Next-period count forecast and a likely range. |
| Camera quality | A trend or change alert with its measured evidence and a suggested physical check. |
| Alarm review priority | Priority category, reasons and link to the original incident; never an automated verdict. |
| Image description | Detected visible objects/regions and confidence, labelled as a model result and awaiting review. |
| Stranger count | Estimated count/range and how many walk-pasts had usable, pending or unusable fingerprints. |

Example combined daily summary:

> **Today at Entrance:** 146 walk-pasts, slightly above the usual Tuesday range of 100–130.  
> The 02:00–03:00 period was unusual (14 vs. usual 2–5).  
> Camera image-quality signals have been stable this week.  
> **Review:** 2 alarms remain open. These findings describe patterns; they do not establish intent.

---

## 4. Recommended order of work

1. **Measure data readiness:** event counts by camera/day/kind, history length, ingest gaps, missing
   scores, usable-image percentage and actual retention behaviour.
2. **Build the activity baseline:** provide observed counts, usual ranges and explainable anomaly
   signals before introducing a complex model.
3. **Add forecasting:** compare against simple same-weekday baselines and show a range, not just one
   number.
4. **Add camera-quality trends:** surface signal drops as maintenance prompts.
5. **Improve alarm prioritization only after review labels exist:** make the review process consistent
   and preserve who reviewed an alarm and why.
6. **Add image analysis only after durable image storage, human labels and privacy controls are in
   place.**

For each model, record its version, training period, data fields, evaluation results and known
limitations. Keep a time-based test set that is not used for training. Compare each model with a
simple baseline before deciding it is good enough to use.

---

## 5. Privacy and safe use

Face images, face fingerprints, personnel identifiers and visit patterns are sensitive. Restrict
access, use only data needed for the stated purpose, set retention limits, and check applicable
consent and legal requirements before training or storing additional images.

Do not train or use a model to infer criminality, dangerousness, emotion or intent from a person's
face, identity, group, clothing or presence. Do not treat a stranger estimate, box attribute,
similarity score or anomaly score as proof. Keep a person responsible for reviewing alerts and making
decisions.

---

## References in this repository

- [Project overview](docs/project-overview.md) — sources and flows of portal data.
- [Box API reference](docs/box-api.md) — documented box records, images and field caveats.
- [Backend API reference](docs/backend-api.md) — response shapes exposed to the website.
- [System design](docs/system-design.md) — database tables and how the background workers process data.
- [Dashboard performance plan](docs/dashboard-performance-plan.md) — event fields and derived dashboard statistics.
- [Backend README](fastapi-app/README.md) — configuration and existing fingerprint models.
