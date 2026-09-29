"""App entry point: box connection lifecycle, error handling, access check and router wiring only."""
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from b4h import B4HError
from core import box, check_access, log
from routers import capture, common, dashboard, devices, personnel, preview, recognition, timeplan


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await box.login()
        log.info("B4H login OK")
    except B4HError as e:
        # Wrong username/password: no more attempts until restart (5 wrong ones lock the account).
        log.error("B4H login refused: %s. Fix B4H_USER / B4H_PASS in .env and restart.", e.message)
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
    if isinstance(exc, httpx.TimeoutException) and not isinstance(exc, httpx.ConnectTimeout):
        # Connected, but the box took too long to answer (e.g. a very long date range).
        return JSONResponse(status_code=504, content={
            "detail": "The box took too long to answer. Try a shorter date range, or try again."})
    return JSONResponse(status_code=503, content={"detail": f"B4H box unreachable ({type(exc).__name__})"})


@app.get("/")
async def root():
    return {"message": "Hello World"}


# Every /api route needs the API key (when API_KEY is set in .env); see core.check_access.
for r in (recognition, capture, common, preview, personnel, devices, timeplan, dashboard):
    app.include_router(r.router, dependencies=[Depends(check_access)])
