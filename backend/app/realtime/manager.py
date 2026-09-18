"""In-process WebSocket connection registry with fan-out broadcast."""

import asyncio
import json
import logging
from typing import Any, Protocol

log = logging.getLogger("app.realtime")


class Sender(Protocol):
    async def send_text(self, data: str) -> None: ...


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: set[Any] = set()

    def add(self, ws: Sender) -> None:
        self._conns.add(ws)

    def remove(self, ws: Sender) -> None:
        self._conns.discard(ws)

    @property
    def count(self) -> int:
        return len(self._conns)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._conns:
            return
        data = json.dumps(message, ensure_ascii=False)
        targets = list(self._conns)
        results = await asyncio.gather(
            *(ws.send_text(data) for ws in targets), return_exceptions=True
        )
        for ws, res in zip(targets, results, strict=True):
            if isinstance(res, BaseException):
                log.debug("dropping ws after send failure: %r", res)
                self._conns.discard(ws)


manager = ConnectionManager()
