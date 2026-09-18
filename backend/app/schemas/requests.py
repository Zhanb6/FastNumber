"""Request bodies (Pydantic v2)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _aware(v: datetime | None) -> datetime | None:
    """Naive datetimes are treated as UTC (DB columns are timestamptz)."""
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    first_name: str | None = Field(default=None, max_length=200)
    last_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=300)
    company: str | None = Field(default=None, max_length=300)
    device_token: str | None = Field(default=None, max_length=64)


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class DrawCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=120)
    prize: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    position: int | None = Field(default=None, ge=0, le=100000)
    scheduled_at: datetime | None = None
    exclude_previous_winners: bool | None = None

    _aware_scheduled = field_validator("scheduled_at")(_aware)


class DrawPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str | None = Field(default=None, min_length=1, max_length=120)
    prize: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    position: int | None = Field(default=None, ge=0, le=100000)
    scheduled_at: datetime | None = None
    exclude_previous_winners: bool | None = None

    _aware_scheduled = field_validator("scheduled_at")(_aware)


class ReasonIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reason: str | None = Field(default=None, max_length=500)


SettingsPatch = dict[str, Any]
