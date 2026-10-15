# Recommended Staffing and Guard Coverage

## Model

Use **LightGBM regression** to predict the number of people detected by each
camera in the next 15 minutes.

Train one model using historical camera counts and time-based features.

## Data shape

One row represents one camera and one 15-minute time interval.

Example:

| camera_id | hour | weekday | previous_count | count_1_hour | count_last_week | target_count |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 17 | 4 | 12 | 45 | 38 | 16 |

`target_count` is the number of people detected in the next 15-minute
interval.

## Data input

Use data that already exists in the system:

- `camera_id`
- hour and weekday from the event timestamp
- previous 15-minute sighting count
- previous 1-hour sighting count
- same camera, hour, and weekday count from the previous week
- recent event count
- face and body sighting counts
- matched-person and stranger-event counts
- camera counting status

The main sources are `count_buckets`, `sightings`, and `events`.

## Model output

For each camera and future 15-minute interval:

```json
{
  "camera_id": 3,
  "predicted_people": 16,
  "lower_estimate": 11,
  "upper_estimate": 23
}
```

The lower and upper estimates show the likely prediction range.

## Recommendation

Convert the prediction into staffing using a configured capacity:

```text
recommended_guards =
ceil(predicted_people / people_one_guard_can_monitor)
```

Example:

```text
predicted_people = 16
one guard capacity = 8
recommended_guards = ceil(16 / 8) = 2
```

The system recommends how many guards are needed for each camera and time
period. The capacity value must be configured by the site manager because the
current data does not record how many guards were actually needed.
