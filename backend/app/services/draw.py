"""Draw lifecycle: CRUD, eligibility, start / redraw / confirm, live idle.

All state transitions run in one transaction that locks the draw row and the
single live_state row (SELECT ... FOR UPDATE) and NOTIFY inside the transaction.
"""

import hashlib
import secrets
import uuid
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import ApiError, not_found
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
from app.services import audit
from app.services.notify import notify_live
from app.services.settings import EventSettings, get_settings
from app.util import utcnow

LIVE_ID = 1


# --- eligibility -----------------------------------------------------------


def effective_exclude(draw: Draw, settings: EventSettings) -> bool:
    if draw.exclude_previous_winners is not None:
        return draw.exclude_previous_winners
    return not settings.allow_previous_winners


def eligible_filter(draw_id: uuid.UUID, exclude_previous_winners: bool):
    rejected_here = exists().where(
        DrawResult.participant_id == Participant.id,
        DrawResult.draw_id == draw_id,
        DrawResult.status == DrawResultStatus.REJECTED,
    )
    conds = [Participant.status == ParticipantStatus.ACTIVE, ~rejected_here]
    if exclude_previous_winners:
        confirmed_any = exists().where(
            DrawResult.participant_id == Participant.id,
            DrawResult.status == DrawResultStatus.CONFIRMED,
        )
        conds.append(~confirmed_any)
    return conds


async def list_eligible(
    session: AsyncSession, draw: Draw, settings: EventSettings
) -> list[Participant]:
    stmt = (
        select(Participant)
        .where(*eligible_filter(draw.id, effective_exclude(draw, settings)))
        .order_by(Participant.number)
    )
    return list((await session.execute(stmt)).scalars().all())


