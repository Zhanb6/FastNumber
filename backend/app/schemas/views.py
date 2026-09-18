"""Response shapes as plain dicts (exact field names from the API contract)."""

from datetime import datetime
from typing import Any

from app.models import AuditLog, Draw, DrawResult, DrawResultStatus, Participant
from app.services.settings import EventSettings


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def participant_public(p: Participant) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "number": p.number,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "token": str(p.device_token) if p.device_token else None,
        "created_at": iso(p.created_at),
    }


def participant_short(p: Participant) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "number": p.number,
        "first_name": p.first_name,
        "last_name": p.last_name,
    }


def participant_admin(p: Participant, has_won: bool, pending_result: bool) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "number": p.number,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "phone": p.phone,
        "email": p.email,
        "company": p.company,
        "status": p.status.value,
        "status_reason": p.status_reason,
        "created_at": iso(p.created_at),
        "has_won": has_won,
        "pending_result": pending_result,
    }


def result_view(r: DrawResult) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "status": r.status.value,
        "participant": participant_short(r.participant),
        "eligible_count": r.eligible_count,
        "eligible_hash": r.eligible_hash,
        "reason": r.reason,
        "created_at": iso(r.created_at),
    }


def draw_ref(d: Draw) -> dict[str, Any]:
    return {"id": str(d.id), "title": d.title, "prize": d.prize}


def draw_view(d: Draw) -> dict[str, Any]:
    current = None
    for r in d.results:
        if r.status in (DrawResultStatus.SELECTED, DrawResultStatus.CONFIRMED):
            current = r
            break
    return {
        "id": str(d.id),
        "position": d.position,
        "title": d.title,
        "prize": d.prize,
        "description": d.description,
        "status": d.status.value,
        "exclude_previous_winners": d.exclude_previous_winners,
        "scheduled_at": iso(d.scheduled_at),
        "started_at": iso(d.started_at),
        "completed_at": iso(d.completed_at),
        "created_at": iso(d.created_at),
        "winner": participant_short(d.winner) if d.winner else None,
        "current_result": result_view(current) if current else None,
    }


def draw_detail(d: Draw, eligible_count: int, effective_exclude: bool) -> dict[str, Any]:
    view = draw_view(d)
    results = sorted(d.results, key=lambda r: r.created_at, reverse=True)
    view.update(
        {
            "eligible_count": eligible_count,
            "effective_exclude_previous_winners": effective_exclude,
            "results": [result_view(r) for r in results],
        }
    )
    return view


def audit_view(e: AuditLog) -> dict[str, Any]:
    return {
        "id": e.id,
        "action": e.action,
        "entity_type": e.entity_type,
        "entity_id": str(e.entity_id) if e.entity_id else None,
        "participant_id": str(e.participant_id) if e.participant_id else None,
        "draw_id": str(e.draw_id) if e.draw_id else None,
        "admin_login": e.admin_login,
        "ip": str(e.ip) if e.ip else None,
        "metadata": e.meta,
        "created_at": iso(e.created_at),
    }


def settings_view(s: EventSettings, locked: bool) -> dict[str, Any]:
    data = s.model_dump()
    data["start_number_locked"] = locked
    return data


def public_config(s: EventSettings) -> dict[str, Any]:
    return {
        "event_name": s.event_name,
        "registration_open": s.registration_open,
        "fields": s.fields.model_dump(),
    }
