import re

from tests.conftest import audit_actions, create_draw, register


async def test_participants_csv_format_and_injection_guard(client, admin):
    await admin.put("/api/admin/settings", json={"fields": {"company": {"enabled": True}}})
    await register(client, "-Иван", "Иванов", company="=SUM(1)")
    await register(client, "Айгерим", "Ахметова", company="@ZIZ")
    r = await admin.get("/api/admin/export/participants")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    cd = r.headers["content-disposition"]
    assert re.fullmatch(
        r'attachment; filename="ktf-2026_participants_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.csv"', cd
    ), cd
    raw = r.content
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    lines = text.split("\r\n")
    assert lines[0] == (
        "number;first_name;last_name;phone;email;company;status;status_reason;has_won;created_at"
    )
    assert lines[1].startswith("1000;'-Иван;Иванов;;;'=SUM(1);ACTIVE;;false;")
    assert lines[2].startswith("1001;Айгерим;Ахметова;;;'@ZIZ;ACTIVE;;false;")
    assert "\n" not in text.replace("\r\n", "")
    entries = await audit_actions(admin, action="EXPORT")
    assert len(entries) == 1 and entries[0]["metadata"]["kind"] == "participants"
    assert entries[0]["metadata"]["rows"] == 2

    r = await admin.get("/api/admin/export/participants", params={"q": "Айгерим"})
    assert r.content.decode("utf-8-sig").count("\r\n") == 2


async def test_winners_and_audit_csv(client, admin):
    await register(client, "-Победитель", "Фамилия")
    d = await create_draw(admin, "+Розыгрыш", "@Приз")
    await admin.post(f"/api/admin/draws/{d['id']}/start")
    await admin.post(f"/api/admin/draws/{d['id']}/confirm")

    r = await admin.get("/api/admin/export/winners")
    lines = r.content.decode("utf-8-sig").split("\r\n")
    assert lines[0] == "draw_position;draw_title;prize;number;first_name;last_name;confirmed_at"
    assert lines[1].startswith("1;'+Розыгрыш;'@Приз;1000;'-Победитель;Фамилия;20")
    assert 'filename="ktf-2026_winners_' in r.headers["content-disposition"]

    r = await admin.get("/api/admin/export/audit", params={"draw_id": d["id"]})
    text = r.content.decode("utf-8-sig")
    lines = text.split("\r\n")
    assert lines[0] == (
        "id;created_at;action;entity_type;entity_id;participant_id;draw_id;admin_login;ip;metadata"
    )
    assert re.match(r"^\d+;\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2};DRAW_CREATED;draw;", lines[1])
    assert "WINNER_CONFIRMED" in text
    kinds = [e["metadata"]["kind"] for e in await audit_actions(admin, action="EXPORT")]
    assert sorted(kinds) == ["audit", "winners"]
