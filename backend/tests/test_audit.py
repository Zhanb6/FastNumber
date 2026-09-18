import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import engine
from tests.conftest import audit_actions, create_draw, register


async def test_audit_log_is_append_only():
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO audit_log (action, entity_type) VALUES ('TEST', 'test')")
        )
    for stmt in ("UPDATE audit_log SET action = 'X'", "DELETE FROM audit_log"):
        with pytest.raises(DBAPIError) as exc:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        assert "append-only" in str(exc.value)
    async with engine.connect() as conn:
        n = (await conn.execute(text("SELECT count(*) FROM audit_log"))).scalar_one()
    assert n == 1


async def test_audit_list_filters_and_actions(client, admin):
    p = await register(client)
    d = await create_draw(admin)
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    await admin.post(f"/api/admin/draws/{d['id']}/confirm")
    await admin.put("/api/admin/settings", json={"event_name": "Test"})

    r = await admin.get("/api/admin/audit")
    body = r.json()
    assert body["total"] >= 6 and body["page"] == 1 and body["page_size"] == 50
    ids = [e["id"] for e in body["items"]]
    assert ids == sorted(ids, reverse=True)
    entry = body["items"][0]
    assert set(entry) == {
        "id", "action", "entity_type", "entity_id", "participant_id", "draw_id",
        "admin_login", "ip", "metadata", "created_at",
    }  # fmt: skip

    r = await admin.get("/api/admin/audit/actions")
    assert set(r.json()["items"]) >= {
        "ADMIN_LOGIN", "PARTICIPANT_REGISTERED", "DRAW_CREATED", "DRAW_STARTED",
        "WINNER_SELECTED", "WINNER_CONFIRMED", "SETTINGS_CHANGED",
    }  # fmt: skip
    by_draw = await audit_actions(admin, draw_id=d["id"])
    assert {e["action"] for e in by_draw} == {
        "DRAW_CREATED", "DRAW_STARTED", "WINNER_SELECTED", "WINNER_CONFIRMED",
    }  # fmt: skip
    by_p = await audit_actions(admin, participant_id=p["id"])
    assert {e["action"] for e in by_p} == {
        "PARTICIPANT_REGISTERED", "WINNER_SELECTED", "WINNER_CONFIRMED",
    }  # fmt: skip
    r = await admin.get("/api/admin/audit", params={"page_size": 2, "page": 2})
    assert len(r.json()["items"]) == 2
