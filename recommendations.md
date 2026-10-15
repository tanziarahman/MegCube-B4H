# Regression-Based Recommendations for the B4H Portal

## Goal

Use historical camera and portal data to predict **how much activity or operational work to expect**,
then turn those predictions into practical recommendations about **when to add coverage, review
alarms, or inspect a camera**.

The regression model predicts numbers. A separate, visible recommendation step compares those
predictions with site rules or thresholds. A high predicted count means “expect more activity,” not
“a threat is likely.”

## Data available

When the portal database is enabled, it stores normalized box events and derived counts:

| Data | Useful fields |
|---|---|
| **Events** | `occurred_at`, `received_at`, `camera_id`, `kind` (`matched`, `stranger`, `face_capture`, `body_capture`), `match_score`, `liveness_score`, and `sighting_id`. |
| **Sightings (walk-pasts)** | `camera_id`, `first_seen_at`, `last_seen_at`, `event_count`, `recognition_result`, and optional best match score. |
| **15-minute count buckets** | `local_date`, `local_hour`, `iso_dow`, `sightings`, `events`, and counts by event kind. |
| **Alarm incidents** | Camera, occurrence time, rule, severity, `event_count`, delay and status. These allow prediction of alarm-review workload, but statuses are not reliable labels for whether an event was truly dangerous. |
| **Box context** | Camera names and IDs, current online/stream state, assigned task, time zone and regular/festival time plans. Time plans can provide schedule context; current camera state is not a historical status series. |

The image paths in event rows are not durable images: the box may rotate the image files out. Images
are not needed for the recommendations below. Camera passwords, person names and face-library IDs
should not be used as regression features.

## Model: gradient-boosted-tree regression

Fit a regression model to predict numerical outcomes for a future time window, such as the next hour.
Use **one model per target** (or a multi-output implementation if supported and evaluated), because
walk-pasts, stranger detections, alarm workload and match quality are different quantities.

For each training example, use earlier information as the **input** and the measured later result as
the **target**. For example, features up to 09:00 predict counts from 09:00 to 10:00. Test on later
dates than the training data.

### Inputs

Create a row for each camera and prediction window with:

- **Camera:** `camera_id` (name is for display, not necessary for fitting).
- **Calendar:** local hour, weekday (`iso_dow`), month/season and whether the time falls within a
  configured schedule, if that schedule is available.
- **Recent history:** previous-window and recent same-hour counts, such as the previous hour and
  corresponding hours on earlier days.
- **Observed activity:** recent walk-pasts and counts for matched, stranger, face-capture and
  body-capture events.
- **Optional operating signals:** recent alarm count, average match score, low-score counts and
  event receipt delay, calculated only from records available before the prediction window.

Example input:

```text
camera=Entrance | next_window=09:00–10:00 | weekday=Monday | scheduled=true
walk-pasts_previous_hour=11 | same-hour_recent_average=16
strangers_previous_hour=2 | alarms_previous_hour=1
```

Do not include information from the period being predicted; that would leak the answer into the
inputs.

### Regression targets and expected model outputs

Train separate targets where the recommendation needs them:

| Target (the value to learn) | Model output for each camera/time window |
|---|---|
| Number of walk-pasts | Predicted people-counting workload. |
| Number of stranger events | Predicted volume of unmatched-face detections; not a prediction of threat. |
| Number of incidents | Predicted alarm-review workload under the rules that were active historically. |
| Average match score or low-score event count | Predicted recognition-quality indicator, where enough historical scores exist. |

A standard regressor gives a point estimate. Add a **likely range** from errors on held-out dates
(or use quantile regression) so the portal can show uncertainty, not just one number.

Example output:

```text
Entrance, Monday 09:00–10:00
Predicted walk-pasts: 20 (likely range 14–27)
Predicted stranger events: 3 (likely range 1–6)
Predicted incidents: 2 (likely range 0–4)
```

## Recommendations produced from those outputs

### 1. Time-period coverage recommendation

Rank upcoming hours by predicted walk-pasts or total events. Recommend that a site manager consider
extra staffing or monitoring in the consistently busiest periods.

> **Consider extra coverage:** Entrance, weekdays 08:00–10:00.  
> Predicted activity: 20–25 walk-pasts per hour, compared with 6–10 in quieter periods.

The model estimates activity; the site manager decides what staffing level is appropriate.

### 2. Alarm-review staffing recommendation

Rank periods by predicted incident volume. Recommend when to schedule enough people to review the
expected queue, or when to check that notification coverage is available.

> **Plan for a larger review queue:** Loading Bay, 18:00–20:00.  
> Predicted: 4 incidents per hour (likely range 2–7).

This predicts workload under the **existing alarm rules**. It does not establish that alerts are
correct, and it cannot fairly compare periods where rules or cameras changed without accounting for
those changes.

### 3. Alarm schedule review

Compare predicted activity by hour and the configured alarm-rule schedule. Highlight periods with
repeated detections outside the configured window for a human to review whether the rule schedule
still matches site operations.

> **Review this rule’s hours:** repeated detections occur around 06:00–07:00, before its current
> 08:00 start time.

This is a prompt to review the schedule—not an automatic recommendation to enable alarms. Historical
incident counts alone are biased by the rules that were already active.

### 4. Camera inspection prompt

Track predicted and observed match-score summaries by camera. If a camera’s measured match scores
remain below its own usual level, suggest an image-quality inspection (for example, lighting, focus
or angle).

> **Inspect Entrance camera:** recent average match score is below its usual range.

Treat this as a maintenance prompt only: changes in people, lighting or event conditions can also
change scores. Camera online/stream state is currently live data, not a complete historical series;
save periodic status snapshots if the model should learn from past outages.

## Important limits

- Recommendations depend on having enough consistent history for each camera and time period.
  Measure database coverage and missing-data rates before fitting.
- A regression forecast predicts **observed counts**, not the effect of changing a schedule,
  staffing level or camera position. Do not present it as proof that a proposed change will improve
  safety or reduce incidents.
- To learn whether a recommendation actually helped, record the proposed action, whether it was
  adopted, and the later measured outcome. Evaluate those outcomes over time.
- Event and incident data can be incomplete during box/database outages. Exclude or flag affected
  periods rather than teaching the model that missing records mean zero activity.
- Show the predicted value, range, historical comparison and reason for each recommendation. Keep
  consequential decisions with a human reviewer.
