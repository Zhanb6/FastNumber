"""PostgreSQL LISTEN/NOTIFY bridge: DB events -> WebSocket broadcast.

`live_events`          -> rebuild the LiveSnapshot and broadcast `state`
`participants_changed` -> broadcast `participants_count`, debounced to <= 1 per 2 s
"""

import asyncio
import logging
import time

import asyncpg

from app.db import async_session
from app.realtime.manager import ConnectionManager
from app.services.live import active_count, build_snapshot
from app.services.notify import LIVE_CHANNEL, PARTICIPANTS_CHANNEL
from app.util import now_ms

log = logging.getLogger("app.realtime")

COUNT_DEBOUNCE_S = 2.0
MAX_BACKOFF_S = 10.0


class PgListener:
    def __init__(self, manager: ConnectionManager, dsn: str) -> None:
        self.manager = manager
        self.dsn = dsn
        self._conn: asyncpg.Connection | None = None
        self._run_task: asyncio.Task | None = None
        self._state_task: asyncio.Task | None = None
        self._count_task: asyncio.Task | None = None
        self._state_event = asyncio.Event()
        self._last_count_sent = 0.0
        self._stopping = False

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        self._stopping = False
        self._state_task = asyncio.create_task(self._state_worker(), name="live-state-worker")
        self._run_task = asyncio.create_task(self._run(), name="pg-listener")

    async def stop(self) -> None:
        self._stopping = True
        for task in (self._run_task, self._state_task, self._count_task):
            if task is not None:
                task.cancel()
        for task in (self._run_task, self._state_task, self._count_task):
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
        await self._close_conn()

    async def _close_conn(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None and not conn.is_closed():
            try:
                await asyncio.wait_for(conn.close(), timeout=2)
            except Exception:  # noqa: BLE001
                conn.terminate()

    # -- connection loop with backoff ----------------------------------------

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stopping:
            try:
                conn = await asyncpg.connect(self.dsn)
                self._conn = conn
                await conn.add_listener(LIVE_CHANNEL, self._on_notify)
                await conn.add_listener(PARTICIPANTS_CHANNEL, self._on_notify)
                backoff = 1.0
                log.info("pg listener connected")
                self.request_state()  # clients may have missed events while disconnected
                while not conn.is_closed():
                    await asyncio.sleep(1)
                log.warning("pg listener connection closed")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("pg listener error: %r (retry in %.0fs)", exc, backoff)
            await self._close_conn()
            if self._stopping:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)

    def _on_notify(self, _conn, _pid, channel: str, payload: str) -> None:
        if channel == LIVE_CHANNEL:
            self.request_state()
        elif channel == PARTICIPANTS_CHANNEL:
            self.request_count()

    # -- state broadcast (coalesced) -----------------------------------------

    def request_state(self) -> None:
        self._state_event.set()

    async def _state_worker(self) -> None:
        while True:
            await self._state_event.wait()
            self._state_event.clear()
            try:
                async with async_session() as session:
                    snapshot = await build_snapshot(session)
                await self.manager.broadcast(snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.exception("failed to broadcast state: %r", exc)

    # -- participants_count (debounced) --------------------------------------

    def request_count(self) -> None:
        if self._count_task is not None and not self._count_task.done():
            return
        self._count_task = asyncio.create_task(self._send_count_later(), name="count-debounce")

    async def _send_count_later(self) -> None:
        delay = max(0.0, self._last_count_sent + COUNT_DEBOUNCE_S - time.monotonic())
        if delay:
            await asyncio.sleep(delay)
        try:
            async with async_session() as session:
                count = await active_count(session)
            await self.manager.broadcast(
                {"type": "participants_count", "count": count, "server_time": now_ms()}
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("failed to broadcast participants_count: %r", exc)
        finally:
            self._last_count_sent = time.monotonic()
