# B4H Portal API (FastAPI, MVC)

```
fastapi-app/
├─ main.py                        # legacy entry point
├─ pyproject.toml                 # dependencies managed by uv
├─ .env                           # your settings (see .env.example)
├─ app/
│  ├─ main.py                     # app factory: CORS, lifespan (box login), routers
│  ├─ core/
│  │  ├─ config.py                # all settings from .env
│  │  └─ b4h.py                   # shared box client + b4h_call() (box error → HTTP 502)
│  ├─ clients/b4h_client.py       # your box client (moved here, unchanged)
│  ├─ models/                     # M: data shapes returned to the frontend
│  │  ├─ recognition.py  device.py  event.py
│  ├─ views/                      # V: HTTP endpoints (thin)
│  │  ├─ recognition_view.py  event_view.py  b4h_view.py
│  ├─ controllers/                # C: logic — call the box, page, map
│  │  ├─ recognition_controller.py  device_controller.py  event_controller.py  person_controller.py
│  └─ utils/json_extract.py       # tolerant lookups for undocumented box JSON
└─ tests/                         # `uv run pytest -q` (fake box, no device needed)
```

Flow: **view** (parse request) → **controller** (call box, map data) → **model** (response shape).

## Recognition endpoints
| Method | Path | |
|---|---|---|
| GET | `/api/recognition/records` | `start`, `end` (ISO; default today), `result=all\|matched\|stranger`, `camera_id`, `name`, `page`, `size` (≤30, default 10), `include_raw` |
| GET | `/api/recognition/records/{id}` | one record from recent list results |
| GET | `/api/recognition/image?uri=` | image proxy for face / panorama / base image |
| GET | `/api/recognition/cameras` | capture-device filter `[{id,name,online}]` |
| GET | `/api/recognition/groups` | groups `[{id,name}]` |
| GET | `/api/events/stream?major=face_basic_business` | live recognitions (SSE) |
| GET | `/api/recognition/types` | debug: box face alarm types |
| GET | `/api/recognition/raw-sample` | debug: one raw box record |

## First run
1. Run `uv sync` to install runtime and test dependencies. Copy `.env.example` to `.env` and set your box credentials.
2. Open `/docs` → `GET /api/recognition/types`: confirm the stranger minor type; set `RECOG_MINOR_STRANGER` if needed.
3. `GET /api/recognition/raw-sample`: compare with `/records`. If a field is empty, add the real key name
   first in the matching list in `controllers/recognition_controller.py → to_record()`.
