import hashlib
import os
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

BOX_URL = os.getenv("B4H_URL", "https://192.168.90.200")
BOX_USER = os.getenv("B4H_USER", "admin")
BOX_PASS = os.getenv("B4H_PASS", "Shohan@98")  # set this before running: B4H_PASS=yourpassword

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

box = httpx.AsyncClient(base_url=BOX_URL, verify=False, timeout=15)  # box uses a self-signed certificate
session_id: str | None = None


# ---------- talking to the box ----------

async def login():
    """Same login the box web page does: get a challenge, send sha256(password + salt + challenge)."""
    global session_id
    r = (await box.get("/auth/login/challenge", params={"username": BOX_USER})).json()
    d = r["data"]
    pwd = hashlib.sha256((BOX_PASS + d["salt"] + d["challenge"]).encode()).hexdigest()
    r = (await box.post("/auth/login", json={"session_id": d["session_id"], "username": BOX_USER, "password": pwd},
                        headers={"Cookie": f"sessionID={d['session_id']}"})).json()
    if r.get("code") != 0:
        raise HTTPException(401, f"Box login failed: {r.get('message')}")
    session_id = r.get("data", {}).get("session_id", d["session_id"])


async def call_box(method: str, path: str, body: dict | None = None):
    """Call a box API. Logs in when needed and retries once if the session expired (code 512)."""
    for attempt in range(2):
        if session_id is None:
            await login()
        r = await box.request(method, path, json=body, headers={"Cookie": f"sessionID={session_id}"})
        data = r.json()
        if data.get("code") == 512 and attempt == 0:  # session expired -> log in again
            await login()
            continue
        if data.get("code") != 0:
            raise HTTPException(502, f"Box error {data.get('code')}: {data.get('message')}")
        return data.get("data")


# ---------- endpoints for the frontend ----------

@app.get("/api/recognition")
async def recognition_records(
    start: str | None = None,   # e.g. 2026-09-27 00:00:00   (default: today)
    end: str | None = None,     # e.g. 2026-09-27 23:59:59
    page: int = 1,
    size: int = 10,             # box allows max 30
    minor: str = "face_comparison_successful",
):
    """Recognition Record list — same call the box page makes (device_alarm/alarm_history)."""
    today = datetime.now().strftime("%Y-%m-%d")
    start_ms = int(datetime.strptime(start or f"{today} 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    end_ms = int(datetime.strptime(end or f"{today} 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

    body = {
        "offset": (page - 1) * size,
        "size": min(size, 30),
        "query_condition": {
            "start_time": str(start_ms),
            "end_time": str(end_ms),
            "alarm_type": [{"major_type": "face_basic_business", "minor_type": [minor]}],
        },
    }
    return await call_box("POST", "/device_alarm/alarm_history", body)


@app.get("/api/devices")
async def devices():
    """Capture devices (cameras) — same call the box page makes (device_access/device_config)."""
    return await call_box("POST", "/device_access/device_config", {"offset": 0, "size": 100})


@app.get("/api/image")
async def image(uri: str):
    """Face / panorama / base images from the records. The box needs the login cookie, so we fetch them here."""
    if session_id is None:
        await login()
    cookie = {"Cookie": f"sessionID={session_id}"}
    r = await box.get("/web/" + uri.lstrip("./"), headers=cookie)
    if r.status_code != 200:
        r = await box.get("/device_storage/get_image", params={"image_uri": uri}, headers=cookie)
    if r.status_code != 200:
        raise HTTPException(404, "Image not found")
    return Response(r.content, media_type=r.headers.get("content-type", "image/jpeg"))