async def eligible_numbers(session: AsyncSession, draw: Draw, settings: EventSettings) -> list[int]:
    stmt = (
        select(Participant.number)
        .where(*eligible_filter(draw.id, effective_exclude(draw, settings)))
        .order_by(Participant.number)
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_eligible(session: AsyncSession, draw: Draw, settings: EventSettings) -> int:
    stmt = select(func.count(Participant.id)).where(
        *eligible_filter(draw.id, effective_exclude(draw, settings))
    )
    return int((await session.execute(stmt)).scalar_one())


def eligible_hash(numbers: list[int]) -> str:
    return hashlib.sha256(",".join(str(n) for n in numbers).encode("ascii")).hexdigest()


# --- loading ---------------------------------------------------------------

DRAW_LOAD = (
    selectinload(Draw.results).selectinload(DrawResult.participant),
    selectinload(Draw.winner),
)


async def get_draw(session: AsyncSession, draw_id: uuid.UUID) -> Draw:
    """Load a draw with results and winner (fresh from DB)."""
    stmt = (select(Draw).where(Draw.id == draw_id).options(*DRAW_LOAD)).execution_options(
        populate_existing=True
    )
    draw = (await session.execute(stmt)).scalar_one_or_none()
    if draw is None:
        raise not_found("Draw")
    return draw


async def list_draws(session: AsyncSession) -> list[Draw]:
    stmt = (
        select(Draw).options(*DRAW_LOAD).order_by(Draw.position, Draw.created_at)
    ).execution_options(populate_existing=True)
    return list((await session.execute(stmt)).scalars().all())


async def lock_draw(session: AsyncSession, draw_id: uuid.UUID) -> Draw:
    stmt = select(Draw).where(Draw.id == draw_id).with_for_update()
    draw = (await session.execute(stmt)).scalar_one_or_none()
    if draw is None:
        raise not_found("Draw")
    return draw


async def lock_live(session: AsyncSession) -> LiveState:
    stmt = select(LiveState).where(LiveState.id == LIVE_ID).with_for_update()
    live = (await session.execute(stmt)).scalar_one_or_none()
    if live is None:
        raise RuntimeError("live_state row is missing; run the startup step")
    return live


def current_result(draw: Draw) -> DrawResult | None:
    for r in draw.results:
        if r.status in (DrawResultStatus.SELECTED, DrawResultStatus.CONFIRMED):
            return r
    return None


async def get_selected_result(session: AsyncSession, draw_id: uuid.UUID) -> DrawResult | None:
    stmt = (
        select(DrawResult)
        .where(DrawResult.draw_id == draw_id, DrawResult.status == DrawResultStatus.SELECTED)
        .options(selectinload(DrawResult.participant))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def invalid_status(draw: Draw) -> ApiError:
    return ApiError(
        409,
        "INVALID_STATUS",
        f"Draw is in status {draw.status.value}",
        {"status": draw.status.value},
    )


# --- CRUD ------------------------------------------------------------------


async def create_draw(
    session: AsyncSession, data: dict[str, Any], *, admin_login: str | None, ip: str | None
) -> Draw:
    position = data.get("position")
    if position is None:
        max_pos = (await session.execute(select(func.max(Draw.position)))).scalar_one()
        position = (max_pos or 0) + 1
    draw = Draw(
        position=position,
        title=data["title"],
        prize=data["prize"],
        description=data.get("description"),
        scheduled_at=data.get("scheduled_at"),
        exclude_previous_winners=data.get("exclude_previous_winners"),
        status=DrawStatus.DRAFT,
    )
    session.add(draw)
    await session.flush()
    audit.log(
        session,
        "DRAW_CREATED",
        entity_type="draw",
        entity_id=draw.id,
        draw_id=draw.id,
        admin_login=admin_login,
        ip=ip,
        metadata={"title": draw.title, "prize": draw.prize, "position": draw.position},
    )
    await notify_live(session, "draw_created")
    await session.commit()
    return await get_draw(session, draw.id)


async def update_draw(
    session: AsyncSession,
    draw_id: uuid.UUID,
    changes: dict[str, Any],
    *,
    admin_login: str | None,
    ip: str | None,
) -> Draw:
    draw = await lock_draw(session, draw_id)
    if draw.status != DrawStatus.DRAFT:
        raise ApiError(409, "DRAW_NOT_EDITABLE", "Only DRAFT draws can be edited")
    diff: dict[str, Any] = {}
    for key, new in changes.items():
        old = getattr(draw, key)
        if old != new:
            diff[key] = {"old": _jsonable(old), "new": _jsonable(new)}
            setattr(draw, key, new)
    if diff:
        audit.log(
            session,
            "DRAW_UPDATED",
            entity_type="draw",
            entity_id=draw.id,
            draw_id=draw.id,
            admin_login=admin_login,
            ip=ip,
            metadata={"changes": diff},
        )
        await notify_live(session, "draw_updated")
    await session.commit()
    return await get_draw(session, draw.id)


async def delete_draw(
    session: AsyncSession, draw_id: uuid.UUID, *, admin_login: str | None, ip: str | None
) -> None:
    draw = await lock_draw(session, draw_id)
    has_results = (
        await session.execute(select(exists().where(DrawResult.draw_id == draw.id)))
    ).scalar_one()
    if draw.status != DrawStatus.DRAFT or has_results:
        raise ApiError(409, "DRAW_NOT_DELETABLE", "Only DRAFT draws without results can be deleted")
    audit.log(
        session,
        "DRAW_DELETED",
        entity_type="draw",
        entity_id=draw.id,
        draw_id=draw.id,
        admin_login=admin_login,
        ip=ip,
        metadata={"title": draw.title, "prize": draw.prize},
    )
    await session.delete(draw)
    await notify_live(session, "draw_deleted")
    await session.commit()


async def cancel_draw(
    session: AsyncSession, draw_id: uuid.UUID, *, admin_login: str | None, ip: str | None
) -> Draw:
    draw = await lock_draw(session, draw_id)
    if draw.status != DrawStatus.DRAFT:
        raise invalid_status(draw)
    draw.status = DrawStatus.CANCELLED
    audit.log(
        session,
        "DRAW_CANCELLED",
        entity_type="draw",
        entity_id=draw.id,
        draw_id=draw.id,
        admin_login=admin_login,
        ip=ip,
    )
    await notify_live(session, "draw_cancelled")
    await session.commit()
    return await get_draw(session, draw.id)


# --- start / redraw / confirm / idle ---------------------------------------


async def _pick_winner(
    session: AsyncSession, draw: Draw, settings: EventSettings
) -> tuple[Participant, int, str]:
    """CSPRNG selection among eligible participants sorted by number."""
    eligible = await list_eligible(session, draw, settings)
    if not eligible:
        raise ApiError(409, "NO_ELIGIBLE_PARTICIPANTS", "Нет участников, подходящих для розыгрыша")
    numbers = [p.number for p in eligible]
    digest = eligible_hash(numbers)
    index = secrets.randbelow(len(eligible))
    return eligible[index], len(eligible), digest


def _add_result(
    session: AsyncSession,
    draw: Draw,
    winner: Participant,
    eligible_count: int,
    digest: str,
    *,
    admin_login: str | None,
    ip: str | None,
) -> DrawResult:
    result = DrawResult(
        draw_id=draw.id,
        participant_id=winner.id,
        status=DrawResultStatus.SELECTED,
        eligible_count=eligible_count,
        eligible_hash=digest,
        created_at=utcnow(),
    )
    session.add(result)
    audit.log(
        session,
        "WINNER_SELECTED",
        entity_type="draw_result",
        entity_id=result.id,
        participant_id=winner.id,
        draw_id=draw.id,
        admin_login=admin_login,
        ip=ip,
        metadata={
            "number": winner.number,
            "first_name": winner.first_name,
            "last_name": winner.last_name,
            "eligible_count": eligible_count,
            "eligible_hash": digest,
        },
    )
    return result


async def start_draw(
    session: AsyncSession, draw_id: uuid.UUID, *, admin_login: str | None, ip: str | None
) -> Draw:
    draw = await lock_draw(session, draw_id)
    live = await lock_live(session)
    if draw.status != DrawStatus.DRAFT:
        raise invalid_status(draw)
    other = (
        await session.execute(
            select(Draw.id).where(
                Draw.status == DrawStatus.PENDING_CONFIRMATION, Draw.id != draw.id
            )
        )
    ).scalar_one_or_none()
    if other is not None:
        raise ApiError(
            409,
            "ANOTHER_DRAW_ACTIVE",
            "Another draw is pending confirmation",
            {"draw_id": str(other)},
        )
    settings = await get_settings(session)
    winner, count, digest = await _pick_winner(session, draw, settings)
    now = utcnow()
    draw.status = DrawStatus.PENDING_CONFIRMATION
    draw.started_at = now
    audit.log(
        session,
        "DRAW_STARTED",
        entity_type="draw",
        entity_id=draw.id,
        draw_id=draw.id,
        admin_login=admin_login,
        ip=ip,
        metadata={
            "eligible_count": count,
            "eligible_hash": digest,
            "exclude_previous_winners": effective_exclude(draw, settings),
        },
    )
    _add_result(session, draw, winner, count, digest, admin_login=admin_login, ip=ip)
    live.state = LiveStateValue.COUNTDOWN
    live.draw_id = draw.id
    live.updated_at = now
    await session.flush()
    await notify_live(session, "draw_started")
    await session.commit()
    return await get_draw(session, draw.id)


async def redraw(
    session: AsyncSession,
    draw_id: uuid.UUID,
    *,
    reason: str | None,
    admin_login: str | None,
    ip: str | None,
) -> Draw:
    draw = await lock_draw(session, draw_id)
    live = await lock_live(session)
    if draw.status != DrawStatus.PENDING_CONFIRMATION:
        raise invalid_status(draw)
    current = await get_selected_result(session, draw.id)
    if current is None:
        raise ApiError(409, "INVALID_STATUS", "Draw has no selected result", {"status": "BROKEN"})
    current.status = DrawResultStatus.REJECTED
    current.reason = (reason or "").strip() or None
    await session.flush()  # free the partial unique index before inserting the new result

    settings = await get_settings(session)
    winner, count, digest = await _pick_winner(session, draw, settings)
    audit.log(
        session,
        "DRAW_REDRAW",
        entity_type="draw",
        entity_id=draw.id,
        participant_id=current.participant_id,
        draw_id=draw.id,
        admin_login=admin_login,
        ip=ip,
        metadata={
            "rejected_participant_id": str(current.participant_id),
            "rejected_number": current.participant.number,
            "rejected_result_id": str(current.id),
            "reason": current.reason,
            "eligible_count": count,
            "eligible_hash": digest,
        },
    )
    _add_result(session, draw, winner, count, digest, admin_login=admin_login, ip=ip)
    live.state = LiveStateValue.COUNTDOWN
    live.draw_id = draw.id
    live.updated_at = utcnow()
    await session.flush()
    await notify_live(session, "draw_redraw")
    await session.commit()
    return await get_draw(session, draw.id)


async def confirm(
    session: AsyncSession, draw_id: uuid.UUID, *, admin_login: str | None, ip: str | None
) -> Draw:
    draw = await lock_draw(session, draw_id)
    live = await lock_live(session)
    if draw.status != DrawStatus.PENDING_CONFIRMATION:
        raise invalid_status(draw)
    current = await get_selected_result(session, draw.id)
    if current is None:
        raise ApiError(409, "INVALID_STATUS", "Draw has no selected result", {"status": "BROKEN"})
    now = utcnow()
    current.status = DrawResultStatus.CONFIRMED
    draw.status = DrawStatus.COMPLETED
    draw.winner_id = current.participant_id
    draw.completed_at = now
    audit.log(
        session,
        "WINNER_CONFIRMED",
        entity_type="draw",
        entity_id=draw.id,
        participant_id=current.participant_id,
        draw_id=draw.id,
        admin_login=admin_login,
        ip=ip,
        metadata={
            "number": current.participant.number,
            "first_name": current.participant.first_name,
            "last_name": current.participant.last_name,
            "result_id": str(current.id),
        },
    )
    live.state = LiveStateValue.COMPLETED
    live.draw_id = draw.id
    live.updated_at = now
    await session.flush()
    await notify_live(session, "winner_confirmed")
    await session.commit()
    return await get_draw(session, draw.id)


async def set_idle(session: AsyncSession, *, admin_login: str | None, ip: str | None) -> None:
    live = await lock_live(session)
    previous = {"state": live.state.value, "draw_id": str(live.draw_id) if live.draw_id else None}
    live.state = LiveStateValue.IDLE
    live.draw_id = None
    live.updated_at = utcnow()
    audit.log(
        session,
        "LIVE_IDLE",
        entity_type="live_state",
        admin_login=admin_login,
        ip=ip,
        metadata={"previous": previous},
    )
    await notify_live(session, "idle")
    await session.commit()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
