"""Live screen: REST snapshot and WebSocket stream."""

import json
import logging

from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import live_access_ok, require_live_key
from app.db import async_session, get_session
from app.realtime.manager import manager
from app.services.auth import COOKIE_NAME
from app.services.live import build_snapshot

log = logging.getLogger("app.live")
router = APIRouter(tags=["live"])


@router.get("/api/live/current", dependencies=[Depends(require_live_key)])
async def live_current(session: AsyncSession = Depends(get_session)) -> dict:
    return await build_snapshot(session)


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    if not live_access_ok(websocket.query_params.get("key"), websocket.cookies.get(COOKIE_NAME)):
        await websocket.close(code=4403)
        return
    manager.add(websocket)
    try:
        async with async_session() as session:
            snapshot = await build_snapshot(session)
        await websocket.send_text(json.dumps(snapshot, ensure_ascii=False))
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
    except Exception as exc:  # noqa: BLE001 - client went away / transport error
        log.debug("ws closed: %r", exc)
    finally:
        manager.remove(websocket)
