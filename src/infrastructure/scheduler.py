import asyncio
import contextlib
import logging

from src.application.request_consent import RequestConsent

logger = logging.getLogger(__name__)


class ConsentScheduler:
    """Fon rejimida har `interval` soniyada rozilik so'rovlarini tekshirib turadi."""

    def __init__(self, request_consent: RequestConsent, interval_seconds: int) -> None:
        self._request_consent = request_consent
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
                sent = await self._request_consent.execute()
                if sent:
                    logger.info("Consent requested from %d user(s)", sent)
            except Exception:
                logger.exception("Consent check failed")
            await asyncio.sleep(self._interval)
