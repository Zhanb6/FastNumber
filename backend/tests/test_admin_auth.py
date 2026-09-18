from tests.conftest import ADMIN_PASSWORD, audit_actions


async def test_login_sets_cookie_and_me(client):
    r = await client.post(
        "/api/admin/auth/login", json={"login": "admin", "password": ADMIN_PASSWORD}
    )
    assert r.status_code == 200 and r.json() == {"login": "admin"}
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("admin_session=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "Secure" not in cookie  # PUBLIC_BASE_URL is http
    r = await client.get("/api/admin/auth/me")
    assert r.status_code == 200 and r.json()["login"] == "admin"
    entries = await audit_actions(client, action="ADMIN_LOGIN")
    assert len(entries) == 1 and entries[0]["admin_login"] == "admin"

    r = await client.post("/api/admin/auth/logout")
    assert r.status_code == 204
    r = await client.get("/api/admin/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_protected_routes_require_cookie(client):
    for method, url in [
        ("GET", "/api/admin/stats"),
        ("GET", "/api/admin/participants"),
        ("POST", "/api/admin/draws"),
        ("GET", "/api/admin/settings"),
        ("GET", "/api/admin/export/participants"),
        ("POST", "/api/admin/live/idle"),
    ]:
        r = await client.request(method, url)
        assert r.status_code == 401, url
        assert r.json()["error"]["code"] == "UNAUTHORIZED"
    r = await client.get("/api/admin/stats", cookies={"admin_session": "garbage"})
    assert r.status_code == 401


async def test_wrong_password_and_bruteforce_block(client):
    for i in range(5):
        r = await client.post("/api/admin/auth/login", json={"login": "admin", "password": "nope"})
        assert r.status_code == 401, i
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r = await client.post(
        "/api/admin/auth/login", json={"login": "admin", "password": ADMIN_PASSWORD}
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    # other IP not affected
    r = await client.post(
        "/api/admin/auth/login",
        json={"login": "admin", "password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": "198.51.100.9"},
    )
    assert r.status_code == 200
    failed = await audit_actions(client, action="ADMIN_LOGIN_FAILED")
    assert len(failed) == 5


async def test_csrf_origin_check(client, admin):
    r = await admin.post(
        "/api/admin/draws",
        json={"title": "t", "prize": "p"},
        headers={"Origin": "http://evil.example"},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    # same host as Host header
    r = await admin.post(
        "/api/admin/draws",
        json={"title": "t", "prize": "p"},
        headers={"Origin": "http://testserver"},
    )
    assert r.status_code == 201
    # PUBLIC_BASE_URL origin
    r = await admin.post(
        "/api/admin/draws",
        json={"title": "t2", "prize": "p"},
        headers={"Origin": "http://localhost"},
    )
    assert r.status_code == 201
    # GET is never blocked
    r = await admin.get("/api/admin/draws", headers={"Origin": "http://evil.example"})
    assert r.status_code == 200
    # login is also protected
    r = await client.post(
        "/api/admin/auth/login",
        json={"login": "admin", "password": ADMIN_PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


async def test_error_format_for_unknown_route_and_validation(client, admin):
    r = await client.get("/api/nope")
    assert r.status_code == 404 and r.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not Found"}
    }
    r = await admin.get("/api/admin/participants", params={"page_size": 999})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "page_size" in r.json()["error"]["details"]["fields"]
    r = await admin.get("/api/admin/participants", params={"status": "WRONG"})
    assert r.status_code == 422 and "status" in r.json()["error"]["details"]["fields"]
    r = await admin.get("/api/admin/draws/not-a-uuid")
    assert r.status_code == 422


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "db": True}
