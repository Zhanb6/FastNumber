"""CSV exports: UTF-8 with BOM, ';' delimiter, CRLF, CSV-injection guard."""

import csv
import io
import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.services import audit
from app.services.participants import iter_participants_for_export, list_winners
from app.services.settings import get_settings
from app.util import utcnow

BOM = "﻿"
INJECTION_PREFIXES = ("=", "+", "-", "@")


def guard(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value)
    if s.startswith(INJECTION_PREFIXES):
        return "'" + s
    return s


def fmt_dt(dt: datetime | None, tz: ZoneInfo) -> str:
    if dt is None:
        return ""
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")


def render_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    for row in rows:
        writer.writerow([guard(v) for v in row])
    return (BOM + buf.getvalue()).encode("utf-8")


def filename(slug: str, kind: str, tz: ZoneInfo) -> str:
    stamp = utcnow().astimezone(tz).strftime("%Y-%m-%d_%H-%M")
    return f"{slug}_{kind}_{stamp}.csv"


async def _log_export(
    session: AsyncSession, kind: str, count: int, filters: dict[str, Any], admin_login, ip
) -> None:
    audit.log(
        session,
        "EXPORT",
        entity_type="export",
        admin_login=admin_login,
        ip=ip,
        metadata={"kind": kind, "rows": count, "filters": filters},
    )
    await session.commit()


async def export_participants(
    session: AsyncSession,
    *,
    q: str | None,
    status: str | None,
    won: bool | None,
    admin_login: str | None,
    ip: str | None,
) -> tuple[bytes, str]:
    settings = await get_settings(session)
    rows = await iter_participants_for_export(session, q=q, status=status, won=won)
    header = [
        "number", "first_name", "last_name", "phone", "email", "company",
        "status", "status_reason", "has_won", "created_at",
    ]  # fmt: skip
    data = [
        [
            p.number,
            p.first_name,
            p.last_name,
            p.phone,
            p.email,
            p.company,
            p.status.value,
            p.status_reason,
            has_won,
            fmt_dt(p.created_at, settings.tz),
        ]  # fmt: skip
        for p, has_won in rows
    ]
    await _log_export(
        session, "participants", len(data), {"q": q, "status": status, "won": won}, admin_login, ip
    )
    return render_csv(header, data), filename(settings.event_slug, "participants", settings.tz)


async def export_winners(
    session: AsyncSession, *, admin_login: str | None, ip: str | None
) -> tuple[bytes, str]:
    settings = await get_settings(session)
    items = await list_winners(session)
    header = [
        "draw_position", "draw_title", "prize", "number", "first_name", "last_name", "confirmed_at",
    ]  # fmt: skip
    data = [
        [
            w["draw_position"],
            w["draw_title"],
            w["prize"],
            w["number"],
            w["first_name"],
            w["last_name"],
            fmt_dt(w["confirmed_at"], settings.tz),
        ]  # fmt: skip
        for w in items
    ]
    await _log_export(session, "winners", len(data), {}, admin_login, ip)
    return render_csv(header, data), filename(settings.event_slug, "winners", settings.tz)


async def export_audit(
    session: AsyncSession,
    entries: list[AuditLog],
    filters: dict[str, Any],
    *,
    admin_login: str | None,
    ip: str | None,
) -> tuple[bytes, str]:
    settings = await get_settings(session)
    header = [
        "id", "created_at", "action", "entity_type", "entity_id", "participant_id",
        "draw_id", "admin_login", "ip", "metadata",
    ]  # fmt: skip
    data = [
        [
            e.id,
            fmt_dt(e.created_at, settings.tz),
            e.action,
            e.entity_type,
            e.entity_id,
            e.participant_id,
            e.draw_id,
            e.admin_login,
            e.ip,
            json.dumps(e.meta, ensure_ascii=False, sort_keys=True),
        ]  # fmt: skip
        for e in entries
    ]
    await _log_export(session, "audit", len(data), filters, admin_login, ip)
    return render_csv(header, data), filename(settings.event_slug, "audit", settings.tz)
