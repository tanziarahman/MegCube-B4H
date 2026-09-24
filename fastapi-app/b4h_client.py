"""
Minimal async client for the MegCube B4H WebAPI (AIOTAP / MegConnect protocol).

Flow (from book_en -> base_interface/webapi/login.html):
  1. GET  /auth/login/challenge?username=...  -> session_id, salt, challenge
  2. POST /auth/login  {session_id, username, password=sha256(pwd+salt+challenge)}
  3. Every request: header  Cookie: sessionID=<session_id>
  4. PUT  /login_manager/keep_alive at least every 30 s or the session is dropped
     (dropped session => {"code": 512, "message": "session not found"})
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import ssl
import struct
import time
from typing import Any, Awaitable, Callable

import httpx
import websockets

log = logging.getLogger("b4h")

SESSION_ERRORS = {512}  # error_session_is_not_find


class B4HError(RuntimeError):
    def __init__(self, code: int, message: str, path: str):
        super().__init__(f"{path} -> code={code} message={message}")
        self.code, self.message, self.path = code, message, path


class B4HClient:
    def __init__(self, base_url: str, username: str, password: str, verify_tls: bool = False):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.session_id: str | None = None
        self.sign_str: str | None = None
        self._http = httpx.AsyncClient(base_url=self.base_url, verify=verify_tls, timeout=15)
        self._login_lock = asyncio.Lock()
        self._keepalive_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ auth
    async def login(self) -> None:
        async with self._login_lock:
            r = await self._http.get("/auth/login/challenge", params={"username": self.username})
            body = r.json()
            if body.get("code") != 0:
                raise B4HError(body.get("code"), body.get("message"), "/auth/login/challenge")
            d = body["data"]
            session_id, salt, challenge = d["session_id"], d["salt"], d["challenge"]

            pwd_hash = hashlib.sha256((self.password + salt + challenge).encode()).hexdigest()
            r = await self._http.post(
                "/auth/login",
                json={"session_id": session_id, "username": self.username, "password": pwd_hash},
                headers={"Cookie": f"sessionID={session_id}"},
            )
            body = r.json()
            if body.get("code") != 0:
                # careful: 5 wrong attempts locks the account (Login Setting -> login limit)
                raise B4HError(body.get("code"), body.get("message"), "/auth/login")

            self.session_id = body.get("data", {}).get("session_id", session_id)
            # 16-char sign string, used for websocket auth & encrypted fields
            self.sign_str = hashlib.md5(
                (self.session_id + self.password + self.username).encode()
            ).hexdigest().upper()[:16]
            log.info("B4H login OK, session=%s…", self.session_id[:8])

        if not self._keepalive_task or self._keepalive_task.done():
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _keepalive_loop(self) -> None:
        while True:
            await asyncio.sleep(20)  # device drops idle sessions after 30 s
            try:
                r = await self._http.put(
                    "/login_manager/keep_alive",
                    headers={"Cookie": f"sessionID={self.session_id}",
                             "Content-Type": "application/x-www-form-urlencoded"},
                )
                if r.json().get("code") in SESSION_ERRORS:
                    log.warning("keep_alive: session lost, re-logging in")
                    await self.login()
            except Exception as e:  # network blip -> try re-login next round
                log.warning("keep_alive failed: %s", e)
                try:
                    await self.login()
                except Exception:
                    pass

    async def close(self) -> None:
        if self._keepalive_task:
            self._keepalive_task.cancel()
        try:
            if self.session_id:
                await self._http.get("/auth/logout", headers=self._headers())
        finally:
            await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "Cookie": f"sessionID={self.session_id}"}

    # --------------------------------------------------------------- generic
    async def call(self, method: str, path: str, body: Any = None, params: dict | None = None,
                   _retry: bool = True) -> Any:
        """Call any WebAPI endpoint. Returns `data` on code==0, raises B4HError otherwise."""
        if not self.session_id:
            await self.login()
        r = await self._http.request(method, path, headers=self._headers(), params=params,
                                     content=json.dumps(body) if body is not None else None)
        try:
            payload = r.json()
        except ValueError:
            # Box answered with a non-JSON page, e.g. 404 = this path doesn't exist on this firmware
            raise B4HError(r.status_code, f"HTTP {r.status_code}, non-JSON reply: {r.text[:200]!r}", path)
        code = payload.get("code")
        if code in SESSION_ERRORS and _retry:
            await self.login()
            return await self.call(method, path, body, params, _retry=False)
        if code != 0:
            raise B4HError(code, payload.get("message"), path)
        return payload.get("data")

    async def call_multipart(self, path: str, fields: dict[str, str],
                             files: dict[str, tuple[str, bytes, str]], _retry: bool = True) -> Any:
        """multipart/form-data calls, e.g. POST /face_manager/person (person_info + face1 photo)."""
        if not self.session_id:
            await self.login()
        # no Content-Type here: httpx sets multipart boundary itself
        r = await self._http.post(path, data=fields, files=files,
                                  headers={"Cookie": f"sessionID={self.session_id}"})
        try:
            payload = r.json()
        except ValueError:
            raise B4HError(r.status_code, f"HTTP {r.status_code}, non-JSON reply: {r.text[:200]!r}", path)
        code = payload.get("code")
        if code in SESSION_ERRORS and _retry:
            await self.login()
            return await self.call_multipart(path, fields, files, _retry=False)
        if code != 0:
            raise B4HError(code, payload.get("message"), path)
        return payload.get("data")

    async def get_bytes(self, path: str, params: dict | None = None) -> tuple[bytes, str]:
        """Binary downloads, e.g. /device_storage/get_image?image_uri=... or /web/<uri>."""
        if not self.session_id:
            await self.login()
        r = await self._http.get(path, params=params, headers=self._headers())
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "application/octet-stream")

    # ----------------------------------------------------- alarm websocket
    async def run_alarm_stream(self, on_alarm: Callable[[dict, list[bytes]], Awaitable[None]],
                               alarm_types: list[dict] | None = None) -> None:
        """
        Real-time pull alternative to HTTP push:
          POST /device_alarm/subscribe_stream -> stream_id, handle
          WS   /device_alarm/stream?stream_id=..&session_id=..  (AIOTAP-Access-Sign header)
          PUT  /device_alarm/subscribe_alarm_type {handle, alarm_type: []}   ([] = all types)
        Order 1-2-3 is mandatory. Reconnects forever.
        """
        while True:
            try:
                try:
                    sub = await self.call("POST", "/device_alarm/subscribe_stream", {})
                except B4HError as e:
                    if e.code != 6:  # 6 = already subscribed on this session; re-login gives a fresh one
                        raise
                    await self.login()
                    sub = await self.call("POST", "/device_alarm/subscribe_stream", {})
                stream_id, handle = sub["stream_id"], sub["handle"]

                ws_base = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
                stream_path = f"/device_alarm/stream?stream_id={stream_id}&session_id={self.session_id}"
                sign = hashlib.md5(
                    f"{stream_path}+aiotkey${int(time.time()) // 2000:08d}{self.sign_str}".encode()
                ).hexdigest().upper()
                ssl_ctx = None
                if ws_base.startswith("wss://"):
                    ssl_ctx = ssl.create_default_context()
                    if not self.verify_tls:
                        ssl_ctx.check_hostname = False
                        ssl_ctx.verify_mode = ssl.CERT_NONE

                async with websockets.connect(
                    ws_base + stream_path,
                    additional_headers={"AIOTAP-Access-Sign": sign,
                                        "Cookie": f"sessionID={self.session_id}"},
                    ssl=ssl_ctx, max_size=None, ping_interval=20,
                ) as ws:
                    await self.call("PUT", "/device_alarm/subscribe_alarm_type",
                                    {"handle": handle, "alarm_type": alarm_types or []})
                    log.info("alarm websocket subscribed (handle=%s)", handle)
                    async for frame in ws:
                        if isinstance(frame, bytes):
                            info, blobs = parse_alarm_frame(frame)
                            await on_alarm(info, blobs)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("alarm stream error: %s — reconnecting in 5 s", e)
                await asyncio.sleep(5)


def parse_alarm_frame(buf: bytes) -> tuple[dict, list[bytes]]:
    """
    Binary layout (all ints are 4-byte big-endian / network order):
      total_len | info_len | info(json) | bin_num | {type | size | data} * bin_num
    type: 1 video, 2 audio, 3 picture. Picture index i == image_data.value "i" in the JSON.
    """
    off = 0
    (total_len, info_len) = struct.unpack_from(">II", buf, off); off += 8
    info = json.loads(buf[off:off + info_len].decode("utf-8", "replace")); off += info_len
    (n,) = struct.unpack_from(">I", buf, off); off += 4
    blobs: list[bytes] = []
    for _ in range(n):
        _type, size = struct.unpack_from(">II", buf, off); off += 8
        blobs.append(buf[off:off + size]); off += size
    return info, blobs