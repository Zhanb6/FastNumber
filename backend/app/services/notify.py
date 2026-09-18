"""PostgreSQL NOTIFY helpers. Executed inside the transaction => delivered on commit."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LIVE_CHANNEL = "live_events"
PARTICIPANTS_CHANNEL = "participants_changed"


async def notify_live(session: AsyncSession, reason: str) -> None:
    await session.execute(
        text("SELECT pg_notify(:ch, :payload)"), {"ch": LIVE_CHANNEL, "payload": reason}
    )


async def notify_participants(session: AsyncSession, reason: str = "changed") -> None:
    await session.execute(
        text("SELECT pg_notify(:ch, :payload)"), {"ch": PARTICIPANTS_CHANNEL, "payload": reason}
    )
