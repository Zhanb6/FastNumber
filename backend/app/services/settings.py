"""Event settings: env defaults on first run, then the `settings` table wins.

Values are cached in-process; the cache is invalidated on every write.
"""

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.models import Setting
from app.util import utcnow


class FieldCfg(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = False
    required: bool = False


class FieldsCfg(BaseModel):
    model_config = ConfigDict(extra="ignore")
    phone: FieldCfg = Field(default_factory=FieldCfg)
    email: FieldCfg = Field(default_factory=FieldCfg)
    company: FieldCfg = Field(default_factory=FieldCfg)


class AnimationCfg(BaseModel):
    model_config = ConfigDict(extra="ignore")
    duration_ms: int = Field(default=8000, ge=1000, le=60000)
    sound: bool = False


class EventSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_name: str = Field(min_length=1, max_length=120)
    event_slug: str = Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    registration_open: bool
    allow_previous_winners: bool
    start_number: int = Field(ge=0, le=2_000_000_000)
    max_number: int = Field(ge=1, le=2_000_000_000)
    on_max_reached: str = Field(pattern=r"^(continue|close)$")
    timezone: str
    fields: FieldsCfg
    animation: AnimationCfg

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown timezone") from exc
        return v

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


SETTING_KEYS = tuple(EventSettings.model_fields.keys())

_cache: EventSettings | None = None


def env_defaults() -> dict[str, Any]:
    cfg = get_config()
    return {
        "event_name": cfg.event_name,
        "event_slug": cfg.event_slug,
        "registration_open": cfg.registration_open,
        "allow_previous_winners": cfg.allow_previous_winners,
        "start_number": cfg.start_number,
        "max_number": cfg.max_number,
        "on_max_reached": cfg.on_max_reached,
        "timezone": cfg.event_timezone,
        "fields": FieldsCfg().model_dump(),
        "animation": AnimationCfg(duration_ms=cfg.animation_duration_ms).model_dump(),
    }


def invalidate_cache() -> None:
    global _cache
    _cache = None


async def ensure_defaults(session: AsyncSession) -> None:
    """Insert missing keys from env defaults (first run). Does not commit."""
    for key, value in env_defaults().items():
        stmt = pg_insert(Setting).values(key=key, value=value, updated_at=utcnow())
        await session.execute(stmt.on_conflict_do_nothing(index_elements=["key"]))
    invalidate_cache()


async def load_settings(session: AsyncSession) -> EventSettings:
    """Read settings from DB (bypassing the cache)."""
    rows = (await session.execute(select(Setting))).scalars().all()
    data = env_defaults()
    for row in rows:
        if row.key in data:
            data[row.key] = row.value
    return EventSettings.model_validate(data)


async def get_settings(session: AsyncSession) -> EventSettings:
    global _cache
    if _cache is None:
        _cache = await load_settings(session)
    return _cache


async def write_setting(session: AsyncSession, key: str, value: Any) -> None:
    """Upsert one key. Does not commit; invalidates the cache."""
    stmt = pg_insert(Setting).values(key=key, value=value, updated_at=utcnow())
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"value": value, "updated_at": utcnow()}
    )
    await session.execute(stmt)
    invalidate_cache()
