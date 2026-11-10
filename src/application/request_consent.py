import logging
from datetime import timedelta

from src.application.ports import Clock, ConsentNotifier
from src.domain.repositories import UserRepository

logger = logging.getLogger(__name__)


class RequestConsent:
    """Oxirgi xabaridan `idle_timeout` o'tgan foydalanuvchilardan
    ma'lumotlarni qayta ishlashga rozilik so'raydi (har bir foydalanuvchidan bir marta)."""

    def __init__(
        self,
        users: UserRepository,
        notifier: ConsentNotifier,
        clock: Clock,
        idle_timeout: timedelta,
    ) -> None:
        self._users = users
        self._notifier = notifier
        self._clock = clock
        self._idle_timeout = idle_timeout

    async def execute(self) -> int:
        now = self._clock.now()
        candidates = await self._users.find_awaiting_consent(now - self._idle_timeout)

        for user in candidates:
            try:
                await self._notifier.send_consent_request(user)
            except Exception:
                logger.exception("Consent request failed for user %s", user.telegram_id)
            # Yuborib bo'lmagan bo'lsa ham belgilaymiz, aks holda har tekshiruvda qayta urinadi
            user.mark_consent_requested(now)
            await self._users.save(user)

        return len(candidates)
