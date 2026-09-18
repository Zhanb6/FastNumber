import asyncio
import json

from app.config import get_config
from app.realtime.listener import PgListener
from app.realtime.manager import ConnectionManager
from tests.conftest import audit_actions, create_draw, register


async def test_snapshot_lifecycle(client, admin):
    r = await client.get("/api/live/current")
    snap = r.json()
    assert snap["state"] == "IDLE" and snap["draw"] is None and snap["number_pool"] is None
    assert snap["type"] == "state" and isinstance(snap["server_time"], int)
    assert snap["participants_count"] == 0 and snap["animation_duration_ms"] == 8000
    assert snap["event_name"] == "Kazakhstan Travel Forum 2026"

    numbers = [(await register(client, "Имя", "Ф"))["number"] for i in range(3)]
    d = await create_draw(admin)
    snap = (await client.get("/api/live/current")).json()
    assert snap["next_draw"] == {"id": d["id"], "title": "Розыгрыш №1", "prize": "Авиабилеты"}
    assert snap["participants_count"] == 3

    r = await admin.post(f"/api/admin/draws/{d['id']}/start")
    result = r.json()["current_result"]
    snap = (await client.get("/api/live/current")).json()
    assert snap["state"] == "COUNTDOWN"
    assert snap["draw"]["id"] == d["id"] and snap["draw"]["title"] == "Розыгрыш №1"
    assert isinstance(snap["draw"]["started_at"], int)
    assert abs(snap["server_time"] - snap["draw"]["started_at"]) < 1000
    assert snap["winner"]["number"] == result["participant"]["number"]
    assert snap["winner"]["first_name"] == result["participant"]["first_name"]
    assert snap["number_pool"] == sorted(numbers)
    assert snap["next_draw"] is None

    r = await admin.post(f"/api/admin/draws/{d['id']}/redraw")
    snap2 = (await client.get("/api/live/current")).json()
    assert snap2["state"] == "COUNTDOWN"
    assert snap2["draw"]["started_at"] >= snap["draw"]["started_at"]
    assert snap2["winner"]["number"] != snap["winner"]["number"]
    assert snap2["winner"]["number"] in snap2["number_pool"]
    assert snap["winner"]["number"] not in snap2["number_pool"]  # rejected => not eligible

    await admin.post(f"/api/admin/draws/{d['id']}/confirm")
    snap = (await client.get("/api/live/current")).json()
    assert snap["state"] == "COMPLETED"
    assert snap["winner"]["number"] == snap2["winner"]["number"]
    assert snap["winner"]["number"] in snap["number_pool"]

    r = await admin.post("/api/admin/live/idle")
    assert r.status_code == 200 and r.json()["state"] == "IDLE" and r.json()["draw"] is None
    snap = (await client.get("/api/live/current")).json()
    assert snap["state"] == "IDLE"
    assert len(await audit_actions(admin, action="LIVE_IDLE")) == 1


async def test_derived_state_by_elapsed(client, admin):
    await register(client)
    d = await create_draw(admin)
    await admin.put("/api/admin/settings", json={"animation": {"duration_ms": 1200}})
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    assert (await client.get("/api/live/current")).json()["state"] == "COUNTDOWN"
    await asyncio.sleep(1.05)
    snap = (await client.get("/api/live/current")).json()
    assert snap["state"] == "DRAWING" and snap["animation_duration_ms"] == 1200
    await asyncio.sleep(0.3)
    assert (await client.get("/api/live/current")).json()["state"] == "WINNER"


async def test_idle_keeps_pending_draw(client, admin):
    await register(client)
    await register(client)
    d = await create_draw(admin)
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    r = await admin.post("/api/admin/live/idle")
    assert r.json()["state"] == "IDLE"
    r = await admin.get(f"/api/admin/draws/{d['id']}")
    assert r.json()["status"] == "PENDING_CONFIRMATION"
    r = await admin.post(f"/api/admin/draws/{d['id']}/redraw")
    assert r.status_code == 200
    assert (await client.get("/api/live/current")).json()["state"] == "COUNTDOWN"


async def test_draw_screen_key(client):
    get_config().draw_screen_key = "s3cret"
    r = await client.get("/api/live/current")
    assert r.status_code == 403 and r.json()["error"]["code"] == "DRAW_KEY_REQUIRED"
    r = await client.get("/api/live/current", params={"key": "wrong"})
    assert r.status_code == 403
    r = await client.get("/api/live/current", params={"key": "s3cret"})
    assert r.status_code == 200
    # admin session also grants access
    r = await client.post("/api/admin/auth/login", json={"login": "admin", "password": "secret123"})
    assert r.status_code == 200
    r = await client.get("/api/live/current")
    assert r.status_code == 200
    # public endpoints never require the key
    r = await client.get("/api/config/public")
    assert r.status_code == 200


class FakeWs:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.closed = False

    async def send_text(self, data: str) -> None:
        if self.closed:
            raise RuntimeError("closed")
        self.messages.append(json.loads(data))


async def wait_for(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("timeout waiting for realtime event")
        await asyncio.sleep(0.05)


async def test_notify_reaches_websocket_clients(client, admin):
    manager = ConnectionManager()
    listener = PgListener(manager, get_config().asyncpg_dsn)
    await listener.start()
    ws, dead = FakeWs(), FakeWs()
    dead.closed = True
    manager.add(ws)
    manager.add(dead)
    try:
        await wait_for(lambda: listener._conn is not None and not listener._conn.is_closed())
        # initial state broadcast after (re)connect
        await wait_for(lambda: any(m["type"] == "state" for m in ws.messages))
        assert manager.count == 1  # dead connection dropped after send failure
        ws.messages.clear()

        await register(client)
        await wait_for(lambda: any(m["type"] == "participants_count" for m in ws.messages))
        counts = [m for m in ws.messages if m["type"] == "participants_count"]
        assert counts[-1]["count"] == 1 and isinstance(counts[-1]["server_time"], int)

        d = await create_draw(admin)
        await wait_for(lambda: any(m["type"] == "state" and m["next_draw"] for m in ws.messages))
        ws.messages.clear()

        await admin.post(f"/api/admin/draws/{d['id']}/start")
        await wait_for(lambda: any(m.get("state") == "COUNTDOWN" for m in ws.messages))
        state = [m for m in ws.messages if m["type"] == "state"][-1]
        assert state["draw"]["id"] == d["id"] and state["winner"]["number"] == 1000
        ws.messages.clear()

        await admin.post(f"/api/admin/draws/{d['id']}/confirm")
        await wait_for(lambda: any(m.get("state") == "COMPLETED" for m in ws.messages))
        ws.messages.clear()

        await admin.post("/api/admin/live/idle")
        await wait_for(lambda: any(m.get("state") == "IDLE" for m in ws.messages))

        # participants_count is debounced: a burst yields few messages
        ws.messages.clear()
        for _ in range(5):
            await register(client, "Имя", "Ф")
        await wait_for(lambda: any(m["type"] == "participants_count" for m in ws.messages))
        await asyncio.sleep(0.3)
        counts = [m for m in ws.messages if m["type"] == "participants_count"]
        assert len(counts) == 1
    finally:
        await listener.stop()
