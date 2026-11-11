import asyncio

from src.infrastructure.scheduler import PeriodicJob


async def wait_until(condition, timeout: float = 2.0) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.005)


async def test_job_runs_repeatedly_until_stopped():
    calls = 0

    async def job() -> int:
        nonlocal calls
        calls += 1
        return 0

    periodic = PeriodicJob("test", job, interval_seconds=0.01)
    periodic.start()
    await wait_until(lambda: calls >= 3)
    await periodic.stop()

    stopped_at = calls
    await asyncio.sleep(0.05)
    assert calls == stopped_at


async def test_failing_job_does_not_stop_the_loop():
    calls = 0

    async def job() -> int:
        nonlocal calls
        calls += 1
        raise RuntimeError("database is down")

    periodic = PeriodicJob("test", job, interval_seconds=0.01)
    periodic.start()
    await wait_until(lambda: calls >= 3)
    await periodic.stop()


async def test_stop_before_start_is_safe():
    async def job() -> int:
        return 0

    await PeriodicJob("test", job, interval_seconds=1).stop()
