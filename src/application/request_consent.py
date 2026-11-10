import logging
from datetime import timedelta

from src.application.ports import Clock, ConsentNotifier, PermanentDeliveryError
from src.domain.repositories import ConsentRequestCriteria, UserRepository

logger = logging.getLogger(__name__)

MAX_DELIVERY_ATTEMPTS = 5
CLAIM_LEASE = timedelta(minutes=1)


class RequestConsent:
    """Oxirgi xabaridan `idle_timeout` o'tgan foydalanuvchilardan
    ma'lumotlarni qayta ishlashga rozilik so'raydi (har bir foydalanuvchidan bir marta).

    Tartib: so'rov huquqi bazada vaqtincha (`claim_lease` muddatga) egallanadi, xabar
    yuboriladi, so'ng so'rov yakunlangan deb belgilanadi. Yuborish xato bilan tugasa yoki
    jarayon o'rtada to'xtab qolsa, egallash muddati tugagach so'rov qayta olinadi.
    Urinishlar soni bazada saqlanadi va `max_attempts` bilan cheklanadi.
    Doimiy xatoda (masalan, bot bloklangan) qayta urinilmaydi."""

    def __init__(
        self,
        users: UserRepository,
        notifier: ConsentNotifier,
        clock: Clock,
        idle_timeout: timedelta,
        claim_lease: timedelta = CLAIM_LEASE,
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._users = users
        self._notifier = notifier
        self._clock = clock
        self._idle_timeout = idle_timeout
        self._claim_lease = claim_lease
        self._max_attempts = max_attempts

    async def execute(self) -> int:
        """Yetkazilgan so'rovlar sonini qaytaradi."""
        now = self._clock.now()
        criteria = ConsentRequestCriteria(
            idle_since=now - self._idle_timeout,
            stale_claim_before=now - self._claim_lease,
            max_attempts=self._max_attempts,
        )
        sent = 0

        for user in await self._users.find_awaiting_consent(criteria):
            if not await self._users.claim_consent_request(user.telegram_id, criteria, now):
                continue

            try:
                await self._notifier.send_consent_request(user)
            except PermanentDeliveryError:
                logger.warning("Consent request cannot be delivered to user %s", user.telegram_id)
                await self._users.abandon_consent_request(user.telegram_id, self._max_attempts)
                continue
            except Exception:
                # Egallash muddati tugagach so'rov o'zi qayta olinadi
                logger.exception("Consent request failed for user %s", user.telegram_id)
                continue

            await self._users.complete_consent_request(user.telegram_id, now)
            sent += 1

        return sent
