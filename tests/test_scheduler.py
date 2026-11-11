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


async def test_run_once_swallows_errors_and_reports_handled_items(caplog):
    outcomes = iter([3, RuntimeError("boom"), 0])

    async def job() -> int:
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    periodic = PeriodicJob("test job", job, interval_seconds=1)

    with caplog.at_level("INFO"):
        await periodic.run_once()
        await periodic.run_once()
        await periodic.run_once()

    assert "test job: 3 ta yozuv qayta ishlandi" in caplog.text
    assert "test job failed" in caplog.text
