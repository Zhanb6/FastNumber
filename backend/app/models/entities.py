"""ORM models (see spec section 16)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.util import utcnow


class ParticipantStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    DISQUALIFIED = "DISQUALIFIED"
    DELETED = "DELETED"


class DrawStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DrawResultStatus(enum.StrEnum):
    SELECTED = "SELECTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class LiveStateValue(enum.StrEnum):
    IDLE = "IDLE"
    COUNTDOWN = "COUNTDOWN"
    DRAWING = "DRAWING"
    WINNER = "WINNER"
    COMPLETED = "COMPLETED"


def _enum(py_enum: type[enum.Enum], name: str) -> Enum:
    return Enum(py_enum, name=name, native_enum=True, create_constraint=False)


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    last_name: Mapped[str] = mapped_column(String(60), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    company: Mapped[str | None] = mapped_column(String(120))
    device_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[ParticipantStatus] = mapped_column(
        _enum(ParticipantStatus, "participant_status"),
        nullable=False,
        default=ParticipantStatus.ACTIVE,
        index=True,
    )
    status_reason: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )

    results: Mapped[list["DrawResult"]] = relationship(back_populates="participant")


class NumberCounter(Base):
    __tablename__ = "number_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False)


class Draw(Base):
    __tablename__ = "draws"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    prize: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DrawStatus] = mapped_column(
        _enum(DrawStatus, "draw_status"), nullable=False, default=DrawStatus.DRAFT, index=True
    )
    exclude_previous_winners: Mapped[bool | None] = mapped_column(Boolean)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    winner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    winner: Mapped[Participant | None] = relationship(foreign_keys=[winner_id])
    results: Mapped[list["DrawResult"]] = relationship(
        back_populates="draw", order_by="DrawResult.created_at.desc()"
    )


class DrawResult(Base):
    __tablename__ = "draw_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draw_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("draws.id"), nullable=False, index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False, index=True
    )
    status: Mapped[DrawResultStatus] = mapped_column(
        _enum(DrawResultStatus, "draw_result_status"), nullable=False
    )
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    draw: Mapped[Draw] = relationship(back_populates="results")
    participant: Mapped[Participant] = relationship(back_populates="results")


class LiveState(Base):
    __tablename__ = "live_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[LiveStateValue] = mapped_column(
        _enum(LiveStateValue, "live_state_value"), nullable=False, default=LiveStateValue.IDLE
    )
    draw_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("draws.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    participant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    draw_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    admin_login: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(INET)
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )
