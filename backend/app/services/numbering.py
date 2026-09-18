"""Atomic number allocation via a single-row counter locked with SELECT ... FOR UPDATE."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NumberCounter

COUNTER_ID = 1


async def ensure_counter(session: AsyncSession, start_number: int) -> None:
    """Insert the counter row if missing (does not commit)."""
    stmt = pg_insert(NumberCounter).values(id=COUNTER_ID, next_value=start_number)
    await session.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))


async def lock_counter(session: AsyncSession) -> NumberCounter:
    """Lock and return the counter row. Must be called inside a transaction."""
    row = (
        await session.execute(
            select(NumberCounter).where(NumberCounter.id == COUNTER_ID).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError("number_counter row is missing; run the startup step")
    return row


async def reset_counter(session: AsyncSession, start_number: int) -> None:
    row = await lock_counter(session)
    row.next_value = start_number
