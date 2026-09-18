"""LiveSnapshot derived from the persisted live_state row (see API contract)."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Draw,
    DrawResult,
    DrawResultStatus,
    DrawStatus,
    LiveState,
    LiveStateValue,
    Participant,
    ParticipantStatus,
)
from app.services.draw import LIVE_ID, eligible_numbers
from app.services.settings import get_settings
from app.util import now_ms, to_ms

POOL_CAP = 3000


async def active_count(session: AsyncSession) -> int:
    stmt = select(func.count(Participant.id)).where(Participant.status == ParticipantStatus.ACTIVE)
    return int((await session.execute(stmt)).scalar_one())


async def next_draft(session: AsyncSession) -> Draw | None:
    stmt = (
        select(Draw)
        .where(Draw.status == DrawStatus.DRAFT)
        .order_by(Draw.position, Draw.created_at)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def build_snapshot(session: AsyncSession) -> dict[str, Any]:
    settings = await get_settings(session)
    live = await session.get(LiveState, LIVE_ID, populate_existing=True)
    nxt = await next_draft(session)
    snapshot: dict[str, Any] = {
        "type": "state",
        "state": LiveStateValue.IDLE.value,
        "server_time": now_ms(),
        "participants_count": await active_count(session),
        "event_name": settings.event_name,
        "animation_duration_ms": settings.animation.duration_ms,
        "draw": None,
        "next_draw": {"id": str(nxt.id), "title": nxt.title, "prize": nxt.prize} if nxt else None,
        "winner": None,
        "number_pool": None,
    }
    if live is None or live.state == LiveStateValue.IDLE or live.draw_id is None:
        return snapshot

    draw = await session.get(Draw, live.draw_id, populate_existing=True)
    stmt = (
        select(DrawResult)
        .where(
            DrawResult.draw_id == live.draw_id,
            DrawResult.status.in_([DrawResultStatus.SELECTED, DrawResultStatus.CONFIRMED]),
        )
        .order_by(DrawResult.created_at.desc())
        .limit(1)
        .options(selectinload(DrawResult.participant))
    ).execution_options(populate_existing=True)
    result = (await session.execute(stmt)).scalar_one_or_none()
    if draw is None or result is None:
        return snapshot

    started_ms = to_ms(result.created_at)
    if live.state == LiveStateValue.COMPLETED:
        state = LiveStateValue.COMPLETED
    else:
        elapsed = snapshot["server_time"] - started_ms
        if elapsed < 1000:
            state = LiveStateValue.COUNTDOWN
        elif elapsed < settings.animation.duration_ms:
            state = LiveStateValue.DRAWING
        else:
            state = LiveStateValue.WINNER

    winner = result.participant
    pool = set(await eligible_numbers(session, draw, settings))
    pool.add(winner.number)
    numbers = sorted(pool)
    if len(numbers) > POOL_CAP:
        numbers = numbers[:POOL_CAP]
        if winner.number not in numbers:
            numbers[-1] = winner.number
            numbers.sort()

    snapshot.update(
        {
            "state": state.value,
            "draw": {
                "id": str(draw.id),
                "title": draw.title,
                "prize": draw.prize,
                "started_at": started_ms,
            },
            "winner": {
                "number": winner.number,
                "first_name": winner.first_name,
                "last_name": winner.last_name,
            },
            "number_pool": numbers,
        }
    )
    return snapshot
