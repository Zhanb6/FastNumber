"""Admin operations on participants, winners and dashboard stats."""

import re
import uuid
from datetime import datetime, time
from typing import Any

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import ApiError, not_found
from app.models import (
    Draw,
    DrawResult,
    DrawResultStatus,
    DrawStatus,
    LiveState,
    Participant,
    ParticipantStatus,
)
from app.services import audit
from app.services.notify import notify_participants
from app.services.registration import normalise_phone
from app.services.settings import get_settings
from app.util import utcnow

HAS_WON = (
    exists()
    .where(
        DrawResult.participant_id == Participant.id,
        DrawResult.status == DrawResultStatus.CONFIRMED,
    )
    .label("has_won")
)
PENDING_RESULT = (
    exists()
    .where(
        DrawResult.participant_id == Participant.id,
        DrawResult.status == DrawResultStatus.SELECTED,
    )
    .label("pending_result")
)

SORTS = {
    "number": Participant.number.asc(),
    "-number": Participant.number.desc(),
    "created_at": Participant.created_at.asc(),
    "-created_at": Participant.created_at.desc(),
}


INT32_MAX = 2**31 - 1
PHONE_MIN_DIGITS = 4


def as_number(value: str) -> int | None:
    """Parse a search term as a participant number, or None if it is not one.

    `str.isdigit()` is true for characters like "²" that `int()` rejects, and a
    phone number does not fit the INTEGER column — both used to raise a 500.
    """
    try:
        number = int(value)
    except ValueError:
        return None
    return number if 0 <= number <= INT32_MAX else None


def phone_conditions(value: str) -> list[Any]:
    """Match a search term against stored E.164 phones.

    People give their phone in whatever shape they remember it, and the desk may
    only be told the last few digits, so match both the normalised number and a
    digit substring.
    """
    conds: list[Any] = []
    normalised = normalise_phone(value)
    if normalised:
        conds.append(Participant.phone == normalised)
    digits = re.sub(r"\D", "", value)
    if len(digits) >= PHONE_MIN_DIGITS:
        conds.append(Participant.phone.like(f"%{digits}%"))
    return conds


def apply_filters(stmt: Select, *, q: str | None, status: str | None, won: bool | None) -> Select:
    if status is None or status == "":
        stmt = stmt.where(
            Participant.status.in_([ParticipantStatus.ACTIVE, ParticipantStatus.DISQUALIFIED])
        )
    elif status != "all":
        stmt = stmt.where(Participant.status == ParticipantStatus(status))
    if q:
        q = q.strip()
        conds = [Participant.first_name.ilike(f"%{q}%"), Participant.last_name.ilike(f"%{q}%")]
        number = as_number(q)
        if number is not None:
            conds.append(Participant.number == number)
        conds.extend(phone_conditions(q))
        stmt = stmt.where(or_(*conds))
    if won is True:
        stmt = stmt.where(HAS_WON)
    elif won is False:
        stmt = stmt.where(~HAS_WON)
    return stmt


