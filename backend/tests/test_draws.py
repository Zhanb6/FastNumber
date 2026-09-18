import asyncio
import hashlib

from sqlalchemy import text

from app.db import engine
from tests.conftest import audit_actions, create_draw, register


async def test_no_eligible_participants(admin):
    d = await create_draw(admin)
    r = await admin.post(f"/api/admin/draws/{d['id']}/start")
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_ELIGIBLE_PARTICIPANTS"
    r = await admin.get(f"/api/admin/draws/{d['id']}")
    assert r.json()["status"] == "DRAFT" and r.json()["results"] == []


async def test_only_eligible_participants_win(client, admin):
    ok = await register(client, "Победитель", "Единственный")
    dq = await register(client, "Дисквалифицированный", "Участник")
    deleted = await register(client, "Удалённый", "Участник")
    await admin.post(f"/api/admin/participants/{dq['id']}/disqualify", json={"reason": "тест"})
    await admin.delete(f"/api/admin/participants/{deleted['id']}")

    d = await create_draw(admin)
    r = await admin.get(f"/api/admin/draws/{d['id']}")
    assert r.json()["eligible_count"] == 1
    for _ in range(5):
        r = await admin.post(f"/api/admin/draws/{d['id']}/start")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "PENDING_CONFIRMATION"
        assert body["current_result"]["participant"]["id"] == ok["id"]
        assert body["current_result"]["status"] == "SELECTED"
        assert body["current_result"]["eligible_count"] == 1
        assert body["started_at"] is not None
        # cannot start twice
        r = await admin.post(f"/api/admin/draws/{d['id']}/start")
        assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_STATUS"
        assert r.json()["error"]["details"]["status"] == "PENDING_CONFIRMATION"
        break


async def test_draw_started_audit_hash(client, admin):
    numbers = [(await register(client, "Имя", "Ф"))["number"] for i in range(5)]
    d = await create_draw(admin)
    r = await admin.post(f"/api/admin/draws/{d['id']}/start")
    assert r.status_code == 200
    expected = hashlib.sha256(",".join(str(n) for n in sorted(numbers)).encode()).hexdigest()
    assert r.json()["current_result"]["eligible_hash"] == expected
    started = await audit_actions(admin, action="DRAW_STARTED", draw_id=d["id"])
    assert len(started) == 1
    assert started[0]["metadata"] == {
        "eligible_count": 5,
        "eligible_hash": expected,
        "exclude_previous_winners": True,
    }
    assert started[0]["admin_login"] == "admin"
    selected = await audit_actions(admin, action="WINNER_SELECTED", draw_id=d["id"])
    assert len(selected) == 1
    assert selected[0]["participant_id"] == r.json()["current_result"]["participant"]["id"]


async def test_previous_winners_excluded_by_default_and_override(client, admin):
    a = await register(client, "Первый", "Победитель")
    b = await register(client, "Второй", "Участник")
    d1 = await create_draw(admin, "Розыгрыш №1")
    d2 = await create_draw(admin, "Розыгрыш №2")
    r = await admin.post(f"/api/admin/draws/{d1['id']}/start")
    winner_id = r.json()["current_result"]["participant"]["id"]
    r = await admin.post(f"/api/admin/draws/{d1['id']}/confirm")
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    assert r.json()["winner"]["id"] == winner_id
    other = b if winner_id == a["id"] else a

    r = await admin.get(f"/api/admin/draws/{d2['id']}")
    assert r.json()["eligible_count"] == 1
    assert r.json()["effective_exclude_previous_winners"] is True
    r = await admin.post(f"/api/admin/draws/{d2['id']}/start")
    assert r.json()["current_result"]["participant"]["id"] == other["id"]
    await admin.post(f"/api/admin/draws/{d2['id']}/confirm")

    # global setting off => both participate
    d3 = await create_draw(admin, "Розыгрыш №3")
    await admin.put("/api/admin/settings", json={"allow_previous_winners": True})
    r = await admin.get(f"/api/admin/draws/{d3['id']}")
    assert r.json()["eligible_count"] == 2
    assert r.json()["effective_exclude_previous_winners"] is False
    # per-draw override wins over the global setting
    r = await admin.patch(f"/api/admin/draws/{d3['id']}", json={"exclude_previous_winners": True})
    assert r.status_code == 200 and r.json()["exclude_previous_winners"] is True
    r = await admin.get(f"/api/admin/draws/{d3['id']}")
    assert r.json()["eligible_count"] == 0
    r = await admin.post(f"/api/admin/draws/{d3['id']}/start")
    assert r.json()["error"]["code"] == "NO_ELIGIBLE_PARTICIPANTS"
    await admin.put("/api/admin/settings", json={"allow_previous_winners": False})
    r = await admin.patch(f"/api/admin/draws/{d3['id']}", json={"exclude_previous_winners": False})
    r = await admin.get(f"/api/admin/draws/{d3['id']}")
    assert r.json()["eligible_count"] == 2
    # participant flags
    r = await admin.get("/api/admin/participants", params={"won": "true"})
    assert r.json()["total"] == 2 and all(i["has_won"] for i in r.json()["items"])


