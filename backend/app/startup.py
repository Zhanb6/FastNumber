"""Idempotent startup step: settings defaults, singleton rows, admin upsert, optional seed.

Run by the container entrypoint (`python -m app.startup`) and again from the app
lifespan; every step is a no-op when already done.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.models import LiveState, LiveStateValue, Participant
from app.services.auth import upsert_admin_from_env
from app.services.numbering import ensure_counter
from app.services.settings import ensure_defaults, get_settings

log = logging.getLogger("app.startup")


async def ensure_singletons(session: AsyncSession) -> None:
    """Settings defaults, live_state and number_counter rows. Does not commit."""
    await ensure_defaults(session)
    settings = await get_settings(session)
    stmt = pg_insert(LiveState).values(id=1, state=LiveStateValue.IDLE)
    await session.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))
    await ensure_counter(session, settings.start_number)


async def run_startup(session: AsyncSession) -> None:
    await ensure_singletons(session)
    await upsert_admin_from_env(session)
    await session.commit()

    if get_config().seed_demo:
        has_participants = (
            await session.execute(select(Participant.id).limit(1))
        ).scalar_one_or_none()
        if has_participants is None:
            from scripts.seed import seed  # local import: scripts depend on app

            await seed(session)


async def main() -> None:
    from app.db import async_session, engine

    async with async_session() as session:
        await run_startup(session)
    await engine.dispose()
    log.info("startup step done")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
