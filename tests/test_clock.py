from datetime import UTC, datetime, timedelta

from src.infrastructure.clock import SystemClock


def test_system_clock_returns_timezone_aware_utc_time():
    now = SystemClock().now()

    assert now.tzinfo is not None and now.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - now) < timedelta(seconds=5)
