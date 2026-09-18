import asyncio
import uuid

from sqlalchemy import text

from app.config import get_config
from app.db import engine
from tests.conftest import audit_actions, register


async def test_first_number_is_start_number_and_sequential(client):
    a = await register(client, "Айгерим", "Ахметова")
    b = await register(client, "Данияр", "Сериков")
    c = await register(client, "Alex", "O'Neil-Smith")
    assert (a["number"], b["number"], c["number"]) == (1000, 1001, 1002)
    assert uuid.UUID(a["token"])
    assert a["first_name"] == "Айгерим"


async def test_500_concurrent_registrations_unique_gapless(client):
    async def one(i: int):
        r = await client.post(
            "/api/register",
            json={"first_name": "Имя", "last_name": "Фамилия"},
            headers={"X-Forwarded-For": f"10.0.{i // 250}.{i % 250 + 1}"},
        )
        assert r.status_code == 201, r.text
        return r.json()["number"]

    numbers = await asyncio.gather(*(one(i) for i in range(500)))
    assert len(set(numbers)) == 500
    assert sorted(numbers) == list(range(1000, 1500))


async def test_idempotent_by_device_token(client):
    a = await register(client, "Иван", "Иванов")
    r = await client.post(
        "/api/register",
        json={"first_name": "Другой", "last_name": "Человек", "device_token": a["token"]},
    )
    assert r.status_code == 200
    assert r.json()["number"] == a["number"]
    assert r.json()["first_name"] == "Иван"
    # unknown token => new participant with a fresh token
    r = await client.post(
        "/api/register",
        json={"first_name": "Пётр", "last_name": "Петров", "device_token": str(uuid.uuid4())},
    )
    assert r.status_code == 201
    assert r.json()["number"] == 1001


