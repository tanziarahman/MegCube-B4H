"""The one shared B4H client, plus a helper that turns box errors into HTTP 502 responses."""
from typing import Any

from fastapi import HTTPException

from app.clients.b4h_client import B4HClient, B4HError
from app.core import config

b4h = B4HClient(config.B4H_BASE_URL, config.B4H_USER, config.B4H_PASS, verify_tls=False)


async def b4h_call(method: str, path: str, body: Any = None, params: dict | None = None) -> Any:
    try:
        return await b4h.call(method, path, body, params)
    except B4HError as e:
        raise HTTPException(status_code=502, detail={"b4h_code": e.code, "message": e.message, "path": e.path})