async def list_participants(
    session: AsyncSession,
    *,
    q: str | None,
    status: str | None,
    won: bool | None,
    page: int,
    page_size: int,
    sort: str,
) -> tuple[list[tuple[Participant, bool, bool]], int]:
    base = apply_filters(select(Participant), q=q, status=status, won=won)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = (
        apply_filters(select(Participant, HAS_WON, PENDING_RESULT), q=q, status=status, won=won)
        .order_by(SORTS.get(sort, SORTS["number"]), Participant.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).all()
    return [(r[0], bool(r[1]), bool(r[2])) for r in rows], int(total)


async def iter_participants_for_export(
    session: AsyncSession, *, q: str | None, status: str | None, won: bool | None
) -> list[tuple[Participant, bool]]:
    stmt = apply_filters(select(Participant, HAS_WON), q=q, status=status, won=won).order_by(
        Participant.number
    )
    rows = (await session.execute(stmt)).all()
    return [(r[0], bool(r[1])) for r in rows]


async def get_with_flags(
    session: AsyncSession, participant_id: uuid.UUID
) -> tuple[Participant, bool, bool]:
    stmt = (
        select(Participant, HAS_WON, PENDING_RESULT)
        .where(Participant.id == participant_id)
        .execution_options(populate_existing=True)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise not_found("Participant")
    return row[0], bool(row[1]), bool(row[2])


async def participant_results(session: AsyncSession, participant_id: uuid.UUID) -> list[DrawResult]:
    stmt = (
        select(DrawResult)
        .where(DrawResult.participant_id == participant_id)
        .options(selectinload(DrawResult.draw), selectinload(DrawResult.participant))
        .order_by(DrawResult.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def _lock_participant(session: AsyncSession, participant_id: uuid.UUID) -> Participant:
    stmt = select(Participant).where(Participant.id == participant_id).with_for_update()
    p = (await session.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise not_found("Participant")
    return p


async def _has_pending(session: AsyncSession, participant_id: uuid.UUID) -> bool:
    stmt = select(
        exists().where(
            DrawResult.participant_id == participant_id,
            DrawResult.status == DrawResultStatus.SELECTED,
        )
    )
    return bool((await session.execute(stmt)).scalar_one())


def _pending_error() -> ApiError:
    return ApiError(
        409,
        "PARTICIPANT_HAS_PENDING_RESULT",
        "Participant has a pending draw result; confirm or redraw first",
    )


async def disqualify(
    session: AsyncSession,
    participant_id: uuid.UUID,
    *,
    reason: str | None,
    admin_login: str | None,
    ip: str | None,
) -> None:
    p = await _lock_participant(session, participant_id)
    if p.status == ParticipantStatus.DELETED:
        raise ApiError(409, "INVALID_STATUS", "Participant is deleted", {"status": p.status.value})
    if await _has_pending(session, p.id):
        raise _pending_error()
    p.status = ParticipantStatus.DISQUALIFIED
    p.status_reason = (reason or "").strip() or None
    audit.log(
        session,
        "PARTICIPANT_DISQUALIFIED",
        entity_type="participant",
        entity_id=p.id,
        participant_id=p.id,
        admin_login=admin_login,
        ip=ip,
        metadata={"number": p.number, "reason": p.status_reason},
    )
    await notify_participants(session, "disqualified")
    await session.commit()


async def restore(
    session: AsyncSession, participant_id: uuid.UUID, *, admin_login: str | None, ip: str | None
) -> None:
    p = await _lock_participant(session, participant_id)
    if p.status == ParticipantStatus.ACTIVE:
        raise ApiError(409, "INVALID_STATUS", "Participant is already active", {"status": "ACTIVE"})
    previous = p.status.value
    p.status = ParticipantStatus.ACTIVE
    p.status_reason = None
    audit.log(
        session,
        "PARTICIPANT_RESTORED",
        entity_type="participant",
        entity_id=p.id,
        participant_id=p.id,
        admin_login=admin_login,
        ip=ip,
        metadata={"number": p.number, "previous_status": previous},
    )
    await notify_participants(session, "restored")
    await session.commit()


async def soft_delete(
    session: AsyncSession, participant_id: uuid.UUID, *, admin_login: str | None, ip: str | None
) -> None:
    p = await _lock_participant(session, participant_id)
    if p.status == ParticipantStatus.DELETED:
        await session.rollback()
        return
    if await _has_pending(session, p.id):
        raise _pending_error()
    previous = p.status.value
    p.status = ParticipantStatus.DELETED
    audit.log(
        session,
        "PARTICIPANT_DELETED",
        entity_type="participant",
        entity_id=p.id,
        participant_id=p.id,
        admin_login=admin_login,
        ip=ip,
        metadata={"number": p.number, "previous_status": previous},
    )
    await notify_participants(session, "deleted")
    await session.commit()


async def list_winners(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(DrawResult, Draw, Participant)
        .join(Draw, Draw.id == DrawResult.draw_id)
        .join(Participant, Participant.id == DrawResult.participant_id)
        .where(DrawResult.status == DrawResultStatus.CONFIRMED)
        .order_by(Draw.completed_at, DrawResult.created_at)
    )
    items = []
    for result, draw, p in (await session.execute(stmt)).all():
        items.append(
            {
                "draw_id": str(draw.id),
                "draw_position": draw.position,
                "draw_title": draw.title,
                "prize": draw.prize,
                "participant_id": str(p.id),
                "number": p.number,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "confirmed_at": draw.completed_at or result.created_at,
            }
        )
    return items


async def stats(session: AsyncSession) -> dict[str, Any]:
    settings = await get_settings(session)
    non_deleted = Participant.status.in_([ParticipantStatus.ACTIVE, ParticipantStatus.DISQUALIFIED])
    total = (
        await session.execute(select(func.count(Participant.id)).where(non_deleted))
    ).scalar_one()
    today_local = utcnow().astimezone(settings.tz).date()
    day_start = datetime.combine(today_local, time.min, tzinfo=settings.tz)
    today = (
        await session.execute(
            select(func.count(Participant.id)).where(
                non_deleted, Participant.created_at >= day_start
            )
        )
    ).scalar_one()
    draws_completed = (
        await session.execute(
            select(func.count(Draw.id)).where(Draw.status == DrawStatus.COMPLETED)
        )
    ).scalar_one()
    winners = (
        await session.execute(
            select(func.count(DrawResult.id)).where(DrawResult.status == DrawResultStatus.CONFIRMED)
        )
    ).scalar_one()
    live = await session.get(LiveState, 1, populate_existing=True)
    return {
        "total_participants": int(total),
        "today_participants": int(today),
        "draws_completed": int(draws_completed),
        "winners_count": int(winners),
        "registration_open": settings.registration_open,
        "event_name": settings.event_name,
        "timezone": settings.timezone,
        "live_state": live.state.value if live else "IDLE",
    }