async def test_me_endpoint(client):
    a = await register(client)
    r = await client.get(f"/api/me/{a['token']}")
    assert r.status_code == 200 and r.json()["number"] == 1000
    r = await client.get(f"/api/me/{uuid.uuid4()}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    r = await client.get("/api/me/not-a-uuid")
    assert r.status_code == 404


async def test_deleted_participant_sees_form_and_number_not_reused(client, admin):
    a = await register(client)
    r = await admin.delete(f"/api/admin/participants/{a['id']}")
    assert r.status_code == 204
    r = await client.get(f"/api/me/{a['token']}")
    assert r.status_code == 404
    # re-register with the old token creates a new participant with the next number
    r = await client.post(
        "/api/register",
        json={"first_name": "Иван", "last_name": "Иванов", "device_token": a["token"]},
    )
    assert r.status_code == 201
    assert r.json()["number"] == 1001
    assert r.json()["token"] != a["token"]


async def test_registration_closed(client, admin):
    r = await admin.put("/api/admin/settings", json={"registration_open": False})
    assert r.status_code == 200 and r.json()["registration_open"] is False
    r = await client.get("/api/config/public")
    assert r.json()["registration_open"] is False
    r = await client.post("/api/register", json={"first_name": "Иван", "last_name": "Иванов"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "REGISTRATION_CLOSED"


async def test_name_validation(client):
    r = await client.post("/api/register", json={"first_name": "", "last_name": "Иванов"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert "first_name" in body["details"]["fields"]
    r = await client.post("/api/register", json={"first_name": "Ив@н", "last_name": "x" * 61})
    assert set(r.json()["error"]["details"]["fields"]) == {"first_name", "last_name"}
    r = await client.post("/api/register", json={"first_name": 5, "last_name": []})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    # Kazakh letters accepted
    r = await client.post(
        "/api/register", json={"first_name": "Әлібек", "last_name": "Әбдіқадырова"}
    )
    assert r.status_code == 201


async def test_optional_fields_and_phone_normalisation(client, admin):
    # disabled fields are ignored
    a = await register(client, phone="8 (700) 123-45-67", email="a@b.kz", company="ZIZ")
    r = await admin.get(f"/api/admin/participants/{a['id']}")
    assert r.json()["phone"] is None and r.json()["email"] is None

    r = await admin.put(
        "/api/admin/settings",
        json={"fields": {"phone": {"enabled": True, "required": True}, "email": {"enabled": True}}},
    )
    assert r.status_code == 200
    assert r.json()["fields"]["phone"] == {"enabled": True, "required": True}
    assert r.json()["fields"]["email"] == {"enabled": True, "required": False}

    r = await client.post("/api/register", json={"first_name": "Иван", "last_name": "Иванов"})
    assert r.status_code == 422 and "phone" in r.json()["error"]["details"]["fields"]

    for raw in ("8 (700) 123-45-67", "77001234567", "+7 700 123 45 67", "7001234567"):
        b = await register(client, "Иван", "Иванов", phone=raw, email="Test@Example.com")
        r = await admin.get(f"/api/admin/participants/{b['id']}")
        assert r.json()["phone"] == "+77001234567", raw
        assert r.json()["email"] == "test@example.com"

    b = await register(client, "John", "Doe", phone="+1 (415) 555-0100")
    r = await admin.get(f"/api/admin/participants/{b['id']}")
    assert r.json()["phone"] == "+14155550100"

    r = await client.post(
        "/api/register", json={"first_name": "Иван", "last_name": "Иванов", "phone": "12345"}
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/register",
        json={"first_name": "Иван", "last_name": "Иванов", "phone": "87001234567", "email": "bad"},
    )
    assert r.status_code == 422 and "email" in r.json()["error"]["details"]["fields"]


async def test_rate_limit_per_ip(client):
    get_config().register_rate_limit_per_min = 3
    for _ in range(3):
        await register(client, "Иван", "Иванов")
    r = await client.post("/api/register", json={"first_name": "Иван", "last_name": "Иванов"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"
    # another IP is fine
    r = await client.post(
        "/api/register",
        json={"first_name": "Иван", "last_name": "Иванов"},
        headers={"X-Real-IP": "192.168.1.77"},
    )
    assert r.status_code == 201


async def test_on_max_reached_close(client, admin):
    r = await admin.put("/api/admin/settings", json={"max_number": 1001, "on_max_reached": "close"})
    assert r.status_code == 200
    assert (await register(client))["number"] == 1000
    assert (await register(client))["number"] == 1001
    r = await client.post("/api/register", json={"first_name": "Иван", "last_name": "Иванов"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "REGISTRATION_CLOSED"
    r = await admin.get("/api/admin/settings")
    assert r.json()["registration_open"] is False
    async with engine.connect() as conn:
        nxt = (await conn.execute(text("SELECT next_value FROM number_counter"))).scalar_one()
    assert nxt == 1002


async def test_registration_audit_and_ip(client, admin):
    r = await client.post(
        "/api/register",
        json={"first_name": "Иван", "last_name": "Иванов"},
        headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1", "User-Agent": "pytest-ua"},
    )
    assert r.status_code == 201
    entries = await audit_actions(admin, action="PARTICIPANT_REGISTERED")
    assert len(entries) == 1
    assert entries[0]["participant_id"] == r.json()["id"]
    assert entries[0]["ip"] == "203.0.113.5"
    assert entries[0]["admin_login"] is None
    assert entries[0]["metadata"]["number"] == 1000


async def test_full_name_mode(client, admin):
    r = await client.get("/api/config/public")
    assert r.json()["name_mode"] == "full"

    r = await client.post("/api/register", json={"full_name": "Нұрғалиева Айгерім Серікқызы"})
    assert r.status_code == 201, r.text
    assert r.json()["first_name"] == "Айгерім Серікқызы"
    assert r.json()["last_name"] == "Нұрғалиева"

    # one word is not enough, empty is required
    for value in ("Иванов", "   ", ""):
        r = await client.post("/api/register", json={"full_name": value})
        assert r.status_code == 422
        assert "full_name" in r.json()["error"]["details"]["fields"]

    r = await client.post("/api/register", json={"full_name": "Иванов Иван1"})
    assert r.status_code == 422

    # split names are still accepted by the API in full mode (backwards compatible)
    r = await client.post("/api/register", json={"first_name": "Иван", "last_name": "Иванов"})
    assert r.status_code == 201

    # switching to split mode makes the split fields the default validation path
    r = await admin.put("/api/admin/settings", json={"name_mode": "split"})
    assert r.status_code == 200 and r.json()["name_mode"] == "split"
    r = await client.post("/api/register", json={})
    assert r.status_code == 422
    assert set(r.json()["error"]["details"]["fields"]) == {"first_name", "last_name"}
    r = await admin.put("/api/admin/settings", json={"name_mode": "bogus"})
    assert r.status_code == 422