async def test_redraw_rejects_and_never_repicks_same_participant(client, admin):
    a = await register(client, "А", "Первый")
    b = await register(client, "Б", "Второй")
    d = await create_draw(admin)
    r = await admin.post(f"/api/admin/draws/{d['id']}/start")
    first = r.json()["current_result"]["participant"]["id"]
    r = await admin.post(f"/api/admin/draws/{d['id']}/redraw", json={"reason": "не в зале"})
    assert r.status_code == 200, r.text
    body = r.json()
    second = body["current_result"]["participant"]["id"]
    assert second != first and second in (a["id"], b["id"])
    assert body["status"] == "PENDING_CONFIRMATION"
    assert len(body["results"]) == 2
    assert body["results"][0]["status"] == "SELECTED"
    assert body["results"][1]["status"] == "REJECTED"
    assert body["results"][1]["reason"] == "не в зале"
    assert body["results"][1]["participant"]["id"] == first
    assert body["results"][0]["eligible_count"] == 1
    # third redraw: nobody left (both rejected) => 409, state unchanged
    r = await admin.post(f"/api/admin/draws/{d['id']}/redraw")
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_ELIGIBLE_PARTICIPANTS"
    r = await admin.get(f"/api/admin/draws/{d['id']}")
    assert r.json()["current_result"]["participant"]["id"] == second
    assert len(r.json()["results"]) == 2
    entries = await audit_actions(admin, action="DRAW_REDRAW", draw_id=d["id"])
    assert len(entries) == 1
    assert entries[0]["metadata"]["reason"] == "не в зале"
    assert entries[0]["participant_id"] == first


async def test_double_start_concurrent_creates_one_result(client, admin):
    for _ in range(10):
        await register(client, "Имя", "Ф")
    d = await create_draw(admin)
    responses = await asyncio.gather(
        *(admin.post(f"/api/admin/draws/{d['id']}/start") for _ in range(5))
    )
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 409, 409, 409, 409]
    for r in responses:
        if r.status_code == 409:
            assert r.json()["error"]["code"] == "INVALID_STATUS"
    async with engine.connect() as conn:
        n = (await conn.execute(text("SELECT count(*) FROM draw_results"))).scalar_one()
    assert n == 1


async def test_another_draw_active(client, admin):
    await register(client)
    d1 = await create_draw(admin, "Розыгрыш №1")
    d2 = await create_draw(admin, "Розыгрыш №2")
    await admin.post(f"/api/admin/draws/{d1['id']}/start")
    r = await admin.post(f"/api/admin/draws/{d2['id']}/start")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ANOTHER_DRAW_ACTIVE"
    assert r.json()["error"]["details"]["draw_id"] == d1["id"]


async def test_completed_draw_is_immutable(client, admin):
    await register(client)
    d = await create_draw(admin)
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    r = await admin.post(f"/api/admin/draws/{d['id']}/confirm")
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    assert r.json()["completed_at"] and r.json()["winner"]
    assert r.json()["current_result"]["status"] == "CONFIRMED"
    url = f"/api/admin/draws/{d['id']}"
    checks = [
        (admin.patch(url, json={"title": "x"}), "DRAW_NOT_EDITABLE"),
        (admin.delete(url), "DRAW_NOT_DELETABLE"),
        (admin.post(f"{url}/cancel"), "INVALID_STATUS"),
        (admin.post(f"{url}/start"), "INVALID_STATUS"),
        (admin.post(f"{url}/redraw"), "INVALID_STATUS"),
        (admin.post(f"{url}/confirm"), "INVALID_STATUS"),
    ]
    for coro, code in checks:
        r = await coro
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == code
    r = await admin.get(url)
    assert r.json()["status"] == "COMPLETED" and len(r.json()["results"]) == 1
    confirmed = await audit_actions(admin, action="WINNER_CONFIRMED", draw_id=d["id"])
    assert len(confirmed) == 1
    winners = (await admin.get("/api/admin/winners")).json()["items"]
    assert len(winners) == 1 and winners[0]["draw_id"] == d["id"]
    assert winners[0]["number"] == 1000 and winners[0]["confirmed_at"]


