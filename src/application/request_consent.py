import logging
from datetime import timedelta

from src.application.ports import Clock, ConsentNotifier, PermanentDeliveryError
from src.domain.repositories import UserRepository

logger = logging.getLogger(__name__)

MAX_DELIVERY_ATTEMPTS = 3


class RequestConsent:
    """Oxirgi xabaridan `idle_timeout` o'tgan foydalanuvchilardan
    ma'lumotlarni qayta ishlashga rozilik so'raydi (har bir foydalanuvchidan bir marta).

    Tartib: avval so'rov huquqi atomar egallanadi, keyin xabar yuboriladi.
    Vaqtinchalik xatoda huquq qaytariladi va keyingi tekshiruvda qayta uriniladi
    (eng ko'pi bilan MAX_DELIVERY_ATTEMPTS marta). Doimiy xatoda (bot bloklangan)
    qayta urinilmaydi."""

    def __init__(
        self,
        users: UserRepository,
        notifier: ConsentNotifier,
        clock: Clock,
        idle_timeout: timedelta,
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._users = users
        self._notifier = notifier
        self._clock = clock
        self._idle_timeout = idle_timeout
        self._max_attempts = max_attempts
        self._failed_attempts: dict[int, int] = {}

    async def execute(self) -> int:
        """Yuborilgan so'rovlar sonini qaytaradi."""
        now = self._clock.now()
        idle_since = now - self._idle_timeout
        sent = 0

        for user in await self._users.find_awaiting_consent(idle_since):
            if not await self._users.claim_consent_request(user.telegram_id, idle_since, now):
                continue

            try:
                await self._notifier.send_consent_request(user)
            except PermanentDeliveryError:
                logger.warning("Consent request cannot be delivered to user %s", user.telegram_id)
                continue
            except Exception:
                await self._handle_transient_failure(user.telegram_id)
                continue

            self._failed_attempts.pop(user.telegram_id, None)
            sent += 1

        return sent

    async def _handle_transient_failure(self, telegram_id: int) -> None:
        attempts = self._failed_attempts.get(telegram_id, 0) + 1
        if attempts >= self._max_attempts:
            self._failed_attempts.pop(telegram_id, None)
            logger.exception("Giving up consent request for user %s", telegram_id)
            return

        self._failed_attempts[telegram_id] = attempts
        logger.exception(
            "Consent request failed for user %s (attempt %d), will retry", telegram_id, attempts
        )
        await self._users.release_consent_request(telegram_id)
