"""Public endpoints: config, register, me, health."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, user_agent
from app.db import get_session
from app.errors import not_found
from app.schemas.requests import RegisterIn
from app.schemas.views import participant_public, public_config
from app.services.registration import RegistrationInput, find_by_token, parse_uuid, register
from app.services.settings import get_settings

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/config/public")
async def config_public(session: AsyncSession = Depends(get_session)) -> dict:
    return public_config(await get_settings(session))


@router.post("/register")
async def register_participant(
    body: RegisterIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    participant, created = await register(
        session,
        RegistrationInput(**body.model_dump()),
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    response.status_code = 201 if created else 200
    return participant_public(participant)


@router.get("/me/{token}")
async def me(token: str, session: AsyncSession = Depends(get_session)) -> dict:
    parsed = parse_uuid(token)
    participant = await find_by_token(session, parsed) if parsed else None
    if participant is None:
        raise not_found("Participant")
    return participant_public(participant)


@router.get("/health")
async def health(response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure => unhealthy
        response.status_code = 503
        return {"status": "error", "db": False}
    return {"status": "ok", "db": True}
