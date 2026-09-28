"""
Minimal async client for the MegCube B4H box WebAPI.

Login flow:
  1. GET  /auth/login/challenge?username=...  -> session_id, salt, challenge
  2. POST /auth/login  {session_id, username, password=sha256(pwd+salt+challenge)}
  3. Every request sends the header  Cookie: sessionID=<session_id>
The box drops idle sessions after ~30 s (code 512); call() then logs in again and retries once.
The box can't run two API queries at once on a session (it answers code 1073741825 "general"),
so call() sends them one at a time.
"""
import asyncio
import hashlib
import json
from typing import Any

import httpx

SESSION_LOST = 512


class B4HError(RuntimeError):
    def __init__(self, code: Any, message: Any, path: str):
        super().__init__(f"{path}: code={code} message={message}")
        self.code, self.message, self.path = code, message, path


class B4HClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.username = username
        self.password = password
        self.session_id: str | None = None
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), verify=False, timeout=15)
        self._login_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()

    async def login(self) -> None:
        async with self._login_lock:
            body = (await self._http.get("/auth/login/challenge", params={"username": self.username})).json()
            if body.get("code") != 0:
                raise B4HError(body.get("code"), body.get("message"), "/auth/login/challenge")
            d = body["data"]
            pwd_hash = hashlib.sha256((self.password + d["salt"] + d["challenge"]).encode()).hexdigest()
            body = (await self._http.post(
                "/auth/login",
                json={"session_id": d["session_id"], "username": self.username, "password": pwd_hash},
                headers={"Cookie": f"sessionID={d['session_id']}"},
            )).json()
            if body.get("code") != 0:
                # careful: 5 wrong passwords in a row locks the account on the box
                raise B4HError(body.get("code"), body.get("message"), "/auth/login")
            self.session_id = (body.get("data") or {}).get("session_id", d["session_id"])

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "Cookie": f"sessionID={self.session_id}"}

    async def call(self, method: str, path: str, body: Any = None, _retry: bool = True) -> Any:
        """Call a WebAPI endpoint. Returns `data` on code 0, raises B4HError otherwise."""
        if not self.session_id:
            await self.login()
        async with self._call_lock:
            r = await self._http.request(method, path, headers=self._headers(),
                                         content=json.dumps(body) if body is not None else None)
        try:
            payload = r.json()
        except ValueError:
            raise B4HError(r.status_code, f"non-JSON reply (HTTP {r.status_code})", path)
        if payload.get("code") == SESSION_LOST and _retry:
            await self.login()
            return await self.call(method, path, body, _retry=False)
        if payload.get("code") != 0:
            raise B4HError(payload.get("code"), payload.get("message"), path)
        return payload.get("data")

    async def upload(
        self,
        path: str,
        files: dict[str, tuple],
        data: dict[str, str] | None = None,
        method: str = "POST",
        _retry: bool = True,
    ) -> Any:
        """Send a multipart request to an endpoint that accepts uploaded files."""
        if not self.session_id:
            await self.login()
        async with self._call_lock:
            r = await self._http.request(
                method,
                path,
                headers={"Cookie": f"sessionID={self.session_id}"},
                data=data,
                files=files,
            )
        try:
            payload = r.json()
        except ValueError:
            raise B4HError(r.status_code, f"non-JSON reply (HTTP {r.status_code})", path)
        if payload.get("code") == SESSION_LOST and _retry:
            await self.login()
            return await self.upload(path, files, data, method, _retry=False)
        if payload.get("code") != 0:
            raise B4HError(payload.get("code"), payload.get("message"), path)
        return payload.get("data")

    async def get_bytes(self, path: str, params: dict | None = None) -> tuple[bytes, str]:
        """Binary download, e.g. a record image."""
        if not self.session_id:
            await self.login()
        r = await self._http.get(path, params=params, headers=self._headers())
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "application/octet-stream")

    async def close(self) -> None:
        await self._http.aclose()
