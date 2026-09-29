"""Read-only checks against the REAL running backend + box. Changes nothing on the box.

1. Start the backend:   uv run fastapi dev main.py --port 8001
2. In another terminal:  uv run python tests/live_check.py            (or add a URL: ... live_check.py http://localhost:8001)

Not collected by pytest (the file name doesn't start with test_).
"""
import sys
from datetime import datetime, timedelta

import os

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))  # fastapi-app/.env
HEADERS = {"X-API-Key": os.getenv("API_KEY", "")}   # same key as the backend's .env
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001").rstrip("/")
today = datetime.now().strftime("%Y-%m-%d")
week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
RANGE = {"start": f"{week_ago} 00:00:00", "end": f"{today} 23:59:59"}
results = []


def check(name, method, path, expect, params=None, stream=False, test=None):
    try:
        with httpx.Client(timeout=30, headers=HEADERS) as c:
            if stream:
                with c.stream(method, BASE + path, params=params) as r:
                    body = next(r.iter_bytes(), b"") if r.status_code == 200 else r.read()
                    status, text = r.status_code, body[:300]
            else:
                r = c.request(method, BASE + path, params=params)
                status, text = r.status_code, r.text
                body = r
        ok = status in (expect if isinstance(expect, tuple) else (expect,))
        note = ""
        if ok and test:
            note = test(body) or ""
            ok = not note
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name:55} HTTP {status}  {note or ('' if ok else str(text)[:150])}")
        return body if ok else None
    except httpx.HTTPError as e:
        results.append(False)
        print(f"FAIL  {name:55} {type(e).__name__}: {e}")


def no_password(r):
    return "RTSP password visible in response!" if ("rtsp://" in r.text and ":****@" not in r.text and "@" in r.text) else None


print(f"Backend: {BASE}   Date range: {RANGE['start']} .. {RANGE['end']}\n")

# --- normal use ---
check("Recognition: matched faces", "GET", "/api/recognition", 200, RANGE)
check("Recognition: strangers", "GET", "/api/recognition", 200, {**RANGE, "minor": "stranger"})
check("Recognition: max page size (30)", "GET", "/api/recognition", 200, {**RANGE, "size": 30})
check("Recognition: page far beyond the end -> empty, not error", "GET", "/api/recognition", 200, {**RANGE, "page": 9999})
check("Recognition: date range with no records", "GET", "/api/recognition", 200,
      {"start": "2000-01-01 00:00:00", "end": "2000-01-01 23:59:59"})
check("People (whole face library)", "GET", "/api/people", 200)
check("Capture: all", "GET", "/api/capture", 200, RANGE)
check("Capture: face only", "GET", "/api/capture", 200, {**RANGE, "target_type": "face"})
check("Capture: body only", "GET", "/api/capture", 200, {**RANGE, "target_type": "body"})
check("Devices (Recognition page camera names)", "GET", "/api/devices", 200, test=no_password)
check("Devices detail", "GET", "/api/devices/detail", 200, test=no_password)
cams = check("Preview camera list", "GET", "/api/preview/cameras", 200, test=no_password)
check("Personnel groups", "GET", "/api/personnel/groups", 200)
people = check("Personnel list", "GET", "/api/personnel", 200, {"size": 5})

# --- images: first face of the library ---
if people is not None:
    first = next((p for p in people.json().get("person_list", []) if p.get("face_image1")), None)
    if first:
        check("Face-library image loads", "GET", "/api/image", 200, {"uri": first["face_image1"]},
              test=lambda r: None if r.headers.get("content-type", "").startswith("image/") else "not an image")

# --- live video: first online camera (reads one chunk, then disconnects) ---
if cams is not None:
    online = [c for c in cams.json() if c.get("online")]
    if online:
        cam = online[0]
        link = dict(p.split("=") for p in (cam.get("stream_token") or "").split("&") if "=" in p)
        check(f"Live video, camera {cam['id']} ({cam['name']})", "GET",
              f"/api/preview/{cam['id']}/stream", 200, {"width": 320, "fps": 2, **link}, stream=True,
              test=lambda b: None if b"\xff\xd8" in b or b"--frame" in b else "no JPEG data")
    check("Live video, camera that doesn't exist -> 404", "GET", "/api/preview/9999/stream", 404, stream=True)

# --- bad input must be refused by the backend, never reach the box ---
check("Bad date format -> 422", "GET", "/api/recognition", 422, {"start": "2026-09-28", "end": "x"})
check("Unknown minor type -> 422 (would crash the box)", "GET", "/api/recognition", 422, {**RANGE, "minor": "fire"})
check("Page size 31 -> 422", "GET", "/api/recognition", 422, {**RANGE, "size": 31})
check("Image path outside box records -> 400", "GET", "/api/image", 400, {"uri": "../../etc/passwd"})
check("Image that doesn't exist -> 404", "GET", "/api/image", 404, {"uri": "./record_0/does_not_exist.jpg"})
check("Start after end -> 422", "GET", "/api/recognition", 422,
      {"start": f"{today} 23:00:00", "end": f"{today} 01:00:00"})

# --- access check (only when API_KEY is set in .env) ---
if HEADERS["X-API-Key"]:
    saved = dict(HEADERS)
    HEADERS["X-API-Key"] = "wrong-key"
    check("Wrong API key -> 401", "GET", "/api/people", 401)
    HEADERS.clear()
    check("No API key -> 401", "GET", "/api/people", 401)
    check("Live video without a signed link -> 401", "GET", "/api/preview/1/stream", 401, stream=True)
    HEADERS.update(saved)
else:
    print("NOTE  API_KEY is not set in .env: the API is open (access checks skipped)")

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)