import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from b4h import B4HClient, B4HError

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("b4h")

box = B4HClient(
    os.getenv("B4H_BASE_URL", "https://192.168.90.200"),
    os.getenv("B4H_USER", "admin"),
    os.getenv("B4H_PASS", ""),
)

# Recognitions are stored on the box as alarms of this major type.
RECOG_MAJOR = os.getenv("RECOG_MAJOR", "face_basic_business")
BOX_MAX_PAGE_SIZE = 30  # the box refuses more than 30 records per request
# Only minor types the box lists in GET /device_alarm/alarm_cap. An unknown one crashes the box's web server.
RecognitionMinor = Literal["face_comparison_successful", "stranger"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await box.login()
        log.info("B4H login OK")
    except Exception as e:
        # Box offline/rebooting: start anyway, the first request logs in again.
        log.warning("B4H login at startup failed (%r); will retry on first request", e)
    yield
    await box.close()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(B4HError)
async def box_error(request: Request, exc: B4HError):
    return JSONResponse(status_code=502, content={"detail": f"Box error on {exc.path}: {exc.message} (code {exc.code})"})


@app.exception_handler(httpx.TransportError)
async def box_unreachable(request: Request, exc: httpx.TransportError):
    return JSONResponse(status_code=503, content={"detail": f"B4H box unreachable ({type(exc).__name__})"})


def to_ms(value: str) -> int:
    """'YYYY-MM-DD HH:mm:ss' in this PC's local time -> epoch milliseconds."""
    try:
        return int(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    except ValueError:
        raise HTTPException(422, f"Bad time '{value}', expected YYYY-MM-DD HH:mm:ss")


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/api/recognition")
async def recognition(
    start: str,
    end: str,
    minor: RecognitionMinor = "face_comparison_successful",
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=BOX_MAX_PAGE_SIZE),
):
    """One page of recognition records, as the box returns them (the frontend maps the fields)."""
    return await box.call("POST", "/device_alarm/alarm_history", {
        "offset": (page - 1) * size,
        "size": size,
        "query_condition": {
            "start_time": str(to_ms(start)),
            "end_time": str(to_ms(end)),
            "alarm_type": [{"major_type": RECOG_MAJOR, "minor_type": [minor]}],
        },
    })


@app.get("/api/devices")
async def devices():
    """Cameras configured on the box, used for the device filter (id + name only: the raw config holds RTSP passwords)."""
    data = await box.call("POST", "/device_access/device_config", {"offset": 0, "size": 100})
    return [{"device_id": d.get("device_id"), "device_name": d.get("device_name")} for d in data or []]


@app.get("/api/image")
async def image(uri: str):
    """Proxy a record image from the box (the browser can't send the box session cookie)."""
    for path, params in (("/web/" + uri.lstrip("./"), None), ("/device_storage/get_image", {"image_uri": uri})):
        try:
            content, media_type = await box.get_bytes(path, params)
            if media_type == "application/octet-stream":  # the box doesn't label its JPEGs
                media_type = mimetypes.guess_type(uri)[0] or media_type
            return Response(content, media_type=media_type, headers={"Cache-Control": "max-age=86400"})
        except httpx.HTTPStatusError:
            continue
    raise HTTPException(404, "Image not found on the box")