"""The box client itself (b4h.py): login, session expiry, errors, one-request-at-a-time.

Uses a fake box web server (httpx.MockTransport), so this tests the real B4HClient code.
"""
import asyncio
import hashlib
import json

import httpx
import pytest

from b4h import B4HClient, B4HError


class FakeBoxServer:
    def __init__(self, password="right-pass"):
        self.password = password
        self.logins = 0
        self.sessions_valid = True
        self.session_lost_times = 0       # answer 512 this many times
        self.in_flight = 0
        self.max_in_flight = 0
        self.requests: list[httpx.Request] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/auth/login/challenge":
            if request.url.params.get("username") != "admin":
                return httpx.Response(200, json={"code": 7, "message": "user not exist"})
            return httpx.Response(200, json={"code": 0, "data": {"session_id": f"S{self.logins + 1}",
                                                                   "salt": "SALT", "challenge": "CH"}})
        if path == "/auth/login":
            body = json.loads(request.content)
            expected = hashlib.sha256((self.password + "SALT" + "CH").encode()).hexdigest()
            if body["password"] != expected:
                return httpx.Response(200, json={"code": 6, "message": "password error"})
            self.logins += 1
            return httpx.Response(200, json={"code": 0, "data": {"session_id": body["session_id"]}})
        if path == "/html":
            return httpx.Response(502, text="<html>Bad gateway</html>")
        if path == "/fail":
            return httpx.Response(200, json={"code": 1073741831, "message": "not_support"})
        # any normal API call
        if self.session_lost_times:
            self.session_lost_times -= 1
            return httpx.Response(200, json={"code": 512, "message": "session lost"})
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        return httpx.Response(200, json={"code": 0, "data": {"path": path, "cookie": request.headers.get("cookie")}})


def make_client(server, password="right-pass", user="admin"):
    c = B4HClient("https://box", user, password)
    c._http = httpx.AsyncClient(base_url="https://box", transport=httpx.MockTransport(server.handler))
    return c


def run(coro):
    return asyncio.run(coro)


def test_login_sends_hashed_password_never_plain():
    server = FakeBoxServer()
    c = make_client(server)
    run(c.login())
    assert c.session_id == "S1"
    login_req = [r for r in server.requests if r.url.path == "/auth/login"][0]
    assert b"right-pass" not in login_req.content
    assert login_req.headers["cookie"] == "sessionID=S1"


def test_wrong_password_raises_and_does_not_retry():
    server = FakeBoxServer()
    c = make_client(server, password="wrong")
    with pytest.raises(B4HError) as e:
        run(c.login())
    assert e.value.path == "/auth/login" and e.value.code == 6
    # only ONE login attempt: 5 wrong attempts lock the account on the box
    assert len([r for r in server.requests if r.url.path == "/auth/login"]) == 1


def test_wrong_password_on_call_tries_login_only_once():
    server = FakeBoxServer()
    c = make_client(server, password="wrong")
    with pytest.raises(B4HError):
        run(c.call("POST", "/x", {}))
    assert len([r for r in server.requests if r.url.path == "/auth/login"]) == 1


def test_unknown_user():
    server = FakeBoxServer()
    with pytest.raises(B4HError) as e:
        run(make_client(server, user="nobody").login())
    assert e.value.path == "/auth/login/challenge"


def test_first_call_logs_in_automatically_and_sends_cookie():
    server = FakeBoxServer()
    c = make_client(server)
    data = run(c.call("POST", "/device_access/device_config", {"offset": 0}))
    assert data == {"path": "/device_access/device_config", "cookie": "sessionID=S1"}
    assert server.logins == 1


def test_session_expired_relogs_in_and_retries_once():
    server = FakeBoxServer()
    c = make_client(server)
    run(c.login())
    server.session_lost_times = 1
    data = run(c.call("POST", "/x", {}))
    assert data["cookie"] == "sessionID=S2" and server.logins == 2


def test_session_expired_twice_gives_up_instead_of_looping():
    server = FakeBoxServer()
    c = make_client(server)
    run(c.login())
    server.session_lost_times = 5
    with pytest.raises(B4HError) as e:
        run(c.call("POST", "/x", {}))
    assert e.value.code == 512 and server.logins == 2


def test_box_error_code_raises():
    server = FakeBoxServer()
    with pytest.raises(B4HError) as e:
        run(make_client(server).call("POST", "/fail", {}))
    assert e.value.code == 1073741831 and e.value.message == "not_support" and e.value.path == "/fail"


def test_non_json_reply_raises_clear_error():
    server = FakeBoxServer()
    with pytest.raises(B4HError) as e:
        run(make_client(server).call("GET", "/html"))
    assert "non-JSON" in str(e.value.message) and e.value.code == 502


def test_calls_are_sent_one_at_a_time():
    """The box answers 'general' error if two queries run at once on one session."""
    server = FakeBoxServer()
    c = make_client(server)

    async def many():
        await c.login()
        await asyncio.gather(*(c.call("POST", f"/q{i}", {}) for i in range(10)))
    run(many())
    assert server.max_in_flight == 1


def test_concurrent_first_calls_do_not_crash():
    server = FakeBoxServer()
    c = make_client(server)

    async def many():
        return await asyncio.gather(*(c.call("POST", f"/q{i}", {}) for i in range(5)))
    assert len(run(many())) == 5


def test_box_unreachable_raises_transport_error():
    def down(request):
        raise httpx.ConnectError("No route to host")
    c = B4HClient("https://box", "admin", "x")
    c._http = httpx.AsyncClient(base_url="https://box", transport=httpx.MockTransport(down))
    with pytest.raises(httpx.TransportError):
        run(c.call("POST", "/x", {}))


def test_upload_retries_after_session_expired():
    server = FakeBoxServer()
    c = make_client(server)
    run(c.login())
    server.session_lost_times = 1
    data = run(c.upload("/face_manager/person", files={"person_info": (None, "{}")}))
    assert data["cookie"] == "sessionID=S2"
