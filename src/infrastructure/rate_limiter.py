from collections import deque
from datetime import datetime, timedelta

from src.application.ports import Clock, RateLimiter

SWEEP_EVERY = 1000


class InMemoryRateLimiter(RateLimiter):
    """Sirpanuvchi oyna: har bir kalit uchun `window` ichida ko'pi bilan `max_events` ta harakat.
    Holat xotirada saqlanadi, shuning uchun bot qayta ishga tushsa nolga qaytadi."""

    def __init__(self, clock: Clock, max_events: int, window: timedelta) -> None:
        self._clock = clock
        self._max_events = max_events
        self._window = window
        self._events: dict[int, deque[datetime]] = {}
        self._calls = 0

    def allow(self, key: int) -> bool:
        now = self._clock.now()
        self._calls += 1
        if self._calls % SWEEP_EVERY == 0:
            self._sweep(now)

        events = self._events.setdefault(key, deque())
        self._drop_expired(events, now)
        if len(events) >= self._max_events:
            return False
        events.append(now)
        return True

    def _drop_expired(self, events: deque[datetime], now: datetime) -> None:
        while events and now - events[0] >= self._window:
            events.popleft()

    def _sweep(self, now: datetime) -> None:
        """Uzoq vaqt yozmagan foydalanuvchilarni xotiradan chiqaradi."""
        for key in list(self._events):
            self._drop_expired(self._events[key], now)
            if not self._events[key]:
                del self._events[key]
