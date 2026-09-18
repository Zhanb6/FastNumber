"""Test fixtures: real PostgreSQL (TEST_DATABASE_URL), migrations once per session,
tables truncated between tests."""

import os
import subprocess
import sys
from pathlib import Path

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://eventdraw:eventdraw@localhost:5433/eventdraw_test"
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["ADMIN_LOGIN"] = "admin"
os.environ["ADMIN_PASSWORD"] = "secret123"
os.environ["PUBLIC_BASE_URL"] = "http://localhost"
os.environ["DRAW_SCREEN_KEY"] = ""
os.environ["ALLOWED_ORIGINS"] = ""
os.environ["REGISTER_RATE_LIMIT_PER_MIN"] = "0"
os.environ["START_NUMBER"] = "1000"
os.environ["MAX_NUMBER"] = "2000"
os.environ["ON_MAX_REACHED"] = "continue"
os.environ["ALLOW_PREVIOUS_WINNERS"] = "false"
os.environ["REGISTRATION_OPEN"] = "true"
os.environ["SEED_DEMO"] = "false"
os.environ["EVENT_TIMEZONE"] = "Asia/Almaty"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import get_config  # noqa: E402
from app.db import async_session, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import settings as settings_service  # noqa: E402
from app.services.ratelimit import login_limiter, register_limiter  # noqa: E402
from app.startup import run_startup  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
ADMIN_PASSWORD = "secret123"


@pytest.fixture(scope="session", autouse=True)
def migrate_db():
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    alembic = [sys.executable, "-m", "alembic"]
    subprocess.run([*alembic, "downgrade", "base"], cwd=BACKEND_DIR, env=env, check=True)
    subprocess.run([*alembic, "upgrade", "head"], cwd=BACKEND_DIR, env=env, check=True)
    yield


@pytest.fixture(scope="session", autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db():
    cfg = get_config()
    cfg.draw_screen_key = ""
    cfg.register_rate_limit_per_min = 0
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE participants, draws, draw_results, audit_log, settings, admins "
                "RESTART IDENTITY CASCADE"
            )
        )
        await conn.execute(text("UPDATE live_state SET state='IDLE', draw_id=NULL"))
        await conn.execute(text("DELETE FROM number_counter"))
    settings_service.invalidate_cache()
    register_limiter.clear()
    login_limiter.clear()
    async with async_session() as session:
        await run_startup(session)
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def login(c: AsyncClient) -> None:
    r = await c.post("/api/admin/auth/login", json={"login": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text


@pytest.fixture
async def admin(client: AsyncClient):
    await login(client)
    return client


async def register(c: AsyncClient, first: str = "Иван", last: str = "Иванов", **extra) -> dict:
    r = await c.post("/api/register", json={"first_name": first, "last_name": last, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def create_draw(
    c: AsyncClient, title: str = "Розыгрыш №1", prize: str = "Авиабилеты", **extra
):
    r = await c.post("/api/admin/draws", json={"title": title, "prize": prize, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def audit_actions(c: AsyncClient, **params) -> list[dict]:
    r = await c.get("/api/admin/audit", params={"page_size": 200, **params})
    assert r.status_code == 200
    return r.json()["items"]
