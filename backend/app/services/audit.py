"""Append-only audit log writer."""

import ipaddress
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def normalise_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip.strip()))
    except ValueError:
        return None


def log(
    session: AsyncSession,
    action: str,
    *,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    participant_id: uuid.UUID | None = None,
    draw_id: uuid.UUID | None = None,
    admin_login: str | None = None,
    ip: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit entry to the session (caller commits)."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        participant_id=participant_id,
        draw_id=draw_id,
        admin_login=admin_login,
        ip=normalise_ip(ip),
        meta=metadata or {},
    )
    session.add(entry)
    return entry
