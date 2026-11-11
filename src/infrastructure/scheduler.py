import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class PeriodicJob:
    """Berilgan vazifani fon rejimida har `interval_seconds` soniyada takrorlaydi.
    Vazifa xato bersa, ish to'xtamaydi: xato yoziladi va keyingi marta qayta uriniladi."""

    def __init__(
        self, name: str, job: Callable[[], Awaitable[int]], interval_seconds: float
    ) -> None:
        self._name = name
        self._job = job
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _run(self) -> None:
        while True:
            try:
                handled = await self._job()
                if handled:
                    logger.info("%s: %d ta yozuv qayta ishlandi", self._name, handled)
            except Exception:
                logger.exception("%s failed", self._name)
            await asyncio.sleep(self._interval)
