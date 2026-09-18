"""Partial settings update with audit and start_number lock."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Participant
from app.services import audit
from app.services.notify import notify_live
from app.services.numbering import reset_counter
from app.services.settings import (
    SETTING_KEYS,
    EventSettings,
    get_settings,
    invalidate_cache,
    load_settings,
    write_setting,
)


async def start_number_locked(session: AsyncSession) -> bool:
    stmt = select(exists().where(Participant.id.isnot(None)))
    return bool((await session.execute(stmt)).scalar_one())


def _merge(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in patch.items():
        if key not in SETTING_KEYS:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = {k: dict(v) if isinstance(v, dict) else v for k, v in merged[key].items()}
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, dict) and isinstance(nested.get(sub_key), dict):
                    nested[sub_key] = {**nested[sub_key], **sub_val}
                else:
                    nested[sub_key] = sub_val
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _validation_error(exc: ValidationError) -> ApiError:
    fields = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "body"
        fields.setdefault(loc, err["msg"])
    return ApiError(422, "VALIDATION_ERROR", "Validation failed", {"fields": fields})


async def update_settings(
    session: AsyncSession, patch: dict[str, Any], *, admin_login: str | None, ip: str | None
) -> tuple[EventSettings, bool]:
    current = await load_settings(session)
    current_dict = current.model_dump()
    try:
        new = EventSettings.model_validate(_merge(current_dict, patch))
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    new_dict = new.model_dump()

    changes = {
        key: {"old": current_dict[key], "new": new_dict[key]}
        for key in SETTING_KEYS
        if current_dict[key] != new_dict[key]
    }
    locked = await start_number_locked(session)
    if "start_number" in changes and locked:
        raise ApiError(
            409,
            "START_NUMBER_LOCKED",
            "Start number cannot be changed after the first registration",
        )
    if not changes:
        return new, locked

    for key in changes:
        await write_setting(session, key, new_dict[key])
    if "start_number" in changes:
        await reset_counter(session, new.start_number)
    audit.log(
        session,
        "SETTINGS_CHANGED",
        entity_type="settings",
        admin_login=admin_login,
        ip=ip,
        metadata={"changes": changes},
    )
    await notify_live(session, "settings_changed")
    await session.commit()
    invalidate_cache()
    await get_settings(session)
    return new, locked
