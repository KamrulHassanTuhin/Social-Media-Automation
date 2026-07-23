from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone


class RateLimitExceeded(RuntimeError):
    pass


class ProviderRateLimiter:
    def __init__(self, limit_per_minute: int = 60) -> None:
        self.limit_per_minute = max(1, limit_per_minute)
        self._events: dict[str, deque[datetime]] = {}

    def acquire(self, key: str) -> None:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)
        events = self._events.setdefault(key, deque())
        while events and events[0] <= window_start:
            events.popleft()
        if len(events) >= self.limit_per_minute:
            raise RateLimitExceeded(f"Provider rate limit reached for {key}.")
        events.append(now)
