from datetime import timedelta

from src.infrastructure.rate_limiter import SWEEP_EVERY, InMemoryRateLimiter
from tests.fakes import FakeClock

WINDOW = timedelta(seconds=10)


def make_limiter(clock: FakeClock, max_events: int = 3) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(clock, max_events=max_events, window=WINDOW)


def test_actions_over_the_limit_are_refused():
    limiter = make_limiter(FakeClock())

    results = [limiter.allow(1) for _ in range(5)]

    assert results == [True, True, True, False, False]


def test_allowed_again_after_the_window_passes():
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(3):
        limiter.allow(1)

    clock.advance(seconds=9)
    assert limiter.allow(1) is False
    clock.advance(seconds=1)
    assert limiter.allow(1) is True


def test_users_are_limited_independently():
    limiter = make_limiter(FakeClock(), max_events=1)

    assert limiter.allow(1) is True
    assert limiter.allow(1) is False
    assert limiter.allow(2) is True


def test_refused_actions_do_not_extend_the_block():
    clock = FakeClock()
    limiter = make_limiter(clock, max_events=1)
    limiter.allow(1)

    for _ in range(20):
        clock.advance(seconds=0.4)
        limiter.allow(1)  # 8 soniya davomida urinish

    clock.advance(seconds=2)
    assert limiter.allow(1) is True


def test_inactive_users_are_dropped_from_memory():
    clock = FakeClock()
    limiter = make_limiter(clock)
    for user_id in range(50):
        limiter.allow(user_id)
    clock.advance(minutes=5)

    for _ in range(SWEEP_EVERY):
        limiter.allow(10_000)

    assert set(limiter._events) == {10_000}
