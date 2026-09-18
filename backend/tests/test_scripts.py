from sqlalchemy import text

from app.db import async_session, engine
from scripts import draw_cli
from scripts import reset as reset_script
from scripts import seed as seed_script
from tests.conftest import audit_actions, create_draw, register


async def test_seed_is_idempotent(client, admin):
    async with async_session() as session:
        created = await seed_script.seed(session)
    assert created == {"participants": 50, "draws": 1}
    r = await admin.get("/api/admin/participants", params={"page_size": 100})
    assert r.json()["total"] == 50
    assert [i["number"] for i in r.json()["items"]][:3] == [1000, 1001, 1002]
    r = await admin.get("/api/admin/draws")
    assert [d["title"] for d in r.json()["items"]] == ["Демо-розыгрыш"]
    assert r.json()["items"][0]["prize"] == "Демо-приз"
    async with async_session() as session:
        created = await seed_script.seed(session)
    assert created == {"participants": 0, "draws": 0}
    assert len(await audit_actions(admin, action="SEED")) == 1
    assert (await register(client))["number"] == 1050


async def test_draw_cli_flow(client, admin, capsys):
    await register(client, "А", "Первый")
    await register(client, "Б", "Второй")
    await create_draw(admin, "Розыгрыш №1")
    assert await draw_cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "DRAFT" in out and "Розыгрыш №1" in out

    assert await draw_cli.main(["start", "1"]) == 0  # by position
    assert "pending confirmation" in capsys.readouterr().out
    assert await draw_cli.main(["start", "Розыгрыш"]) == 1  # already started
    assert "INVALID_STATUS" in capsys.readouterr().err
    assert await draw_cli.main(["redraw", "Розыгрыш №1", "--reason", "absent"]) == 0
    capsys.readouterr()
    r = await admin.get("/api/admin/draws")
    d = r.json()["items"][0]
    assert d["status"] == "PENDING_CONFIRMATION" and d["current_result"] is not None
    assert await draw_cli.main(["confirm", d["id"]]) == 0
    assert "confirmed" in capsys.readouterr().out
    assert await draw_cli.main(["idle"]) == 0
    assert (await client.get("/api/live/current")).json()["state"] == "IDLE"

    r = await admin.get(f"/api/admin/draws/{d['id']}")
    assert r.json()["status"] == "COMPLETED" and len(r.json()["results"]) == 2
    entries = await audit_actions(admin, draw_id=d["id"])
    cli_actions = {e["action"] for e in entries if e["admin_login"] == "cli"}
    assert cli_actions == {"DRAW_STARTED", "WINNER_SELECTED", "DRAW_REDRAW", "WINNER_CONFIRMED"}
    assert all(e["ip"] is None for e in entries if e["admin_login"] == "cli")


async def test_reset_requires_confirm_and_wipes(client, admin, capsys):
    assert await reset_script.main([]) == 2
    await register(client)
    d = await create_draw(admin)
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    assert await reset_script.main(["--confirm"]) == 0
    assert "deleted 1 results, 1 draws, 1 participants" in capsys.readouterr().out
    async with engine.connect() as conn:
        for table in ("participants", "draws", "draw_results"):
            assert (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0
        nxt = (await conn.execute(text("SELECT next_value FROM number_counter"))).scalar_one()
        assert nxt == 1000
    snap = (await client.get("/api/live/current")).json()
    assert snap["state"] == "IDLE" and snap["participants_count"] == 0
    entries = await audit_actions(admin, action="RESET")
    assert entries[0]["metadata"]["deleted"] == {"draw_results": 1, "draws": 1, "participants": 1}
    assert entries[0]["metadata"]["counter_reset_to"] == 1000
    assert (await register(client))["number"] == 1000
