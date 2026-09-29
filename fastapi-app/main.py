"""App entry point: box connection lifecycle, error handling, and router wiring only."""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from b4h import B4HError
from core import box, log
from routers import capture, common, devices, personnel, preview, recognition, timeplan


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


@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(recognition.router)
app.include_router(capture.router)
app.include_router(common.router)
app.include_router(preview.router)
app.include_router(personnel.router)
app.include_router(devices.router)
app.include_router(timeplan.router)