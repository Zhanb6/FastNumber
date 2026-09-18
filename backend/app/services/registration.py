"""Participant registration: validation, idempotency, rate limit, atomic numbering."""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.errors import ApiError
from app.models import Participant, ParticipantStatus
from app.services import audit
from app.services.notify import notify_participants
from app.services.numbering import lock_counter
from app.services.ratelimit import register_limiter
from app.services.settings import EventSettings, get_settings, write_setting

# Cyrillic block (incl. Kazakh letters ӘәҒғҚқҢңӨөҰұҮүҺһІі), Latin, space, hyphen, apostrophe.
NAME_RE = re.compile(r"^[A-Za-zЀ-ӿ' \-’]{1,60}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class RegistrationInput:
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    device_token: str | None = None


def normalise_phone(raw: str) -> str | None:
    """Return E.164 (+7XXXXXXXXXX for KZ/RU) or None if not a valid phone."""
    s = re.sub(r"[\s\-().]", "", raw.strip())
    if not s:
        return None
    plus = s.startswith("+")
    digits = s[1:] if plus else s
    if not digits.isdigit():
        return None
    if plus:
        if digits.startswith("7"):
            return f"+{digits}" if len(digits) == 11 else None
        return f"+{digits}" if 10 <= len(digits) <= 15 else None
    if len(digits) == 11 and digits[0] in "78":
        return f"+7{digits[1:]}"
    if len(digits) == 10:
        return f"+7{digits}"
    return None


def validate_name(value: str | None) -> tuple[str | None, str | None]:
    v = (value or "").strip()
    if not v:
        return None, "Обязательное поле"
    if len(v) > 60:
        return None, "Не более 60 символов"
    if not NAME_RE.match(v):
        return None, "Допустимы только буквы, пробел, дефис и апостроф"
    return v, None


def validate_fields(data: RegistrationInput, settings: EventSettings) -> dict[str, str | None]:
    """Validate according to enabled/required field settings. Raises 422 on errors."""
    errors: dict[str, str] = {}
    out: dict[str, str | None] = {"phone": None, "email": None, "company": None}

    first, err = validate_name(data.first_name)
    if err:
        errors["first_name"] = err
    last, err = validate_name(data.last_name)
    if err:
        errors["last_name"] = err

    f = settings.fields
    if f.phone.enabled:
        raw = (data.phone or "").strip()
        if raw:
            phone = normalise_phone(raw)
            if phone is None:
                errors["phone"] = "Неверный формат телефона"
            out["phone"] = phone
        elif f.phone.required:
            errors["phone"] = "Обязательное поле"
    if f.email.enabled:
        raw = (data.email or "").strip()
        if raw:
            if len(raw) > 254 or not EMAIL_RE.match(raw):
                errors["email"] = "Неверный формат email"
            out["email"] = raw.lower()
        elif f.email.required:
            errors["email"] = "Обязательное поле"
    if f.company.enabled:
        raw = (data.company or "").strip()
        if raw:
            if len(raw) > 120:
                errors["company"] = "Не более 120 символов"
            out["company"] = raw
        elif f.company.required:
            errors["company"] = "Обязательное поле"

    if errors:
        raise ApiError(422, "VALIDATION_ERROR", "Validation failed", {"fields": errors})
    out["first_name"] = first
    out["last_name"] = last
    return out


def parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value).strip())
    except ValueError:
        return None


async def find_by_token(session: AsyncSession, token: uuid.UUID) -> Participant | None:
    stmt = select(Participant).where(
        Participant.device_token == token,
        Participant.status.in_([ParticipantStatus.ACTIVE, ParticipantStatus.DISQUALIFIED]),
    )
    return (await session.execute(stmt)).scalars().first()


async def create_participant(
    session: AsyncSession,
    settings: EventSettings,
    *,
    first_name: str,
    last_name: str,
    phone: str | None = None,
    email: str | None = None,
    company: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    admin_login: str | None = None,
) -> Participant:
    """Allocate the next number and insert the participant. Does not commit.

    Raises 403 REGISTRATION_CLOSED (and commits the closure) when `on_max_reached=close`
    and the next number would exceed `max_number`.
    """
    counter = await lock_counter(session)
    number = counter.next_value
    if settings.on_max_reached == "close" and number > settings.max_number:
        if settings.registration_open:
            await write_setting(session, "registration_open", False)
            audit.log(
                session,
                "SETTINGS_CHANGED",
                entity_type="settings",
                admin_login=admin_login,
                ip=ip,
                metadata={
                    "changes": {"registration_open": {"old": True, "new": False}},
                    "reason": "max_number_reached",
                },
            )
            await session.commit()
        raise ApiError(403, "REGISTRATION_CLOSED", "Регистрация закрыта")
    counter.next_value = number + 1

    participant = Participant(
        number=number,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        company=company,
        device_token=uuid.uuid4(),
        status=ParticipantStatus.ACTIVE,
        ip=audit.normalise_ip(ip),
        user_agent=(user_agent or None) and user_agent[:1000],
    )
    session.add(participant)
    await session.flush()
    audit.log(
        session,
        "PARTICIPANT_REGISTERED",
        entity_type="participant",
        entity_id=participant.id,
        participant_id=participant.id,
        admin_login=admin_login,
        ip=ip,
        metadata={"number": number},
    )
    await notify_participants(session, "registered")
    return participant


async def register(
    session: AsyncSession,
    data: RegistrationInput,
    *,
    ip: str | None,
    user_agent: str | None,
) -> tuple[Participant, bool]:
    """Register (or return the existing participant for a known device token).

    Returns (participant, created).
    """
    settings = await get_settings(session)
    token = parse_uuid(data.device_token)
    if token is not None:
        existing = await find_by_token(session, token)
        if existing is not None:
            return existing, False

    if not settings.registration_open:
        raise ApiError(403, "REGISTRATION_CLOSED", "Регистрация закрыта")

    fields = validate_fields(data, settings)

    limit = get_config().register_rate_limit_per_min
    if not register_limiter.allow(ip or "unknown", limit):
        raise ApiError(429, "RATE_LIMITED", "Слишком много регистраций, попробуйте позже")

    participant = await create_participant(
        session,
        settings,
        first_name=fields["first_name"] or "",
        last_name=fields["last_name"] or "",
        phone=fields["phone"],
        email=fields["email"],
        company=fields["company"],
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return participant, True
