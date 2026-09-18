"""Wipe draw_results, draws and participants (hard delete) before the event.

    python -m scripts.reset --confirm

Resets the number counter to the configured start number (participants table is
empty afterwards), sets live_state to IDLE and writes a RESET audit entry.
"""

import argparse
import asyncio
import sys

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Draw, DrawResult, LiveStateValue, Participant
from app.services import audit
from app.services.draw import lock_live
from app.services.notify import notify_live, notify_participants
from app.services.numbering import reset_counter
from app.services.settings import get_settings
from app.util import utcnow


async def _count(session: AsyncSession, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def reset(session: AsyncSession, *, admin_login: str = "cli") -> dict[str, int]:
    settings = await get_settings(session)
    live = await lock_live(session)
    counts = {}
    for name, model in (
        ("draw_results", DrawResult),
        ("draws", Draw),
        ("participants", Participant),
    ):
        counts[name] = int(
            (await session.execute(select(func.count()).select_from(model))).scalar_one()
        )

    live.state = LiveStateValue.IDLE
    live.draw_id = None
    live.updated_at = utcnow()
    await session.flush()
    await session.execute(delete(DrawResult))
    await session.execute(delete(Draw))
    await session.execute(delete(Participant))

    remaining = int(
        (await session.execute(select(func.count()).select_from(Participant))).scalar_one()
    )
    counter_reset = remaining == 0
    if counter_reset:
        await reset_counter(session, settings.start_number)

    audit.log(
        session,
        "RESET",
        entity_type="system",
        admin_login=admin_login,
        metadata={
            "deleted": counts,
            "counter_reset_to": settings.start_number if counter_reset else None,
        },
    )
    await notify_live(session, "reset")
    await notify_participants(session, "reset")
    await session.commit()
    return counts


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Delete all participants, draws and results")
    parser.add_argument("--confirm", action="store_true", help="actually perform the reset")
    args = parser.parse_args(argv)
    if not args.confirm:
        print("Refusing to reset without --confirm", file=sys.stderr)
        return 2

    from app.db import async_session, engine
    from app.startup import ensure_singletons

    async with async_session() as session:
        await ensure_singletons(session)
        await session.commit()
        counts = await reset(session)
    await engine.dispose()
    print(
        "Reset done: deleted "
        f"{counts['draw_results']} results, {counts['draws']} draws, "
        f"{counts['participants']} participants; live_state=IDLE"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
