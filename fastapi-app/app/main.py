"""App factory: wires config, lifespan (box login + optional websocket) and the view routers."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers import event_controller
from app.core import config
from app.core.b4h import b4h
from app.views import b4h_view, event_view, recognition_view

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.MEDIA_DIR.mkdir(exist_ok=True)
    await b4h.login()
    ws_task = asyncio.create_task(b4h.run_alarm_stream(event_controller.on_ws_alarm)) if config.B4H_USE_WS else None
    yield
    if ws_task:
        ws_task.cancel()
    await b4h.close()


def create_app() -> FastAPI:
    app = FastAPI(title="B4H Portal API", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS,
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(recognition_view.router)
    app.include_router(event_view.router)
    app.include_router(b4h_view.router)
    return app


app = create_app()
