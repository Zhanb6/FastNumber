"""Admin endpoints (session cookie + CSRF origin check)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, csrf_check, require_admin
from app.config import get_config
from app.db import get_session
from app.errors import ApiError
from app.models import AuditLog
from app.schemas.requests import DrawCreate, DrawPatch, LoginIn, ReasonIn, SettingsPatch
from app.schemas.views import (
    audit_view,
    draw_detail,
    draw_ref,
    draw_view,
    participant_admin,
    result_view,
    settings_view,
)
from app.services import audit as audit_service
from app.services import draw as draw_service
from app.services import export as export_service
from app.services import participants as participants_service
from app.services.auth import (
    COOKIE_NAME,
    SESSION_TTL,
    authenticate,
    create_session_token,
)
from app.services.live import build_snapshot
from app.services.ratelimit import login_limiter
from app.services.settings import get_settings
from app.services.settings_update import start_number_locked, update_settings

auth_router = APIRouter(
    prefix="/api/admin/auth", tags=["admin-auth"], dependencies=[Depends(csrf_check)]
)
router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(csrf_check), Depends(require_admin)]
)

PARTICIPANT_STATUSES = {"ACTIVE", "DISQUALIFIED", "DELETED", "all"}


def _validation(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Validation failed", {"fields": {field: message}})


# --- auth -------------------------------------------------------------------


@auth_router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ip = client_ip(request) or "unknown"
    if login_limiter.is_blocked(ip):
        raise ApiError(429, "TOO_MANY_ATTEMPTS", "Too many failed attempts, try again later")
    admin = await authenticate(session, body.login, body.password)
    if admin is None:
        login_limiter.record_failure(ip)
        audit_service.log(
            session,
            "ADMIN_LOGIN_FAILED",
            entity_type="admin",
            admin_login=body.login[:64],
            ip=ip,
        )
        await session.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid login or password")
    login_limiter.reset(ip)
    audit_service.log(
        session,
        "ADMIN_LOGIN",
        entity_type="admin",
        entity_id=admin.id,
        admin_login=admin.login,
        ip=ip,
    )
    await session.commit()
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(admin.login),
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        httponly=True,
        samesite="strict",
        secure=get_config().cookie_secure_effective,
    )
    return {"login": admin.login}


@auth_router.post("/logout", status_code=204)
async def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
        secure=get_config().cookie_secure_effective,
    )
    return response


@auth_router.get("/me")
async def auth_me(admin: str = Depends(require_admin)) -> dict:
    return {"login": admin}


# --- stats ------------------------------------------------------------------


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)) -> dict:
    data = await participants_service.stats(session)
    data["public_base_url"] = get_config().public_base_url
    return data


# --- participants -----------------------------------------------------------


def _parse_status(status: str | None) -> str | None:
    if status is None or status == "":
        return None
    if status not in PARTICIPANT_STATUSES:
        raise _validation("status", "must be ACTIVE, DISQUALIFIED, DELETED or all")
    return status


@router.get("/participants")
async def participants_list(
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(default=None, max_length=100),
    status: str | None = None,
    won: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="number"),
) -> dict:
    if sort not in participants_service.SORTS:
        raise _validation("sort", "must be number, -number, created_at or -created_at")
    rows, total = await participants_service.list_participants(
        session,
        q=q,
        status=_parse_status(status),
        won=won,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    return {
        "items": [participant_admin(p, w, pend) for p, w, pend in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/participants/{participant_id}")
async def participant_detail(
    participant_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    p, has_won, pending = await participants_service.get_with_flags(session, participant_id)
    results = await participants_service.participant_results(session, participant_id)
    view = participant_admin(p, has_won, pending)
    view["results"] = [{**result_view(r), "draw": draw_ref(r.draw)} for r in results]
    return view


@router.post("/participants/{participant_id}/disqualify")
async def participant_disqualify(
    participant_id: uuid.UUID,
    request: Request,
    body: ReasonIn | None = None,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await participants_service.disqualify(
        session,
        participant_id,
        reason=body.reason if body else None,
        admin_login=admin,
        ip=client_ip(request),
    )
    p, has_won, pending = await participants_service.get_with_flags(session, participant_id)
    return participant_admin(p, has_won, pending)


@router.post("/participants/{participant_id}/restore")
async def participant_restore(
    participant_id: uuid.UUID,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await participants_service.restore(
        session, participant_id, admin_login=admin, ip=client_ip(request)
    )
    p, has_won, pending = await participants_service.get_with_flags(session, participant_id)
    return participant_admin(p, has_won, pending)


@router.delete("/participants/{participant_id}", status_code=204)
async def participant_delete(
    participant_id: uuid.UUID,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await participants_service.soft_delete(
        session, participant_id, admin_login=admin, ip=client_ip(request)
    )
    return Response(status_code=204)


# --- draws ------------------------------------------------------------------


async def _detail(session: AsyncSession, draw_id: uuid.UUID) -> dict:
    draw = await draw_service.get_draw(session, draw_id)
    settings = await get_settings(session)
    count = await draw_service.count_eligible(session, draw, settings)
    return draw_detail(draw, count, draw_service.effective_exclude(draw, settings))


@router.get("/draws")
async def draws_list(session: AsyncSession = Depends(get_session)) -> dict:
    return {"items": [draw_view(d) for d in await draw_service.list_draws(session)]}


@router.post("/draws", status_code=201)
async def draws_create(
    body: DrawCreate,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    draw = await draw_service.create_draw(
        session, body.model_dump(), admin_login=admin, ip=client_ip(request)
    )
    return draw_view(draw)


@router.get("/draws/{draw_id}")
async def draws_detail(draw_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    return await _detail(session, draw_id)


@router.patch("/draws/{draw_id}")
async def draws_update(
    draw_id: uuid.UUID,
    body: DrawPatch,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    changes = body.model_dump(exclude_unset=True)
    draw = await draw_service.update_draw(
        session, draw_id, changes, admin_login=admin, ip=client_ip(request)
    )
    return draw_view(draw)


@router.delete("/draws/{draw_id}", status_code=204)
async def draws_delete(
    draw_id: uuid.UUID,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await draw_service.delete_draw(session, draw_id, admin_login=admin, ip=client_ip(request))
    return Response(status_code=204)


@router.post("/draws/{draw_id}/cancel")
async def draws_cancel(
    draw_id: uuid.UUID,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    draw = await draw_service.cancel_draw(
        session, draw_id, admin_login=admin, ip=client_ip(request)
    )
    return draw_view(draw)


@router.post("/draws/{draw_id}/start")
async def draws_start(
    draw_id: uuid.UUID,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await draw_service.start_draw(session, draw_id, admin_login=admin, ip=client_ip(request))
    return await _detail(session, draw_id)


@router.post("/draws/{draw_id}/redraw")
async def draws_redraw(
    draw_id: uuid.UUID,
    request: Request,
    body: ReasonIn | None = None,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await draw_service.redraw(
        session,
        draw_id,
        reason=body.reason if body else None,
        admin_login=admin,
        ip=client_ip(request),
    )
    return await _detail(session, draw_id)


@router.post("/draws/{draw_id}/confirm")
async def draws_confirm(
    draw_id: uuid.UUID,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await draw_service.confirm(session, draw_id, admin_login=admin, ip=client_ip(request))
    return await _detail(session, draw_id)


@router.post("/live/idle")
async def live_idle(
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await draw_service.set_idle(session, admin_login=admin, ip=client_ip(request))
    return await build_snapshot(session)


# --- winners ----------------------------------------------------------------


@router.get("/winners")
async def winners(session: AsyncSession = Depends(get_session)) -> dict:
    items = await participants_service.list_winners(session)
    for item in items:
        item["confirmed_at"] = item["confirmed_at"].isoformat()
    return {"items": items}


# --- audit ------------------------------------------------------------------


def _audit_query(action: str | None, draw_id: uuid.UUID | None, participant_id: uuid.UUID | None):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if draw_id:
        stmt = stmt.where(AuditLog.draw_id == draw_id)
    if participant_id:
        stmt = stmt.where(AuditLog.participant_id == participant_id)
    return stmt


@router.get("/audit/actions")
async def audit_actions(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        await session.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))
    ).scalars()
    return {"items": list(rows)}


@router.get("/audit")
async def audit_list(
    session: AsyncSession = Depends(get_session),
    action: str | None = Query(default=None, max_length=50),
    draw_id: uuid.UUID | None = None,
    participant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    base = _audit_query(action, draw_id, participant_id)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(
            base.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars()
    return {
        "items": [audit_view(e) for e in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


# --- exports ----------------------------------------------------------------


def _csv_response(data: bytes, name: str) -> Response:
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/export/participants")
async def export_participants(
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(default=None, max_length=100),
    status: str | None = None,
    won: bool | None = None,
) -> Response:
    data, name = await export_service.export_participants(
        session,
        q=q,
        status=_parse_status(status),
        won=won,
        admin_login=admin,
        ip=client_ip(request),
    )
    return _csv_response(data, name)


@router.get("/export/winners")
async def export_winners(
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    data, name = await export_service.export_winners(
        session, admin_login=admin, ip=client_ip(request)
    )
    return _csv_response(data, name)


@router.get("/export/audit")
async def export_audit(
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    action: str | None = Query(default=None, max_length=50),
    draw_id: uuid.UUID | None = None,
    participant_id: uuid.UUID | None = None,
) -> Response:
    entries = list(
        (
            await session.execute(
                _audit_query(action, draw_id, participant_id).order_by(AuditLog.id)
            )
        ).scalars()
    )
    filters: dict[str, Any] = {
        "action": action,
        "draw_id": str(draw_id) if draw_id else None,
        "participant_id": str(participant_id) if participant_id else None,
    }
    data, name = await export_service.export_audit(
        session, entries, filters, admin_login=admin, ip=client_ip(request)
    )
    return _csv_response(data, name)


# --- settings ---------------------------------------------------------------


@router.get("/settings")
async def settings_get(session: AsyncSession = Depends(get_session)) -> dict:
    return settings_view(await get_settings(session), await start_number_locked(session))


@router.put("/settings")
async def settings_put(
    body: SettingsPatch,
    request: Request,
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    new, locked = await update_settings(session, body, admin_login=admin, ip=client_ip(request))
    return settings_view(new, locked)
