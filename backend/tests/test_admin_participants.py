from tests.conftest import create_draw, register


async def test_list_filters_sort_pagination(client, admin):
    ids = {}
    for i, (first, last) in enumerate(
        [
            ("Айгерим", "Ахметова"),
            ("Данияр", "Сериков"),
            ("Алия", "Нурланова"),
            ("Ерлан", "Абдуллин"),
        ]
    ):
        ids[i] = await register(client, first, last)
    await admin.post(f"/api/admin/participants/{ids[1]['id']}/disqualify")
    await admin.delete(f"/api/admin/participants/{ids[2]['id']}")

    r = await admin.get("/api/admin/participants")
    body = r.json()
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 50
    assert [i["number"] for i in body["items"]] == [1000, 1001, 1003]
    assert {i["status"] for i in body["items"]} == {"ACTIVE", "DISQUALIFIED"}
    assert body["items"][0]["has_won"] is False and body["items"][0]["pending_result"] is False

    r = await admin.get("/api/admin/participants", params={"status": "all", "sort": "-number"})
    assert [i["number"] for i in r.json()["items"]] == [1003, 1002, 1001, 1000]
    r = await admin.get("/api/admin/participants", params={"status": "DELETED"})
    assert [i["number"] for i in r.json()["items"]] == [1002]
    r = await admin.get("/api/admin/participants", params={"q": "ай"})
    assert [i["first_name"] for i in r.json()["items"]] == ["Айгерим"]
    r = await admin.get("/api/admin/participants", params={"q": "1003"})
    assert [i["number"] for i in r.json()["items"]] == [1003]
    r = await admin.get("/api/admin/participants", params={"q": "ов"})
    assert r.json()["total"] == 2  # deleted "Нурланова" hidden by default
    r = await admin.get("/api/admin/participants", params={"page": 2, "page_size": 2})
    assert [i["number"] for i in r.json()["items"]] == [1003] and r.json()["total"] == 3
    r = await admin.get("/api/admin/participants", params={"sort": "-created_at"})
    assert r.json()["items"][0]["number"] == 1003
    r = await admin.get("/api/admin/participants", params={"won": "false"})
    assert r.json()["total"] == 3
    r = await admin.get("/api/admin/participants", params={"won": "true"})
    assert r.json()["total"] == 0


async def test_stats(client, admin):
    r = await admin.get("/api/admin/stats")
    assert r.json()["total_participants"] == 0 and r.json()["live_state"] == "IDLE"
    await register(client)
    await register(client)
    d = await create_draw(admin)
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    await admin.post(f"/api/admin/draws/{d['id']}/confirm")
    r = await admin.get("/api/admin/stats")
    body = r.json()
    assert body["total_participants"] == 2
    assert body["today_participants"] == 2
    assert body["draws_completed"] == 1 and body["winners_count"] == 1
    assert body["registration_open"] is True
    assert body["timezone"] == "Asia/Almaty"
    assert body["public_base_url"] == "http://localhost"
    assert body["live_state"] == "COMPLETED"
    assert body["event_name"] == "Kazakhstan Travel Forum 2026"
