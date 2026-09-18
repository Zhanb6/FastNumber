"""Small shared helpers."""

import time
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def now_ms() -> int:
    return int(time.time() * 1000)


def to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)