async def test_draw_crud_and_audit(client, admin):
    d = await create_draw(admin, "Розыгрыш №1", "Авиабилеты", description="desc")
    assert d["position"] == 1 and d["status"] == "DRAFT" and d["exclude_previous_winners"] is None
    d2 = await create_draw(admin, "Розыгрыш №2", "Отель", position=5)
    d3 = await create_draw(admin, "Розыгрыш №3", "Тур")
    assert (d2["position"], d3["position"]) == (5, 6)
    r = await admin.get("/api/admin/draws")
    assert [x["title"] for x in r.json()["items"]] == ["Розыгрыш №1", "Розыгрыш №2", "Розыгрыш №3"]

    r = await admin.patch(
        f"/api/admin/draws/{d['id']}", json={"prize": "Билеты", "description": None}
    )
    assert (
        r.status_code == 200 and r.json()["prize"] == "Билеты" and r.json()["description"] is None
    )
    upd = await audit_actions(admin, action="DRAW_UPDATED", draw_id=d["id"])
    assert upd[0]["metadata"]["changes"]["prize"] == {"old": "Авиабилеты", "new": "Билеты"}

    r = await admin.post(f"/api/admin/draws/{d3['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    r = await admin.post(f"/api/admin/draws/{d3['id']}/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_STATUS"
    r = await admin.delete(f"/api/admin/draws/{d3['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "DRAW_NOT_DELETABLE"

    r = await admin.delete(f"/api/admin/draws/{d2['id']}")
    assert r.status_code == 204
    r = await admin.get(f"/api/admin/draws/{d2['id']}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"

    r = await admin.post("/api/admin/draws", json={"title": "", "prize": "x"})
    assert r.status_code == 422 and "title" in r.json()["error"]["details"]["fields"]

    actions = {e["action"] for e in await audit_actions(admin)}
    assert {"DRAW_CREATED", "DRAW_UPDATED", "DRAW_CANCELLED", "DRAW_DELETED"} <= actions


async def test_pending_participant_cannot_be_deleted_or_disqualified(client, admin):
    p = await register(client)
    d = await create_draw(admin)
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    r = await admin.get(f"/api/admin/participants/{p['id']}")
    assert r.json()["pending_result"] is True and r.json()["has_won"] is False
    assert r.json()["results"][0]["draw"]["id"] == d["id"]
    r = await admin.delete(f"/api/admin/participants/{p['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "PARTICIPANT_HAS_PENDING_RESULT"
    r = await admin.post(f"/api/admin/participants/{p['id']}/disqualify")
    assert r.status_code == 409 and r.json()["error"]["code"] == "PARTICIPANT_HAS_PENDING_RESULT"
    await admin.post(f"/api/admin/draws/{d['id']}/confirm")
    r = await admin.get(f"/api/admin/participants/{p['id']}")
    assert r.json()["has_won"] is True and r.json()["pending_result"] is False
    r = await admin.post(f"/api/admin/participants/{p['id']}/disqualify", json={"reason": "r"})
    assert r.status_code == 200 and r.json()["status"] == "DISQUALIFIED"
    assert r.json()["status_reason"] == "r"
    r = await admin.post(f"/api/admin/participants/{p['id']}/restore")
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
    r = await admin.delete(f"/api/admin/participants/{p['id']}")
    assert r.status_code == 204
    r = await admin.post(f"/api/admin/participants/{p['id']}/disqualify")
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_STATUS"
    r = await admin.post(f"/api/admin/participants/{p['id']}/restore")
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
    actions = {e["action"] for e in await audit_actions(admin, participant_id=p["id"])}
    assert {
        "PARTICIPANT_REGISTERED", "PARTICIPANT_DISQUALIFIED", "PARTICIPANT_RESTORED",
        "PARTICIPANT_DELETED", "WINNER_SELECTED", "WINNER_CONFIRMED",
    } <= actions  # fmt: skip
