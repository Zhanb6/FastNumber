from sqlalchemy import text

from app.db import engine
from tests.conftest import audit_actions, register


async def test_settings_get_defaults(admin):
    r = await admin.get("/api/admin/settings")
    assert r.status_code == 200
    assert r.json() == {
        "event_name": "Kazakhstan Travel Forum 2026",
        "event_slug": "ktf-2026",
        "registration_open": True,
        "allow_previous_winners": False,
        "start_number": 1000,
        "start_number_locked": False,
        "max_number": 2000,
        "on_max_reached": "continue",
        "name_mode": "full",
        "timezone": "Asia/Almaty",
        "fields": {
            "phone": {"enabled": False, "required": False},
            "email": {"enabled": False, "required": False},
            "company": {"enabled": False, "required": False},
        },
        "animation": {"duration_ms": 8000, "sound": False},
    }


async def test_start_number_change_resets_counter_then_locks(client, admin):
    r = await admin.put("/api/admin/settings", json={"start_number": 5000, "event_name": "KTF"})
    assert r.status_code == 200
    assert r.json()["start_number"] == 5000 and r.json()["start_number_locked"] is False
    changes = (await audit_actions(admin, action="SETTINGS_CHANGED"))[0]["metadata"]["changes"]
    assert changes == {
        "start_number": {"old": 1000, "new": 5000},
        "event_name": {"old": "Kazakhstan Travel Forum 2026", "new": "KTF"},
    }
    p = await register(client)
    assert p["number"] == 5000
    r = await admin.get("/api/admin/settings")
    assert r.json()["start_number_locked"] is True
    r = await admin.put("/api/admin/settings", json={"start_number": 7000})
    assert r.status_code == 409 and r.json()["error"]["code"] == "START_NUMBER_LOCKED"
    # unchanged value is not a change
    r = await admin.put("/api/admin/settings", json={"start_number": 5000, "max_number": 9000})
    assert r.status_code == 200 and r.json()["max_number"] == 9000
    assert (await register(client))["number"] == 5001
    async with engine.connect() as conn:
        n = (await conn.execute(text("SELECT next_value FROM number_counter"))).scalar_one()
    assert n == 5002
    # start_number stays locked even after soft delete (numbers are never reused)
    await admin.delete(f"/api/admin/participants/{p['id']}")
    r = await admin.get("/api/admin/settings")
    assert r.json()["start_number_locked"] is True


async def test_settings_validation(admin):
    cases = [
        {"on_max_reached": "explode"},
        {"timezone": "Mars/Olympus"},
        {"event_name": ""},
        {"animation": {"duration_ms": 10}},
        {"max_number": 0},
        {"event_slug": "bad slug!"},
    ]
    for body in cases:
        r = await admin.put("/api/admin/settings", json=body)
        assert r.status_code == 422, body
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"
        assert r.json()["error"]["details"]["fields"]
    r = await admin.put("/api/admin/settings", json={"unknown_key": 1})
    assert r.status_code == 200
    assert len(await audit_actions(admin, action="SETTINGS_CHANGED")) == 0


async def test_public_config_reflects_settings(client, admin):
    await admin.put(
        "/api/admin/settings",
        json={"event_name": "Форум", "fields": {"company": {"enabled": True}}},
    )
    r = await client.get("/api/config/public")
    assert r.json() == {
        "event_name": "Форум",
        "registration_open": True,
        "name_mode": "full",
        "fields": {
            "phone": {"enabled": False, "required": False},
            "email": {"enabled": False, "required": False},
            "company": {"enabled": True, "required": False},
        },
    }
