"""In-memory rate limiters (single process is enough for the event)."""

import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, limit: int) -> bool:
        """Record a hit for `key`; return False if the limit is exceeded. limit<=0 disables."""
        if limit <= 0:
            return True
        now = time.monotonic()
        q = self._hits.setdefault(key, deque())
        cutoff = now - self.window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def clear(self) -> None:
        self._hits.clear()


class LoginLimiter:
    """5 failures within 5 minutes per IP => blocked for 5 minutes."""

    def __init__(self, max_failures: int = 5, window_seconds: float = 300.0) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._fails: dict[str, deque[float]] = {}
        self._blocked_until: dict[str, float] = {}

    def is_blocked(self, key: str) -> bool:
        until = self._blocked_until.get(key)
        if until is None:
            return False
        if until <= time.monotonic():
            del self._blocked_until[key]
            self._fails.pop(key, None)
            return False
        return True

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        q = self._fails.setdefault(key, deque())
        cutoff = now - self.window
        while q and q[0] < cutoff:
            q.popleft()
        q.append(now)
        if len(q) >= self.max_failures:
            self._blocked_until[key] = now + self.window
            q.clear()

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)
        self._blocked_until.pop(key, None)

    def clear(self) -> None:
        self._fails.clear()
        self._blocked_until.clear()


register_limiter = SlidingWindowLimiter(window_seconds=60.0)
login_limiter = LoginLimiter()
