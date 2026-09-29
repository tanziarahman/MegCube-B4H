"""
Minimal async client for the MegCube B4H box WebAPI.

Login flow:
  1. GET  /auth/login/challenge?username=...  -> session_id, salt, challenge
  2. POST /auth/login  {session_id, username, password=sha256(pwd+salt+challenge)}
  3. Every request sends the header  Cookie: sessionID=<session_id>
The box drops idle sessions after ~30 s (code 512); call() then logs in again and retries once.
The box can't run two API queries at once on a session (it answers code 1073741825 "general"),
so call() sends them one at a time.

Login safety: 5 wrong passwords in a row lock the account on the box. So only ONE login runs at a
time (requests arriving together share it), and once the box refuses the username/password, no
further login is attempted until the backend is restarted (after fixing .env).
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
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 15):
        self.username = username
        self.password = password
        self.session_id: str | None = None
        self.login_refused: B4HError | None = None   # set when the box rejects the credentials
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), verify=False, timeout=timeout)
        self._login_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()

    # ---------- login ----------

    def _check_not_refused(self) -> None:
        if self.login_refused:
            e = self.login_refused
            raise B4HError(e.code, f"{e.message}. Login to the box is paused to avoid locking the account: "
                                   "fix B4H_USER / B4H_PASS in .env and restart the backend", e.path)

    async def _do_login(self) -> None:
        """One login attempt. Call only while holding _login_lock."""
        self._check_not_refused()
        body = (await self._http.get("/auth/login/challenge", params={"username": self.username})).json()
        if body.get("code") != 0:
            self.login_refused = B4HError(body.get("code"), body.get("message"), "/auth/login/challenge")
            self._check_not_refused()
        d = body["data"]
        pwd_hash = hashlib.sha256((self.password + d["salt"] + d["challenge"]).encode()).hexdigest()
        body = (await self._http.post(
            "/auth/login",
            json={"session_id": d["session_id"], "username": self.username, "password": pwd_hash},
            headers={"Cookie": f"sessionID={d['session_id']}"},
        )).json()
        if body.get("code") != 0:
            # Wrong username/password (or account locked): never retry automatically.
            self.login_refused = B4HError(body.get("code"), body.get("message"), "/auth/login")
            self._check_not_refused()
        self.session_id = (body.get("data") or {}).get("session_id", d["session_id"])

    async def login(self) -> None:
        """Log in now (a fresh session)."""
        async with self._login_lock:
            await self._do_login()

    async def ensure_session(self) -> None:
        """Log in if there's no session yet. Requests arriving together share one login."""
        if self.session_id:
            return
        async with self._login_lock:
            if not self.session_id:
                await self._do_login()

    async def relogin(self, stale_session: str | None) -> None:
        """The box said `stale_session` has expired. Log in again, unless another request already did."""
        async with self._login_lock:
            if self.session_id == stale_session:
                await self._do_login()

    # ---------- requests ----------

    def _headers(self, session: str | None) -> dict[str, str]:
        return {"Content-Type": "application/json", "Cookie": f"sessionID={session}"}

    @staticmethod
    def _payload(r: httpx.Response, path: str) -> dict:
        try:
            payload = r.json()
        except ValueError:
            raise B4HError(r.status_code, f"non-JSON reply (HTTP {r.status_code})", path)
        if not isinstance(payload, dict):
            raise B4HError(r.status_code, "unexpected reply", path)
        return payload

    async def call(self, method: str, path: str, body: Any = None, _retry: bool = True) -> Any:
        """Call a WebAPI endpoint. Returns `data` on code 0, raises B4HError otherwise."""
        await self.ensure_session()
        async with self._call_lock:
            session = self.session_id
            r = await self._http.request(method, path, headers=self._headers(session),
                                         content=json.dumps(body) if body is not None else None)
        payload = self._payload(r, path)
        if payload.get("code") == SESSION_LOST and _retry:
            await self.relogin(session)
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
        await self.ensure_session()
        async with self._call_lock:
            session = self.session_id
            r = await self._http.request(method, path, headers={"Cookie": f"sessionID={session}"},
                                         data=data, files=files)
        payload = self._payload(r, path)
        if payload.get("code") == SESSION_LOST and _retry:
            await self.relogin(session)
            return await self.upload(path, files, data, method, _retry=False)
        if payload.get("code") != 0:
            raise B4HError(payload.get("code"), payload.get("message"), path)
        return payload.get("data")

    async def get_bytes(self, path: str, params: dict | None = None) -> tuple[bytes, str]:
        """Binary download, e.g. a record image."""
        await self.ensure_session()
        r = await self._http.get(path, params=params, headers=self._headers(self.session_id))
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "application/octet-stream")

    async def close(self) -> None:
        await self._http.aclose()